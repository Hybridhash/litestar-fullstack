"""User Account Controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from advanced_alchemy.service import FilterTypeT  # noqa: TC002
from litestar import Controller, delete, get, patch, post
from litestar.enums import RequestEncodingType
from litestar.params import Body
from litestar.plugins.htmx import HTMXRequest, HTMXTemplate
from litestar.status_codes import HTTP_200_OK
from sqlalchemy import select

from app.db import models as m
from app.db.models.team_member import TeamMember as TeamMemberModel
from app.domain.accounts.guards import requires_active_user
from app.domain.teams import urls
from app.domain.teams.guards import requires_team_admin, requires_team_membership
from app.domain.teams.schemas import Team, TeamCreate, TeamUpdate
from app.domain.teams.services import TeamService
from app.domain.web.table_helpers import build_teams_table
from app.lib.deps import create_service_dependencies

if TYPE_CHECKING:
    from advanced_alchemy.service.pagination import OffsetPagination
    from litestar.params import Dependency, Parameter


class TeamController(Controller):
    """Teams."""

    tags = ["Teams"]
    dependencies = create_service_dependencies(
        TeamService,
        key="teams_service",
        load=[m.Team.tags, m.Team.members],
        filters={"id_filter": UUID},
    )

    guards = [requires_active_user]

    @get(component="team/list", operation_id="ListTeams", path=urls.TEAM_LIST)
    async def list_teams(
        self,
        request: HTMXRequest,
        teams_service: TeamService,
        current_user: m.User,
        filters: Annotated[list[FilterTypeT], Dependency(skip_validation=True)],
        q: str | None = None,
        page: int = 1,
        filter_by: str | None = None,
        sort: str | None = None,
        order: str = "asc",
    ) -> OffsetPagination[Team] | HTMXTemplate:
        """List teams that your account can access.."""
        membership_filters: list[FilterTypeT] = []
        if not teams_service.can_view_all(current_user):
            membership_filters.append(
                m.Team.id.in_(select(TeamMemberModel.team_id).where(TeamMemberModel.user_id == current_user.id)),  # type: ignore[arg-type]
            )
        if request.htmx or request.headers.get("HX-Request", "").lower() == "true":
            results, _ = await teams_service.list_and_count(*membership_filters)
            context = build_teams_table(
                results,
                query=q,
                page=page,
                filter_by=filter_by,
                sort=sort,
                order=order,
            )
            return HTMXTemplate(template_name="partials/teams_table.jinja", context=context)
        results, total = await teams_service.list_and_count(*filters, *membership_filters)
        return teams_service.to_schema(data=results, total=total, schema_type=Team, filters=filters)

    @post(operation_id="CreateTeam", path=urls.TEAM_CREATE)
    async def create_team(
        self,
        request: HTMXRequest,
        teams_service: TeamService,
        current_user: m.User,
        data: Annotated[TeamCreate, Body(title="Create Team", media_type=RequestEncodingType.URL_ENCODED)],
    ) -> Team | HTMXTemplate:
        """Create a new team."""
        obj = data.to_dict()
        obj.update({"owner_id": current_user.id, "owner": current_user})
        db_obj = await teams_service.create(obj)
        if request.htmx:
            results, _ = await teams_service.list_and_count()
            context = build_teams_table(results)
            return HTMXTemplate(template_name="partials/teams_table.jinja", context=context)
        return teams_service.to_schema(schema_type=Team, data=db_obj)

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
    ) -> None | HTMXTemplate:
        """Delete a team."""
        _ = await teams_service.delete(team_id)
        if request.htmx:
            results, _ = await teams_service.list_and_count()
            context = build_teams_table(results)
            return HTMXTemplate(template_name="partials/teams_table.jinja", context=context)
        return None
