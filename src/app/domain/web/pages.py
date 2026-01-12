from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Controller, get
from litestar.di import Provide
from litestar.enums import MediaType
from litestar.plugins.htmx import HTMXRequest
from litestar.response import Template
from litestar.status_codes import HTTP_200_OK
from sqlalchemy import select
from sqlalchemy.sql.elements import ColumnElement

from app.db import models as m
from app.db.models.team_member import TeamMember as TeamMemberModel
from app.domain.accounts.deps import provide_users_service
from app.domain.accounts.guards import requires_active_user, requires_superuser
from app.domain.teams.services import TeamService
from app.domain.web.table_helpers import build_teams_table, build_users_table
from app.lib.deps import create_service_provider

if TYPE_CHECKING:
    from app.domain.accounts.services import UserService


class SiteController(Controller):
    """Server-rendered page routes."""

    include_in_schema = False
    dependencies = {
        "users_service": Provide(provide_users_service),
        "teams_service": Provide(create_service_provider(TeamService)),
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

    @get(path="/profile", operation_id="WebProfile", guards=[requires_active_user], status_code=HTTP_200_OK)
    async def profile_page(self, request: HTMXRequest) -> Template:
        return Template(template_name="site/profile.jinja", context={"user": request.user}, media_type=MediaType.HTML)

    @get(path="/settings", operation_id="WebSettings", guards=[requires_active_user], status_code=HTTP_200_OK)
    async def settings_page(self) -> Template:
        return Template(template_name="site/settings.jinja", context={"theme": "litestar"}, media_type=MediaType.HTML)
