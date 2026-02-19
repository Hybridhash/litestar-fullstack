"""User Account Controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

from advanced_alchemy.filters import FilterTypes, LimitOffset
from litestar import Controller, delete, get, patch, post
from litestar.enums import RequestEncodingType
from litestar.params import Body
from litestar.status_codes import HTTP_200_OK
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import models as m
from app.db.models.team_member import TeamMember as TeamMemberModel
from app.domain.accounts.guards import requires_active_user
from app.domain.teams import urls
from app.domain.teams.filters import (
    TeamFilterBuilder,
    TeamSortBuilder,
    normalize_team_query_params,
    team_members_count_subquery,
)
from app.domain.teams.guards import requires_team_admin, requires_team_membership
from app.domain.teams.schemas import Team, TeamCreate, TeamUpdate
from app.domain.teams.services import TeamService
from app.domain.web.table_helpers import build_teams_table
from app.lib.deps import create_service_dependencies
from app.lib.response_handler import ResponseHandler

if TYPE_CHECKING:
    from advanced_alchemy.service.pagination import OffsetPagination
    from litestar.params import Dependency, Parameter
    from litestar.plugins.htmx import HTMXRequest


class TeamController(Controller):
    """Teams."""

    _DEFAULT_PAGE_SIZE = 20
    _MAX_PAGE_SIZE = 100
    tags = ["Teams"]
    dependencies = create_service_dependencies(
        TeamService,
        key="teams_service",
        load=[selectinload(m.Team.tags), selectinload(m.Team.members)],
        filters={"id_filter": UUID},
    )

    guards = [requires_active_user]

    @staticmethod
    def _membership_filters(teams_service: TeamService, user: m.User) -> list[Any]:
        membership_filters: list[Any] = []
        if not teams_service.can_view_all(user):
            membership_filters.append(
                m.Team.id.in_(select(TeamMemberModel.team_id).where(TeamMemberModel.user_id == user.id)),
            )
        return membership_filters

    async def _build_teams_table_response(
        self,
        handler: ResponseHandler,
        teams_service: TeamService,
        user: m.User,
        status_code: int = HTTP_200_OK,
    ) -> Any:
        """Build HTMX teams table response (used after create/delete)."""
        membership_filters = self._membership_filters(teams_service, user)
        results, total = await teams_service.list_and_count(
            *membership_filters,
            LimitOffset(limit=self._DEFAULT_PAGE_SIZE, offset=0),
            order_by=[m.Team.name.asc()],
        )
        context = build_teams_table(
            results,
            page=1,
            page_size=self._DEFAULT_PAGE_SIZE,
            total=total,
        )
        return handler.respond(
            htmx_template="partials/teams_table.jinja",
            htmx_context=context,
            status_code=status_code,
        )

    @get(component="team/list", operation_id="ListTeams", path=urls.TEAM_LIST)
    async def list_teams(
        self,
        request: HTMXRequest,
        teams_service: TeamService,
        current_user: m.User,
        filters: Annotated[list[FilterTypes], Dependency(skip_validation=True)],
        q: str | None = None,
        page: int = 1,
        page_size: int = _DEFAULT_PAGE_SIZE,
        filter_by: str | None = None,
        sort: str | None = None,
        order: str = "asc",
    ) -> OffsetPagination[Team] | Any:
        """List teams that your account can access.."""
        handler = ResponseHandler(request)
        membership_filters = self._membership_filters(teams_service, current_user)
        if handler.is_htmx():
            cleaned_query, filter_by, sort, order = normalize_team_query_params(q, filter_by, sort, order)
            safe_page_size = max(1, min(page_size, self._MAX_PAGE_SIZE))
            offset = max(page - 1, 0) * safe_page_size
            members_count = team_members_count_subquery()
            statement_filters = TeamFilterBuilder(cleaned_query, filter_by, members_count).build()
            order_by = TeamSortBuilder(sort, order, members_count).build()
            results, total = await teams_service.list_and_count(
                *membership_filters,
                *statement_filters,
                LimitOffset(limit=safe_page_size, offset=offset),
                order_by=[order_by] if order_by is not None else None,
            )
            context = build_teams_table(
                results,
                query=cleaned_query,
                page=page,
                page_size=safe_page_size,
                total=total,
                filter_by=filter_by,
                sort=sort,
                order=order,
            )
            return handler.respond(
                htmx_template="partials/teams_table.jinja",
                htmx_context=context,
            )
        results, total = await teams_service.list_and_count(*filters, *membership_filters)
        return handler.respond(
            data=results,
            json_schema_type=Team,
            service=teams_service,
            schema_kwargs={"total": total, "filters": filters},
        )

    @post(operation_id="CreateTeam", path=urls.TEAM_CREATE)
    async def create_team(
        self,
        request: HTMXRequest,
        teams_service: TeamService,
        current_user: m.User,
        data: Annotated[TeamCreate, Body(title="Create Team", media_type=RequestEncodingType.URL_ENCODED)],
    ) -> Team | Any:
        """Create a new team."""
        obj = data.to_dict()
        obj.update({"owner_id": current_user.id, "owner": current_user})
        db_obj = await teams_service.create(obj)
        handler = ResponseHandler(request)
        if handler.is_htmx():
            return await self._build_teams_table_response(handler, teams_service, current_user)
        return handler.respond(
            data=db_obj,
            json_schema_type=Team,
            service=teams_service,
        )

    @get(operation_id="GetTeam", guards=[requires_team_membership], path=urls.TEAM_DETAIL)
    async def get_team(
        self,
        teams_service: TeamService,
        team_id: Annotated[UUID, Parameter(title="Team ID", description="The team to retrieve.")],
    ) -> Team:
        """Get details about a team."""
        db_obj = await teams_service.get(team_id)
        return teams_service.to_schema(schema_type=Team, data=db_obj)

    @patch(operation_id="UpdateTeam", guards=[requires_team_admin], path=urls.TEAM_UPDATE)
    async def update_team(
        self,
        data: TeamUpdate,
        teams_service: TeamService,
        team_id: Annotated[UUID, Parameter(title="Team ID", description="The team to update.")],
    ) -> Team:
        """Update a migration team."""
        db_obj = await teams_service.update(
            item_id=team_id,
            data=data.to_dict(),
        )
        return teams_service.to_schema(schema_type=Team, data=db_obj)

    @delete(operation_id="DeleteTeam", guards=[requires_team_admin], path=urls.TEAM_DELETE, status_code=HTTP_200_OK)
    async def delete_team(
        self,
        request: HTMXRequest,
        teams_service: TeamService,
        team_id: Annotated[UUID, Parameter(title="Team ID", description="The team to delete.")],
    ) -> None | Any:
        """Delete a team."""
        _ = await teams_service.delete(team_id)
        handler = ResponseHandler(request)
        if handler.is_htmx():
            return await self._build_teams_table_response(handler, teams_service, request.user, HTTP_200_OK)
        return None
