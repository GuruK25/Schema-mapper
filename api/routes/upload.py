"""POST /map — accept a supplier file + target schema, return a MappingResult."""
import json
import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from mapper.models import TargetSchema
from mapper.pipeline import process

router = APIRouter(prefix="/map", tags=["mapping"])


@router.post("", summary="Map a source file to a caller-provided target schema")
async def map_file(
    file: UploadFile = File(...),
    target_schema: str = Form(..., description=(
        "JSON string of the target schema. "
        'Example: {"fields": [{"name": "qty", "type": "number", "synonyms": ["quantity", "units"]}]}'
    )),
    source_id: str | None = Form(None, description="Identifier for the data source (e.g. supplier ID)"),
    exact_keys: str | None = Form(None, description="Comma-separated field names to exact-match records on"),
    fuzzy_keys: str | None = Form(None, description="Comma-separated field names to fuzzy-match records on"),
):
    # Parse and validate the target schema
    try:
        schema = TargetSchema.model_validate(json.loads(target_schema))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid target_schema: {e}")

    suffix = Path(file.filename or "upload").suffix or ".csv"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        result = process(
            file_path=tmp_path,
            target_schema=schema,
            source_id=source_id,
            exact_keys=[k.strip() for k in exact_keys.split(",")] if exact_keys else [],
            fuzzy_keys=[k.strip() for k in fuzzy_keys.split(",")] if fuzzy_keys else [],
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return JSONResponse(content=result.model_dump())
