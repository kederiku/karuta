"""Sonde de liveness de l'API."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Réponse de la sonde de liveness."""

    status: str = Field(description="Vaut « ok » lorsque l'application sert des requêtes.")


@router.get("/health", operation_id="health_check", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Indique que l'API est démarrée et répond.

    Cette sonde ne vérifie aucune dépendance externe : elle confirme uniquement que le
    processus est vivant. Elle répond toujours 200 tant qu'elle est joignable.
    """
    return HealthResponse(status="ok")
