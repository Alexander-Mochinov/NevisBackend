"""Search API routes."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import DatabaseSessionDependency, SettingsDependency
from app.repositories.search import SearchRepository
from app.schemas.search import SearchExplainResponseRead, SearchResultRead
from app.services.embedding_service import create_embedding_provider
from app.services.search import SearchService

router = APIRouter(tags=["search"])


@router.get("/search", response_model=list[SearchResultRead] | SearchExplainResponseRead)
async def search(
    q: Annotated[
        str,
        Query(
            description="Search query",
            examples=["NevisWealth", "address proof", "utlity bil"],
        ),
    ],
    session: DatabaseSessionDependency,
    settings: SettingsDependency,
    explain: Annotated[
        bool,
        Query(description="Include retrieval channels, RRF contributions, and boosts."),
    ] = False,
) -> list[SearchResultRead] | SearchExplainResponseRead:
    """Run hybrid client and document search."""
    service = SearchService(
        repository=SearchRepository(session),
        embedding_provider=create_embedding_provider(settings),
    )
    if explain:
        return await service.search_with_explanation(q, result_limit=settings.search_result_limit)
    return await service.search(q, result_limit=settings.search_result_limit)
