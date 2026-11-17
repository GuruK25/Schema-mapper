"""Supplier profile endpoints."""
from fastapi import APIRouter, HTTPException
from mapper.profiles.profile_store import load_profile, save_profile
from mapper.models import ColumnMappingResult

router = APIRouter(prefix="/suppliers", tags=["profiles"])


@router.get("/{supplier_id}/profile", summary="Get saved mapping profile for a supplier")
def get_profile(supplier_id: str):
    profile = load_profile(supplier_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"No profile found for supplier: {supplier_id}")
    return profile.model_dump()


@router.post("/{supplier_id}/profile", summary="Save a confirmed mapping profile for a supplier")
def set_profile(supplier_id: str, mapping: ColumnMappingResult):
    save_profile(supplier_id, mapping)
    return {"saved": supplier_id}
