from __future__ import annotations

from datetime import datetime  # noqa: TC003
from uuid import UUID  # noqa: TC003

import msgspec

from app.db.models.team_roles import TeamRoles
from app.lib.schema import CamelizedBaseStruct

__all__ = (
    "AccountLogin",
    "AccountRegister",
    "User",
    "UserCreate",
    "UserProfileUpdate",
    "UserRole",
    "UserRoleAdd",
    "UserRoleRevoke",
    "UserTeam",
    "UserUpdate",
)


class UserTeam(CamelizedBaseStruct):
    """Holds team details for a user.

    This is nested in the User Model for 'team'
    """

    team_id: UUID
    team_name: str
    is_owner: bool = False
    role: TeamRoles = TeamRoles.MEMBER


class UserRole(CamelizedBaseStruct):
    """Holds role details for a user.

    This is nested in the User Model for 'roles'
    """

    role_id: UUID
    role_slug: str
    role_name: str
    assigned_at: datetime


class User(CamelizedBaseStruct):
    """User properties to use for a response."""

    id: UUID
    email: str
    name: str | None = None
    is_active: bool = False
    is_verified: bool = False
    has_password: bool = False
    teams: list[UserTeam] = []
    roles: list[UserRole] = []


class UserCreate(CamelizedBaseStruct):
    email: str
    password: str
    name: str | None = None
    is_active: bool = True
    is_verified: bool = False


class UserUpdate(CamelizedBaseStruct, omit_defaults=True):
    email: str | None | msgspec.UnsetType = msgspec.UNSET
    name: str | None | msgspec.UnsetType = msgspec.UNSET
    is_active: bool | None | msgspec.UnsetType = msgspec.UNSET
    is_verified: bool | None | msgspec.UnsetType = msgspec.UNSET


class UserProfileUpdate(CamelizedBaseStruct, omit_defaults=True):
    email: str | None | msgspec.UnsetType = msgspec.UNSET
    name: str | None | msgspec.UnsetType = msgspec.UNSET


class AccountLogin(CamelizedBaseStruct):
    username: str
    password: str


class AccountRegister(CamelizedBaseStruct):
    email: str
    password: str
    name: str | None = None


class UserRoleAdd(CamelizedBaseStruct):
    """User role add ."""

    user_name: str


class UserRoleRevoke(CamelizedBaseStruct):
    """User role revoke ."""

    user_name: str


class OTPSendRequest(CamelizedBaseStruct):
    """Request to send OTP to a mobile number."""

    mobile: str | list[str]


class OTPCheckRequest(CamelizedBaseStruct):
    """Request to verify an OTP code."""

    mobile: str | list[str]
    code: str | list[str]
