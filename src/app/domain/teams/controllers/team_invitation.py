"""Team invitation controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Controller, Response, get, post
from litestar.exceptions import PermissionDeniedException
from litestar.params import Parameter
from litestar.plugins.htmx import HTMXRequest, HTMXTemplate
from litestar.status_codes import HTTP_303_SEE_OTHER, HTTP_409_CONFLICT

from app.db import models as m
from app.domain.accounts.guards import requires_active_user
from app.domain.teams import urls
from app.domain.teams.guards import requires_team_admin
from app.domain.teams.schemas import TeamInvitation, TeamInvitationCreate
from app.domain.teams.services import TeamInvitationService, TeamMemberService, TeamService
from app.domain.web.notification_helpers import build_notification_context
from app.domain.web.table_helpers import build_team_invitations_table
from app.lib.deps import create_service_provider

if TYPE_CHECKING:
    from uuid import UUID

    from advanced_alchemy.service.pagination import OffsetPagination


class TeamInvitationController(Controller):
    """Team Invitations."""

    tags = ["Teams"]
    guards = [requires_active_user]
    dependencies = {
        "team_invitations_service": create_service_provider(TeamInvitationService),
        "team_members_service": create_service_provider(TeamMemberService),
        "teams_service": create_service_provider(TeamService),
    }

    async def _parse_payload(self, request: HTMXRequest) -> TeamInvitationCreate:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = await request.json()
        else:
            form_data = await request.form()
            payload = dict(form_data)
        return TeamInvitationCreate(**payload)

    def _wants_html(self, request: HTMXRequest) -> bool:
        accept = request.headers.get("accept", "")
        return "text/html" in accept.lower()

    def _feedback_response(self, request: HTMXRequest, message: str) -> HTMXTemplate | Response:
        if request.htmx:
            return HTMXTemplate(template_name="partials/feedback.jinja", context={"message": message})
        return Response({"message": message}, status_code=HTTP_409_CONFLICT)

    def _panel_or_feedback_response(
        self,
        request: HTMXRequest,
        message: str,
        invitation: m.TeamInvitation | None = None,
    ) -> HTMXTemplate | Response:
        if request.htmx:
            return self._panel_response(invitation=invitation, message=message)
        return self._feedback_response(request, message)

    def _panel_response(
        self,
        invitation: m.TeamInvitation | None = None,
        status: str | None = None,
        message: str | None = None,
    ) -> HTMXTemplate:
        return HTMXTemplate(
            template_name="partials/invitation_response_panel.jinja",
            context={"invitation": invitation, "status": status, "message": message},
        )

    async def _notifications_response(
        self,
        request: HTMXRequest,
        team_invitations_service: TeamInvitationService,
        teams_service: TeamService,
    ) -> HTMXTemplate:
        context = await build_notification_context(
            email=request.user.email,
            team_invitations_service=team_invitations_service,
            teams_service=teams_service,
        )
        return HTMXTemplate(template_name="partials/notifications_dropdown.jinja", context=context)

    @get(operation_id="ListTeamInvitations", guards=[requires_team_admin], path=urls.TEAM_INVITATION_LIST)
    async def list_team_invitations(
        self,
        request: HTMXRequest,
        team_invitations_service: TeamInvitationService,
        team_id: UUID = Parameter(title="Team ID", description="The team to list invitations for."),
        q: str | None = None,
    ) -> OffsetPagination[TeamInvitation] | HTMXTemplate:
        invitations, total = await team_invitations_service.list_and_count(m.TeamInvitation.team_id == team_id)
        if request.htmx or request.headers.get("HX-Request", "").lower() == "true":
            context = build_team_invitations_table(invitations, query=q)
            context["team_id"] = str(team_id)
            return HTMXTemplate(template_name="partials/team_invitations_table.jinja", context=context)
        return team_invitations_service.to_schema(schema_type=TeamInvitation, data=invitations, total=total)

    @post(operation_id="SendTeamInvitation", guards=[requires_team_admin], path=urls.TEAM_INVITATION_LIST)
    async def send_invitation(
        self,
        request: HTMXRequest,
        team_invitations_service: TeamInvitationService,
        team_id: UUID = Parameter(title="Team ID", description="The team to invite to."),
        current_user: m.User | None = None,
    ) -> TeamInvitation | HTMXTemplate | Response:
        data = await self._parse_payload(request)
        payload = data.to_dict()
        payload.update(
            {
                "team_id": team_id,
                "invited_by_id": getattr(current_user, "id", None),
                "invited_by_email": getattr(current_user, "email", None),
            },
        )
        try:
            invitation = await team_invitations_service.create(payload)
        except Exception as exc:  # noqa: BLE001
            return self._feedback_response(request, getattr(exc, "detail", "Unable to send invitation."))

        if request.htmx:
            invitations, _ = await team_invitations_service.list_and_count(m.TeamInvitation.team_id == team_id)
            context = build_team_invitations_table(invitations)
            context["team_id"] = str(team_id)
            return HTMXTemplate(template_name="partials/team_invitations_table.jinja", context=context)
        if self._wants_html(request):
            return Response(
                content=None,
                status_code=HTTP_303_SEE_OTHER,
                headers={"Location": f"/teams/{team_id}/invitations"},
            )
        return team_invitations_service.to_schema(schema_type=TeamInvitation, data=invitation)

    @post(operation_id="CancelTeamInvitation", guards=[requires_team_admin], path=urls.TEAM_INVITATION_CANCEL)
    async def cancel_invitation(
        self,
        request: HTMXRequest,
        team_invitations_service: TeamInvitationService,
        team_id: UUID = Parameter(title="Team ID", description="The team to update."),
        invitation_id: UUID = Parameter(title="Invitation ID", description="The invitation to cancel."),
    ) -> None | HTMXTemplate | Response:
        invitation = await team_invitations_service.get(invitation_id)
        if invitation.team_id != team_id:
            raise PermissionDeniedException(detail="Insufficient permissions to cancel invitation.")
        _ = await team_invitations_service.delete(invitation_id)
        if request.htmx:
            invitations, _ = await team_invitations_service.list_and_count(m.TeamInvitation.team_id == team_id)
            context = build_team_invitations_table(invitations)
            context["team_id"] = str(team_id)
            return HTMXTemplate(template_name="partials/team_invitations_table.jinja", context=context)
        if self._wants_html(request):
            return Response(
                content=None,
                status_code=HTTP_303_SEE_OTHER,
                headers={"Location": f"/teams/{team_id}/invitations"},
            )
        return None

    @post(operation_id="AcceptTeamInvitation", path=urls.TEAM_INVITATION_ACCEPT)
    async def accept_invitation(
        self,
        request: HTMXRequest,
        team_invitations_service: TeamInvitationService,
        team_members_service: TeamMemberService,
        teams_service: TeamService,
        team_id: UUID = Parameter(title="Team ID", description="The team to accept an invitation for."),
        invitation_id: UUID = Parameter(title="Invitation ID", description="The invitation to accept."),
        current_user: m.User | None = None,
    ) -> TeamInvitation | HTMXTemplate | Response:
        invitation = await team_invitations_service.get(invitation_id)
        if invitation.team_id != team_id:
            raise PermissionDeniedException(detail="Insufficient permissions to respond to invitation.")
        if not current_user or invitation.email.lower() != current_user.email.lower():
            raise PermissionDeniedException(detail="Insufficient permissions to respond to invitation.")
        if invitation.is_accepted:
            msg = "Invitation already accepted."
            return self._panel_or_feedback_response(request, msg, invitation=invitation)

        members, _ = await team_members_service.list_and_count(
            m.TeamMember.team_id == team_id,
            m.TeamMember.user_id == current_user.id,
        )
        if members:
            msg = "User is already a member of the team."
            return self._panel_or_feedback_response(request, msg, invitation=invitation)

        _ = await team_members_service.create(
            {"team_id": team_id, "user_id": current_user.id, "role": invitation.role},
        )
        updated = await team_invitations_service.update(item_id=invitation_id, data={"is_accepted": True})
        if request.htmx and "notifications-shell" in request.headers.get("HX-Target", ""):
            return await self._notifications_response(request, team_invitations_service, teams_service)
        if request.htmx:
            return self._panel_response(invitation=updated, status="accepted")
        if self._wants_html(request):
            return Response(
                content=None,
                status_code=HTTP_303_SEE_OTHER,
                headers={"Location": f"/invitations/{invitation_id}?status=accepted"},
            )
        return team_invitations_service.to_schema(schema_type=TeamInvitation, data=updated)

    @post(operation_id="DeclineTeamInvitation", path=urls.TEAM_INVITATION_DECLINE)
    async def decline_invitation(
        self,
        request: HTMXRequest,
        team_invitations_service: TeamInvitationService,
        teams_service: TeamService,
        team_id: UUID = Parameter(title="Team ID", description="The team to decline an invitation for."),
        invitation_id: UUID = Parameter(title="Invitation ID", description="The invitation to decline."),
        current_user: m.User | None = None,
    ) -> None | HTMXTemplate | Response:
        invitation = await team_invitations_service.get(invitation_id)
        if invitation.team_id != team_id:
            raise PermissionDeniedException(detail="Insufficient permissions to respond to invitation.")
        if not current_user or invitation.email.lower() != current_user.email.lower():
            raise PermissionDeniedException(detail="Insufficient permissions to respond to invitation.")
        if invitation.is_accepted:
            msg = "Invitation already accepted."
            response = self._panel_or_feedback_response(request, msg, invitation=invitation)
        else:
            _ = await team_invitations_service.delete(invitation_id)
            if request.htmx and "notifications-shell" in request.headers.get("HX-Target", ""):
                response = await self._notifications_response(request, team_invitations_service, teams_service)
            elif request.htmx:
                response = self._panel_response(status="declined")
            elif self._wants_html(request):
                response = Response(
                    content=None,
                    status_code=HTTP_303_SEE_OTHER,
                    headers={"Location": f"/invitations/{invitation_id}?status=declined"},
                )
            else:
                response = Response({"message": "Invitation declined."})
        return response
