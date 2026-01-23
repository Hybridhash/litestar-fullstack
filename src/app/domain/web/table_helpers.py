from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from app.db import models as m

from app.domain.sanitize.sanitize_base import clean_text

TableModel = TypeVar("TableModel")

ALLOWED_USER_FILTERS = {"all", "name", "email", "role", "status"}
ALLOWED_USER_SORT = {"name", "email", "status", "role"}
ALLOWED_TEAM_FILTERS = {"all", "name", "status", "members", "slug"}
ALLOWED_TEAM_SORT = {"name", "status", "members", "slug"}
ALLOWED_ORDER = {"asc", "desc"}


def _clean_text(value: str | None) -> str:
    return clean_text(value)


def _normalize_choice(value: str | None, allowed: Iterable[str], default: str) -> str:
    if not value:
        return default
    lowered = value.lower()
    return lowered if lowered in allowed else default


def _paginate(items: Sequence[TableModel], page: int, page_size: int) -> tuple[list[TableModel], int | None]:
    items_list = list(items)
    offset = max(page - 1, 0) * page_size
    page_items = items_list[offset : offset + page_size]
    next_page = page + 1 if len(items_list) > offset + page_size else None
    return page_items, next_page


def build_users_table(
    users: Sequence[m.User],
    *,
    query: str | None = None,
    page: int = 1,
    page_size: int = 20,
    filter_by: str | None = None,
    sort: str | None = None,
    order: str = "asc",
) -> dict[str, object]:
    cleaned_query = _clean_text(query)
    filter_by = _normalize_choice(filter_by, ALLOWED_USER_FILTERS, "all")
    if cleaned_query:
        query_lower = cleaned_query.lower()

        def matches_query(user: m.User) -> bool:
            name_value = (user.name or "").lower()
            email_value = user.email.lower()
            role_value = (user.roles[0].role.name if user.roles else "member").lower()
            status_value = "active" if user.is_active else "inactive"
            if filter_by == "name":
                return query_lower in name_value
            if filter_by == "email":
                return query_lower in email_value
            if filter_by == "role":
                return query_lower in role_value
            if filter_by == "status":
                return query_lower in status_value
            return (
                query_lower in name_value
                or query_lower in email_value
                or query_lower in role_value
                or query_lower in status_value
            )

        users = [user for user in users if matches_query(user)]
    if not sort:
        sort = filter_by if filter_by in ALLOWED_USER_SORT else "name"
    sort = _normalize_choice(sort, ALLOWED_USER_SORT, "name")
    order = _normalize_choice(order, ALLOWED_ORDER, "asc")
    sort_key_map = {
        "name": lambda user: user.name or "",
        "email": lambda user: user.email,
        "status": lambda user: user.is_active,
        "role": lambda user: user.roles[0].role.name if user.roles else "",
    }
    sort_key = sort_key_map.get(sort, sort_key_map["name"])
    users = sorted(users, key=sort_key, reverse=order == "desc")
    page_users, next_page = _paginate(users, page, page_size)
    rows = []
    for user in page_users:
        safe_name = _clean_text(user.name) or "—"
        safe_email = _clean_text(user.email)
        safe_role = _clean_text(user.roles[0].role.name) if user.roles else "Member"
        rows.append(
            {
                "name": safe_name,
                "email": safe_email,
                "status": "Active" if user.is_active else "Inactive",
                "role": safe_role,
                "id": str(user.id),
            },
        )
    headers = ["Name", "Email", "Status", "Role", "Actions"]
    return {
        "headers": headers,
        "rows": rows,
        "next_page": next_page,
        "query": cleaned_query,
        "total": len(users),
        "filter_by": filter_by,
        "sort": sort,
        "order": order,
    }


def build_teams_table(
    teams: Sequence[m.Team],
    *,
    query: str | None = None,
    page: int = 1,
    page_size: int = 20,
    filter_by: str | None = None,
    sort: str | None = None,
    order: str = "asc",
) -> dict[str, object]:
    cleaned_query = _clean_text(query)
    filter_by = _normalize_choice(filter_by, ALLOWED_TEAM_FILTERS, "all")
    if cleaned_query:
        query_lower = cleaned_query.lower()

        def matches_query(team: m.Team) -> bool:
            name_value = team.name.lower()
            slug_value = team.slug.lower()
            status_value = "active" if getattr(team, "is_active", False) else "inactive"
            members_count = len(team.members) if hasattr(team, "members") else 0
            if filter_by == "name":
                return query_lower in name_value
            if filter_by == "slug":
                return query_lower in slug_value
            if filter_by == "status":
                return query_lower in status_value
            if filter_by == "members":
                if query_lower.isdigit():
                    return int(query_lower) == members_count
                return query_lower in str(members_count)
            return (
                query_lower in name_value
                or query_lower in slug_value
                or query_lower in status_value
                or query_lower in str(members_count)
            )

        teams = [team for team in teams if matches_query(team)]
    if not sort:
        sort = filter_by if filter_by in ALLOWED_TEAM_SORT else "name"
    sort = _normalize_choice(sort, ALLOWED_TEAM_SORT, "name")
    order = _normalize_choice(order, ALLOWED_ORDER, "asc")
    sort_key_map = {
        "name": lambda team: team.name,
        "status": lambda team: team.is_active,
        "members": lambda team: len(team.members) if hasattr(team, "members") else 0,
        "slug": lambda team: team.slug,
    }
    sort_key = sort_key_map.get(sort, sort_key_map["name"])
    teams = sorted(teams, key=sort_key, reverse=order == "desc")
    page_teams, next_page = _paginate(teams, page, page_size)
    rows = []
    for team in page_teams:
        safe_name = _clean_text(team.name)
        safe_slug = _clean_text(team.slug) or "—"
        members_count = str(len(team.members)) if hasattr(team, "members") else "0"
        rows.append(
            {
                "name": safe_name,
                "slug": safe_slug,
                "members": members_count,
                "status": "Active" if getattr(team, "is_active", False) else "Inactive",
                "id": str(team.id),
            },
        )
    headers = ["Name", "Slug", "Members", "Status", "Actions"]
    return {
        "headers": headers,
        "rows": rows,
        "next_page": next_page,
        "query": cleaned_query,
        "total": len(teams),
        "filter_by": filter_by,
        "sort": sort,
        "order": order,
    }


def build_team_members_table(
    members: Sequence[m.TeamMember],
    *,
    query: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, object]:
    cleaned_query = _clean_text(query)
    if cleaned_query:
        query_lower = cleaned_query.lower()

        def matches_query(member: m.TeamMember) -> bool:
            user = getattr(member, "user", None)
            name_value = (getattr(user, "name", "") or "").lower()
            email_value = (getattr(user, "email", "") or getattr(member, "email", "") or "").lower()
            role_value = (getattr(member, "role", "") or "").lower()
            return query_lower in name_value or query_lower in email_value or query_lower in role_value

        members = [member for member in members if matches_query(member)]

    page_members, next_page = _paginate(list(members), page, page_size)
    rows = []
    for member in page_members:
        user = getattr(member, "user", None)
        safe_name = _clean_text(getattr(user, "name", None)) or "—"
        safe_email = _clean_text(getattr(user, "email", None) or getattr(member, "email", None))
        role_value = getattr(member, "role", None)
        role_text = getattr(role_value, "value", role_value)
        safe_role = _clean_text(role_text) or "Member"
        rows.append(
            {
                "name": safe_name,
                "email": safe_email,
                "role": safe_role,
                "id": str(member.id),
                "user_id": str(getattr(member, "user_id", "")),
                "is_owner": bool(getattr(member, "is_owner", False)),
            },
        )
    headers = ["Name", "Email", "Role", "Actions"]
    return {
        "headers": headers,
        "rows": rows,
        "query": cleaned_query,
        "total": len(members),
        "next_page": next_page,
    }


def build_team_invitations_table(
    invitations: Sequence[m.TeamInvitation],
    *,
    query: str | None = None,
) -> dict[str, object]:
    cleaned_query = _clean_text(query)
    if cleaned_query:
        query_lower = cleaned_query.lower()

        def matches_query(invite: m.TeamInvitation) -> bool:
            email_value = (getattr(invite, "email", "") or "").lower()
            role_value = (getattr(invite, "role", "") or "").lower()
            return query_lower in email_value or query_lower in role_value

        invitations = [invite for invite in invitations if matches_query(invite)]

    rows = []
    for invite in invitations:
        role_value = getattr(invite, "role", None)
        role_text = getattr(role_value, "value", role_value)
        safe_role = _clean_text(role_text) or "Member"
        rows.append(
            {
                "email": _clean_text(invite.email),
                "role": safe_role,
                "status": "Accepted" if invite.is_accepted else "Pending",
                "id": str(invite.id),
            },
        )
    headers = ["Email", "Role", "Status", "Actions"]
    return {
        "headers": headers,
        "rows": rows,
        "query": cleaned_query,
        "total": len(invitations),
    }
