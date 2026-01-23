"""User Account Controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING, overload

from litestar import Controller, Response, get, patch, post
from litestar.di import Provide
from litestar.params import Parameter
from litestar.plugins.htmx import HTMXRequest, HTMXTemplate
from litestar.status_codes import HTTP_303_SEE_OTHER, HTTP_409_CONFLICT
from sqlalchemy.orm import contains_eager, selectinload

from app.db import models as m
from app.domain.accounts.deps import provide_users_service
from app.domain.accounts.guards import requires_active_user
from app.domain.teams import urls
from app.domain.teams.guards import requires_team_admin, requires_team_membership
from app.domain.teams.schemas import Team, TeamMember, TeamMemberModify, TeamMemberUpdate
from app.domain.teams.services import TeamMemberService, TeamService
from app.domain.web.table_helpers import build_team_members_table
from app.lib.deps import create_service_provider

if TYPE_CHECKING:
    from uuid import UUID

    from advanced_alchemy.service.pagination import OffsetPagination

    from app.domain.accounts.services import UserService


class TeamMemberController(Controller):
    """Team Members."""

    tags = ["Team Members"]
    guards = [requires_active_user]
    dependencies = {
        "teams_service": create_service_provider(TeamService, load=[m.Team.tags, m.Team.members]),
        "team_members_service": create_service_provider(
            TeamMemberService,
            load=[
                selectinload(m.TeamMember.team).options(contains_eager(m.Team.tags)),
                selectinload(m.TeamMember.user),
            ],
        ),
        "users_service": Provide(provide_users_service),
    }

    @get(operation_id="ListTeamMembers", guards=[requires_team_membership], path=urls.TEAM_MEMBERS_LIST)
    async def list_team_members(
        self,
        request: HTMXRequest,
        team_members_service: TeamMemberService,
        team_id: UUID = Parameter(title="Team ID", description="The team to list."),
        q: str | None = None,
        page: int = 1,
    ) -> OffsetPagination[TeamMember] | HTMXTemplate:
        """List team members."""
        members, total = await team_members_service.list_and_count(m.TeamMember.team_id == team_id)
        if request.htmx or request.headers.get("HX-Request", "").lower() == "true":
            context = build_team_members_table(members, query=q, page=page)
            context["team_id"] = str(team_id)
            return HTMXTemplate(template_name="partials/team_members_table.jinja", context=context)
        return team_members_service.to_schema(schema_type=TeamMember, data=members, total=total)

    def _wants_html(self, request: HTMXRequest) -> bool:
        accept = request.headers.get("accept", "")
        return "text/html" in accept.lower()

    @overload
    async def _parse_payload(
        self,
        request: HTMXRequest,
        schema_type: type[TeamMemberModify],
    ) -> TeamMemberModify: ...

    @overload
    async def _parse_payload(
        self,
        request: HTMXRequest,
        schema_type: type[TeamMemberUpdate],
    ) -> TeamMemberUpdate: ...

    async def _parse_payload(
        self,
        request: HTMXRequest,
        schema_type: type[TeamMemberModify | TeamMemberUpdate],
    ) -> TeamMemberModify | TeamMemberUpdate:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = await request.json()
        else:
            form_data = await request.form()
            payload = dict(form_data)
        return schema_type(**payload)

    def _feedback_response(self, request: HTMXRequest, message: str) -> HTMXTemplate | Response:
        if request.htmx:
            return HTMXTemplate(template_name="partials/feedback.jinja", context={"message": message})
        return Response({"message": message}, status_code=HTTP_409_CONFLICT)

    @post(operation_id="AddMemberToTeam", guards=[requires_team_admin], path=urls.TEAM_ADD_MEMBER)
    async def add_member_to_team(
        self,
        request: HTMXRequest,
        teams_service: TeamService,
        team_members_service: TeamMemberService,
        users_service: UserService,
        team_id: UUID = Parameter(title="Team ID", description="The team to update."),
    ) -> Team | HTMXTemplate | Response:
        """Add a member to a team."""
        data = await self._parse_payload(request, TeamMemberModify)
        team_obj = await teams_service.get(team_id)
        user_obj = await users_service.get_one(email=data.user_name)
        is_member = any(membership.team.id == team_id for membership in user_obj.teams)
        if is_member:
            msg = "User is already a member of the team."
            return self._feedback_response(request, msg)
        role = data.role or m.TeamRoles.MEMBER
        team_obj.members.append(m.TeamMember(user_id=user_obj.id, team_id=team_id, role=role))
        team_obj = await teams_service.update(item_id=team_id, data=team_obj)
        if request.htmx:
            members, _ = await team_members_service.list_and_count(m.TeamMember.team_id == team_id)
            context = build_team_members_table(members)
            context["team_id"] = str(team_id)
            return HTMXTemplate(template_name="partials/team_members_table.jinja", context=context)
        if self._wants_html(request):
            return Response(
                content=None, status_code=HTTP_303_SEE_OTHER, headers={"Location": f"/teams/{team_id}/members"}
            )
        return teams_service.to_schema(schema_type=Team, data=team_obj)

    @post(operation_id="RemoveMemberFromTeam", guards=[requires_team_admin], path=urls.TEAM_REMOVE_MEMBER)
    async def remove_member_from_team(
        self,
        request: HTMXRequest,
        teams_service: TeamService,
        team_members_service: TeamMemberService,
        users_service: UserService,
        team_id: UUID = Parameter(title="Team ID", description="The team to delete."),
    ) -> Team | HTMXTemplate | Response:
        """Revoke a members access to a team."""
        data = await self._parse_payload(request, TeamMemberModify)
        user_obj = await users_service.get_one(email=data.user_name)
        removed_member = False
        for membership in user_obj.teams:
            if membership.user_id == user_obj.id and membership.team_id == team_id:
                removed_member = True
                _ = await team_members_service.delete(membership.id)
        if not removed_member:
            msg = "User is not a member of this team."
            return self._feedback_response(request, msg)
        team_obj = await teams_service.get(team_id)
        if request.htmx:
            members, _ = await team_members_service.list_and_count(m.TeamMember.team_id == team_id)
            context = build_team_members_table(members)
            context["team_id"] = str(team_id)
            return HTMXTemplate(template_name="partials/team_members_table.jinja", context=context)
        if self._wants_html(request):
            return Response(
                content=None, status_code=HTTP_303_SEE_OTHER, headers={"Location": f"/teams/{team_id}/members"}
            )
        return teams_service.to_schema(schema_type=Team, data=team_obj)

    @patch(
        operation_id="UpdateTeamMemberRole",
        guards=[requires_team_admin],
        path=urls.TEAM_UPDATE_MEMBER_ROLE,
    )
    async def update_member_role(
        self,
        request: HTMXRequest,
        team_members_service: TeamMemberService,
        team_id: UUID = Parameter(title="Team ID", description="The team to update."),
        member_id: UUID = Parameter(title="Member ID", description="The team member to update."),
    ) -> TeamMember | HTMXTemplate | Response:
        """Update a team member's role."""
        data = await self._parse_payload(request, TeamMemberUpdate)
        member = await team_members_service.get(member_id)
        if member.team_id != team_id:
            msg = "User is not a member of this team."
            return self._feedback_response(request, msg)
        updated_member = await team_members_service.update(item_id=member_id, data=data.to_dict())
        if request.htmx:
            members, _ = await team_members_service.list_and_count(m.TeamMember.team_id == team_id)
            context = build_team_members_table(members)
            context["team_id"] = str(team_id)
            return HTMXTemplate(template_name="partials/team_members_table.jinja", context=context)
        if self._wants_html(request):
            return Response(
                content=None, status_code=HTTP_303_SEE_OTHER, headers={"Location": f"/teams/{team_id}/members"}
            )
        return team_members_service.to_schema(schema_type=TeamMember, data=updated_member)
