from __future__ import annotations

from typing import TYPE_CHECKING

from app.db import models as m
from app.domain.sanitize.sanitize_base import clean_text

if TYPE_CHECKING:
    from app.domain.teams.services import TeamInvitationService, TeamService


async def build_notification_context(
    *,
    email: str,
    team_invitations_service: TeamInvitationService,
    teams_service: TeamService,
) -> dict[str, object]:
    invitations, _ = await team_invitations_service.list_and_count(
        m.TeamInvitation.email == email,
        m.TeamInvitation.is_accepted == False,  # noqa: E712
    )
    team_ids = {invitation.team_id for invitation in invitations}
    teams_by_id: dict[str, str] = {}
    if team_ids:
        teams, _ = await teams_service.list_and_count(m.Team.id.in_(team_ids))
        teams_by_id = {str(team.id): clean_text(team.name) or "Team" for team in teams}

    notifications: list[dict[str, object]] = []
    for invitation in invitations:
        team_id = str(invitation.team_id)
        role_value = getattr(invitation.role, "value", invitation.role)
        role_text = clean_text(str(role_value)) or "Member"
        team_name = teams_by_id.get(team_id, "Team")
        notifications.append(
            {
                "id": str(invitation.id),
                "type": "invitation",
                "status": "pending",
                "title": "Team invitation",
                "description": f"{team_name} invited you as {role_text}.",
                "team_id": team_id,
                "invitation_id": str(invitation.id),
                "accept_url": f"/api/teams/{team_id}/invitations/{invitation.id}/accept",
                "decline_url": f"/api/teams/{team_id}/invitations/{invitation.id}/decline",
            },
        )

    return {
        "notifications": notifications,
        "notification_count": len(notifications),
    }
