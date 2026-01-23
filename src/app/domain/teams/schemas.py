from __future__ import annotations

from uuid import UUID  # noqa: TC003

import msgspec

from app.db.models.team_roles import TeamRoles
from app.lib.schema import CamelizedBaseStruct


class TeamTag(CamelizedBaseStruct):
    id: UUID
    slug: str
    name: str


class TeamMember(CamelizedBaseStruct):
    id: UUID
    user_id: UUID
    email: str
    name: str | None = None
    role: TeamRoles | None = TeamRoles.MEMBER
    is_owner: bool | None = False


class Team(CamelizedBaseStruct):
    id: UUID
    name: str
    description: str | None = None
    members: list[TeamMember] = []
    tags: list[TeamTag] = []


class TeamInvitation(CamelizedBaseStruct):
    id: UUID
    team_id: UUID
    email: str
    role: TeamRoles | None = TeamRoles.MEMBER
    is_accepted: bool = False
    invited_by_email: str | None = None


class TeamCreate(CamelizedBaseStruct):
    name: str
    description: str | None = None
    tags: list[str] = []


class TeamUpdate(CamelizedBaseStruct, omit_defaults=True):
    name: str | None | msgspec.UnsetType = msgspec.UNSET
    description: str | None | msgspec.UnsetType = msgspec.UNSET
    tags: list[str] | None | msgspec.UnsetType = msgspec.UNSET


class TeamMemberModify(CamelizedBaseStruct):
    """Team Member Modify."""

    user_name: str
    role: TeamRoles | None = None


class TeamMemberUpdate(CamelizedBaseStruct):
    """Team Member Update."""

    role: TeamRoles


class TeamInvitationCreate(CamelizedBaseStruct):
    """Team Invitation Create."""

    email: str
    role: TeamRoles | None = TeamRoles.MEMBER
