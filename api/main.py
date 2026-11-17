from fastapi import FastAPI
from api.routes import upload, review, profiles

app = FastAPI(
    title="Schema Mapper",
    description="Maps non-standard supplier files to canonical PO line item fields.",
    version="0.1.0",
)

app.include_router(upload.router)
app.include_router(review.router)
app.include_router(profiles.router)


@app.get("/health")
def health():
    return {"status": "ok"}
