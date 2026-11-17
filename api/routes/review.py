"""GET /review — list items pending human review (stub, to be backed by a store)."""
from fastapi import APIRouter

router = APIRouter(prefix="/review", tags=["review"])


@router.get("", summary="List items in the review queue")
def list_review_items():
    # TODO: wire to a persistent review queue store
    return {"items": [], "message": "Review queue store not yet implemented"}
