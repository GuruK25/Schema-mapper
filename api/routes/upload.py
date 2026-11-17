"""POST /map — accept a supplier file and return a MappingResult."""
import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from mapper.pipeline import process

router = APIRouter(prefix="/map", tags=["mapping"])


@router.post("", summary="Map a supplier file to PO line items")
async def map_file(
    file: UploadFile = File(...),
    supplier_id: str | None = Form(None),
    po_number: str | None = Form(None),
):
    suffix = Path(file.filename or "upload").suffix or ".csv"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    result = process(
        file_path=tmp_path,
        supplier_id=supplier_id,
    )
    # Patch po_number into metadata if provided
    if po_number:
        result.metadata.po_number = po_number

    Path(tmp_path).unlink(missing_ok=True)
    return JSONResponse(content=result.model_dump())
