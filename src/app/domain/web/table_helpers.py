from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.db import models as m

from app.domain.sanitize.sanitize_base import clean_text


def _clean_text(value: str | None) -> str:
    return clean_text(value)


def build_users_table(
    users: Sequence[m.User],
    *,
    query: str | None = None,
    page: int = 1,
    page_size: int = 20,
    total: int | None = None,
    filter_by: str | None = None,
    sort: str | None = None,
    order: str = "asc",
) -> dict[str, object]:
    cleaned_query = _clean_text(query)
    page_users = list(users)
    total_value = len(page_users) if total is None else total
    next_page = page + 1 if total_value > page * page_size else None
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
    total_pages = (total_value + page_size - 1) // page_size if total_value else 0
    return {
        "headers": headers,
        "rows": rows,
        "next_page": next_page,
        "query": cleaned_query,
        "total": total_value,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": next_page is not None,
        "has_prev": page > 1,
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
    total: int | None = None,
    filter_by: str | None = None,
    sort: str | None = None,
    order: str = "asc",
) -> dict[str, object]:
    cleaned_query = _clean_text(query)
    page_teams = list(teams)
    total_value = len(page_teams) if total is None else total
    next_page = page + 1 if total_value > page * page_size else None
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
    total_pages = (total_value + page_size - 1) // page_size if total_value else 0
    return {
        "headers": headers,
        "rows": rows,
        "next_page": next_page,
        "query": cleaned_query,
        "total": total_value,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": next_page is not None,
        "has_prev": page > 1,
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
    total: int | None = None,
) -> dict[str, object]:
    cleaned_query = _clean_text(query)
    page_members = list(members)
    total_value = len(page_members) if total is None else total
    next_page = page + 1 if total_value > page * page_size else None
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
    total_pages = (total_value + page_size - 1) // page_size if total_value else 0
    return {
        "headers": headers,
        "rows": rows,
        "query": cleaned_query,
        "total": total_value,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": next_page is not None,
        "has_prev": page > 1,
        "next_page": next_page,
    }


def build_team_invitations_table(
    invitations: Sequence[m.TeamInvitation],
    *,
    query: str | None = None,
    page: int = 1,
    page_size: int = 20,
    total: int | None = None,
) -> dict[str, object]:
    cleaned_query = _clean_text(query)
    page_invitations = list(invitations)
    total_value = len(page_invitations) if total is None else total
    next_page = page + 1 if total_value > page * page_size else None
    rows = []
    for invite in page_invitations:
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
    total_pages = (total_value + page_size - 1) // page_size if total_value else 0
    return {
        "headers": headers,
        "rows": rows,
        "query": cleaned_query,
        "total": total_value,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": next_page is not None,
        "has_prev": page > 1,
        "next_page": next_page,
    }
