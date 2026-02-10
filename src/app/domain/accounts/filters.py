"""User domain filtering and sorting helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import false, or_, select

from app.config import constants
from app.db import models as m
from app.domain.sanitize.sanitize_base import clean_text, escape_like

ALLOWED_USER_FILTERS = {"all", "name", "email", "role", "status"}
ALLOWED_USER_SORT = {"name", "email", "status", "role"}
ALLOWED_ORDER = {"asc", "desc"}
ROLE_ALIASES = {
    "member": ("application-access", "application access"),
    "members": ("application-access", "application access"),
}


def _normalize_choice(value: str | None, allowed: set[str], default: str) -> str:
    if not value:
        return default
    lowered = value.lower()
    return lowered if lowered in allowed else default


def normalize_user_query_params(
    query: str | None,
    filter_by: str | None,
    sort: str | None,
    order: str,
) -> tuple[str, str, str, str]:
    cleaned_query = clean_text(query)
    filter_by = _normalize_choice(filter_by, ALLOWED_USER_FILTERS, "all")
    if not sort:
        sort = filter_by if filter_by in ALLOWED_USER_SORT else "name"
    sort = _normalize_choice(sort, ALLOWED_USER_SORT, "name")
    order = _normalize_choice(order, ALLOWED_ORDER, "asc")
    return cleaned_query, filter_by, sort, order


class UserFilterBuilder:
    """Build SQLAlchemy filters for user queries."""

    def __init__(self, query: str, filter_by: str) -> None:
        self.query = query
        self.filter_by = filter_by

    def build(self) -> list[Any]:
        if not self.query:
            return []

        like_query = f"%{escape_like(self.query)}%"
        query_lower = self.query.lower()
        status_value = self._parse_status(query_lower)
        role_match = self._build_role_match(like_query, query_lower)

        if self.filter_by == "name":
            return [m.User.name.ilike(like_query, escape="\\")]
        if self.filter_by == "email":
            return [m.User.email.ilike(like_query, escape="\\")]
        if self.filter_by == "role":
            return [role_match]
        if self.filter_by == "status":
            return self._status_filters(status_value)

        return self._combined_filters(like_query, status_value, role_match)

    @staticmethod
    def _parse_status(query_lower: str) -> bool | str:
        if "inactive" in query_lower:
            return False
        if "active" in query_lower:
            return True
        return "none"

    def _build_role_match(self, like_query: str, query_lower: str) -> Any:
        alias_terms = ROLE_ALIASES.get(query_lower, ())
        if query_lower in {"member", "members"}:
            default_role = constants.DEFAULT_USER_ROLE
            slug_variant = default_role.lower().replace(" ", "-")
            alias_terms = tuple(
                {
                    *alias_terms,
                    default_role,
                    default_role.lower(),
                    slug_variant,
                    slug_variant.replace("-", "_"),
                },
            )

        role_conditions = [
            m.Role.name.ilike(like_query, escape="\\"),
            m.Role.slug.ilike(like_query, escape="\\"),
        ]
        for alias in alias_terms:
            escaped_alias = escape_like(alias)
            role_conditions.append(m.Role.name.ilike(f"%{escaped_alias}%", escape="\\"))
            role_conditions.append(m.Role.slug.ilike(f"%{escaped_alias}%", escape="\\"))

        role_match: Any = m.User.roles.any(m.UserRole.role.has(or_(*role_conditions)))
        if alias_terms:
            role_match = or_(role_match, ~m.User.roles.any())
        return role_match

    @staticmethod
    def _status_filters(status_value: bool | str) -> list[Any]:
        if status_value is True or status_value is False:
            return [m.User.is_active.is_(status_value)]
        return [false()]

    @staticmethod
    def _combined_filters(like_query: str, status_value: bool | str, role_match: Any) -> list[Any]:
        or_conditions = [
            m.User.name.ilike(like_query, escape="\\"),
            m.User.email.ilike(like_query, escape="\\"),
            role_match,
        ]
        if status_value is True or status_value is False:
            or_conditions.append(m.User.is_active.is_(status_value))
        return [or_(*or_conditions)]


class UserSortBuilder:
    """Build SQLAlchemy order_by for user queries."""

    ORDER_BY_MAP = {
        "name": m.User.name,
        "email": m.User.email,
        "status": m.User.is_active,
    }

    def __init__(self, sort: str, order: str) -> None:
        self.sort = sort
        self.order = order

    def build(self) -> Any:
        if self.sort == "role":
            order_by: Any = (
                select(m.Role.name)
                .join(m.UserRole, m.UserRole.role_id == m.Role.id)
                .where(m.UserRole.user_id == m.User.id)
                .order_by(m.Role.name)
                .limit(1)
                .scalar_subquery()
            )
        else:
            order_by = self.ORDER_BY_MAP.get(self.sort, m.User.name)

        if self.order == "desc":
            return order_by.desc()
        return order_by.asc()
