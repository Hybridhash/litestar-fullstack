"""Team domain filtering and sorting helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import false, func, or_, select

from app.db import models as m
from app.domain.sanitize.sanitize_base import clean_text, escape_like

ALLOWED_TEAM_FILTERS = {"all", "name", "status", "members", "slug"}
ALLOWED_TEAM_SORT = {"name", "status", "members", "slug"}
ALLOWED_ORDER = {"asc", "desc"}


def _normalize_choice(value: str | None, allowed: set[str], default: str) -> str:
    if not value:
        return default
    lowered = value.lower()
    return lowered if lowered in allowed else default


def normalize_team_query_params(
    query: str | None,
    filter_by: str | None,
    sort: str | None,
    order: str,
) -> tuple[str, str, str, str]:
    cleaned_query = clean_text(query)
    filter_by = _normalize_choice(filter_by, ALLOWED_TEAM_FILTERS, "all")
    if not sort:
        sort = filter_by if filter_by in ALLOWED_TEAM_SORT else "name"
    sort = _normalize_choice(sort, ALLOWED_TEAM_SORT, "name")
    order = _normalize_choice(order, ALLOWED_ORDER, "asc")
    return cleaned_query, filter_by, sort, order


def team_members_count_subquery() -> Any:
    return (
        select(func.count(m.TeamMember.id)).where(m.TeamMember.team_id == m.Team.id).correlate(m.Team).scalar_subquery()
    )


class TeamFilterBuilder:
    """Build SQLAlchemy filters for team queries."""

    def __init__(self, query: str, filter_by: str, members_count: Any) -> None:
        self.query = query
        self.filter_by = filter_by
        self.members_count = members_count

    def build(self) -> list[Any]:
        if not self.query:
            return []

        like_query = f"%{escape_like(self.query)}%"
        query_lower = self.query.lower()
        status_value = self._parse_status(query_lower)

        if self.filter_by == "name":
            return [m.Team.name.ilike(like_query, escape="\\")]
        if self.filter_by == "slug":
            return [m.Team.slug.ilike(like_query, escape="\\")]
        if self.filter_by == "status":
            return self._status_filters(status_value)
        if self.filter_by == "members":
            return self._members_filters(query_lower)

        return self._combined_filters(like_query, status_value, query_lower)

    @staticmethod
    def _parse_status(query_lower: str) -> bool | str:
        if "inactive" in query_lower:
            return False
        if "active" in query_lower:
            return True
        return "none"

    @staticmethod
    def _status_filters(status_value: bool | str) -> list[Any]:
        if status_value is True or status_value is False:
            return [m.Team.is_active.is_(status_value)]
        return [false()]

    def _members_filters(self, query_lower: str) -> list[Any]:
        if query_lower.isdigit():
            return [self.members_count == int(query_lower)]
        return [false()]

    def _combined_filters(self, like_query: str, status_value: bool | str, query_lower: str) -> list[Any]:
        or_conditions = [
            m.Team.name.ilike(like_query, escape="\\"),
            m.Team.slug.ilike(like_query, escape="\\"),
        ]
        if status_value is True or status_value is False:
            or_conditions.append(m.Team.is_active.is_(status_value))
        if query_lower.isdigit():
            or_conditions.append(self.members_count == int(query_lower))
        return [or_(*or_conditions)]


class TeamSortBuilder:
    """Build SQLAlchemy order_by for team queries."""

    def __init__(self, sort: str, order: str, members_count: Any) -> None:
        self.sort = sort
        self.order = order
        self.members_count = members_count

    def build(self) -> Any:
        order_by_map = {
            "name": m.Team.name,
            "slug": m.Team.slug,
            "status": m.Team.is_active,
            "members": self.members_count,
        }
        order_by = order_by_map.get(self.sort, m.Team.name)
        if self.order == "desc":
            return order_by.desc()
        return order_by.asc()


class TeamMemberFilterBuilder:
    """Build SQLAlchemy filters for team member queries."""

    def __init__(self, team_id: Any, query: str | None) -> None:
        self.team_id = team_id
        self.query = clean_text(query)

    def build(self) -> tuple[list[Any], str]:
        filters: list[Any] = [m.TeamMember.team_id == self.team_id]
        if not self.query:
            return filters, ""

        like_query = f"%{escape_like(self.query)}%"
        filters.append(
            or_(
                m.TeamMember.user.has(m.User.name.ilike(like_query, escape="\\")),
                m.TeamMember.user.has(m.User.email.ilike(like_query, escape="\\")),
                m.TeamMember.role.ilike(like_query, escape="\\"),
            ),
        )
        return filters, self.query


class TeamInvitationFilterBuilder:
    """Build SQLAlchemy filters for team invitation queries."""

    def __init__(self, team_id: Any, query: str | None) -> None:
        self.team_id = team_id
        self.query = clean_text(query)

    def build(self) -> tuple[list[Any], str]:
        filters: list[Any] = [m.TeamInvitation.team_id == self.team_id]
        if not self.query:
            return filters, ""

        like_query = f"%{escape_like(self.query)}%"
        filters.append(
            or_(
                m.TeamInvitation.email.ilike(like_query, escape="\\"),
                m.TeamInvitation.role.ilike(like_query, escape="\\"),
            ),
        )
        return filters, self.query
