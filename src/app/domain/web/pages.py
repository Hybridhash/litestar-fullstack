from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Controller, get
from litestar.di import Provide
from litestar.enums import MediaType
from litestar.exceptions import PermissionDeniedException
from litestar.repository.exceptions import NotFoundError
from litestar.response import Template
from litestar.status_codes import HTTP_200_OK
from sqlalchemy import select
from sqlalchemy.orm import load_only, selectinload

from app.db import models as m
from app.db.models.team_member import TeamMember as TeamMemberModel
from app.domain.accounts.deps import provide_users_service
from app.domain.accounts.guards import requires_active_user, requires_superuser
from app.domain.teams import urls
from app.domain.teams.guards import requires_team_admin, requires_team_membership
from app.domain.teams.services import TeamInvitationService, TeamMemberService, TeamService
from app.domain.web.notification_helpers import build_notification_context
from app.domain.web.table_helpers import (
    build_team_invitations_table,
    build_team_members_table,
    build_teams_table,
    build_users_table,
)
from app.lib.deps import create_service_provider

if TYPE_CHECKING:
    from uuid import UUID

    from litestar.plugins.htmx import HTMXRequest
    from sqlalchemy.sql.elements import ColumnElement

    from app.domain.accounts.services import UserService


class SiteController(Controller):
    """Server-rendered page routes."""

    include_in_schema = False
    dependencies = {
        "users_service": Provide(provide_users_service),
        "teams_service": Provide(create_service_provider(TeamService)),
        "team_members_service": Provide(
            create_service_provider(
                TeamMemberService,
                load=[
                    selectinload(m.TeamMember.user).options(
                        # Security: Only load display-safe User fields for team member listings
                        load_only(
                            m.User.id,
                            m.User.email,
                            m.User.name,
                            m.User.avatar_url,
                            m.User.is_active,
                        ),
                    ),
                ],
            ),
        ),
        "team_invitations_service": Provide(create_service_provider(TeamInvitationService)),
    }

    @get(path="/dashboard", operation_id="WebDashboard", guards=[requires_active_user], status_code=HTTP_200_OK)
    async def dashboard(
        self,
        request: HTMXRequest,
        teams_service: TeamService,
        users_service: UserService,
    ) -> Template:
        membership_filters: list[ColumnElement[bool]] = []
        if not teams_service.can_view_all(request.user):
            membership_filters.append(
                m.Team.id.in_(select(TeamMemberModel.team_id).where(TeamMemberModel.user_id == request.user.id)),
            )
        _teams, team_total = await teams_service.list_and_count(*membership_filters)
        _users, user_total = await users_service.list_and_count()
        return Template(
            template_name="site/dashboard.jinja",
            context={"user": request.user, "team_total": team_total, "user_total": user_total},
            media_type=MediaType.HTML,
        )

    @get(path="/users", operation_id="WebUsers", guards=[requires_superuser], status_code=HTTP_200_OK)
    async def users_page(
        self,
        users_service: UserService,
        q: str | None = None,
        filter_by: str | None = None,
    ) -> Template:
        users, _ = await users_service.list_and_count()
        context = build_users_table(users, query=q, filter_by=filter_by)
        return Template(
            template_name="site/users.jinja",
            context={
                "user_total": context["total"],
                "query": q or "",
                "filter_by": context["filter_by"],
            },
            media_type=MediaType.HTML,
        )

    @get(path="/teams", operation_id="WebTeams", guards=[requires_active_user], status_code=HTTP_200_OK)
    async def teams_page(
        self,
        request: HTMXRequest,
        teams_service: TeamService,
        q: str | None = None,
        filter_by: str | None = None,
    ) -> Template:
        membership_filters: list[ColumnElement[bool]] = []
        if not teams_service.can_view_all(request.user):
            membership_filters.append(
                m.Team.id.in_(select(TeamMemberModel.team_id).where(TeamMemberModel.user_id == request.user.id)),
            )
        teams, _ = await teams_service.list_and_count(*membership_filters)
        context = build_teams_table(teams, query=q, filter_by=filter_by)
        return Template(
            template_name="site/teams.jinja",
            context={
                "team_total": context["total"],
                "query": q or "",
                "filter_by": context["filter_by"],
            },
            media_type=MediaType.HTML,
        )

    @get(
        path=urls.TEAM_MEMBERS_PAGE,
        operation_id="WebTeamMembers",
        guards=[requires_active_user, requires_team_membership],
        status_code=HTTP_200_OK,
    )
    async def team_members_page(
        self,
        request: HTMXRequest,
        teams_service: TeamService,
        team_members_service: TeamMemberService,
        team_id: UUID,
        q: str | None = None,
        page: int = 1,
    ) -> Template:
        team = await teams_service.get(team_id)
        members, _ = await team_members_service.list_and_count(m.TeamMember.team_id == team_id)
        context = build_team_members_table(members, query=q, page=page)
        return Template(
            template_name="site/team_members.jinja",
            context={
                "team": team,
                "team_id": team_id,
                "member_total": context["total"],
                "query": q or "",
            },
            media_type=MediaType.HTML,
        )

    @get(
        path=urls.TEAM_INVITATION_PAGE,
        operation_id="WebTeamInvitations",
        guards=[requires_active_user, requires_team_admin],
        status_code=HTTP_200_OK,
    )
    async def team_invitations_page(
        self,
        request: HTMXRequest,
        teams_service: TeamService,
        team_invitations_service: TeamInvitationService,
        team_id: UUID,
        q: str | None = None,
    ) -> Template:
        team = await teams_service.get(team_id)
        invitations, _ = await team_invitations_service.list_and_count(m.TeamInvitation.team_id == team_id)
        context = build_team_invitations_table(invitations, query=q)
        return Template(
            template_name="site/team_invitations.jinja",
            context={
                "team": team,
                "team_id": team_id,
                "invitation_total": context["total"],
                "query": q or "",
            },
            media_type=MediaType.HTML,
        )

    @get(
        path="/notifications",
        operation_id="WebNotificationsDropdown",
        guards=[requires_active_user],
        status_code=HTTP_200_OK,
    )
    async def notifications_dropdown(
        self,
        request: HTMXRequest,
        teams_service: TeamService,
        team_invitations_service: TeamInvitationService,
    ) -> Template:
        context = await build_notification_context(
            email=request.user.email,
            team_invitations_service=team_invitations_service,
            teams_service=teams_service,
        )
        return Template(
            template_name="partials/notifications_dropdown.jinja",
            context=context,
            media_type=MediaType.HTML,
        )

    @get(
        path="/invitations/{invitation_id:uuid}",
        operation_id="WebInvitationResponse",
        guards=[requires_active_user],
        status_code=HTTP_200_OK,
    )
    async def invitation_response_page(
        self,
        request: HTMXRequest,
        teams_service: TeamService,
        team_invitations_service: TeamInvitationService,
        invitation_id: UUID,
        status: str | None = None,
    ) -> Template:
        normalized_status = status.lower() if status else None
        if normalized_status not in {"accepted", "declined"}:
            normalized_status = None

        invitation = None
        team = None
        if normalized_status == "declined":
            try:
                invitation = await team_invitations_service.get(invitation_id)
            except NotFoundError:
                invitation = None
        else:
            invitation = await team_invitations_service.get(invitation_id)

        if invitation:
            if invitation.email.lower() != request.user.email.lower():
                raise PermissionDeniedException(detail="Insufficient permissions to respond to invitation.")
            team = await teams_service.get(invitation.team_id)

        return Template(
            template_name="site/invitation_response.jinja",
            context={"invitation": invitation, "team": team, "status": normalized_status},
            media_type=MediaType.HTML,
        )

    @get(path="/profile", operation_id="WebProfile", guards=[requires_active_user], status_code=HTTP_200_OK)
    async def profile_page(self, request: HTMXRequest) -> Template:
        return Template(template_name="site/profile.jinja", context={"user": request.user}, media_type=MediaType.HTML)

    @get(path="/settings", operation_id="WebSettings", guards=[requires_active_user], status_code=HTTP_200_OK)
    async def settings_page(self) -> Template:
        return Template(template_name="site/settings.jinja", context={"theme": "litestar"}, media_type=MediaType.HTML)
