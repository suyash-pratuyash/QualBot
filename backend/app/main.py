"""FastAPI application entry point for QualBot."""
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import get_settings
from app.api.routes import router, websocket_conversation
from app.persistence.database import _get_engine, init_db
from app.services.auth import ensure_default_admin
settings=get_settings()
app=FastAPI(title="QualBot API",version="0.1.0",debug=settings.environment=="development",openapi_url=f"{settings.api_prefix}/openapi.json",docs_url=f"{settings.api_prefix}/docs",redoc_url=None)
app.add_middleware(CORSMiddleware,allow_origins=[str(o).rstrip("/") for o in settings.cors_origins],allow_credentials=True,allow_methods=["GET","POST","PATCH"],allow_headers=["Authorization","Content-Type"])
@app.exception_handler(HTTPException)
async def http_exception_handler(_request,exc):
    detail=exc.detail if isinstance(exc.detail,dict) and "code" in exc.detail else {"code":"HTTP_ERROR","message":str(exc.detail),"details":None}
    return JSONResponse(status_code=exc.status_code,content={"error":detail})
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request,exc):
    return JSONResponse(status_code=422,content={"error":{"code":"VALIDATION_ERROR","message":"Request validation failed.","details":exc.errors()}})
@app.on_event("startup")
def startup():
    engine=_get_engine(); init_db(engine)
    from sqlalchemy.orm import Session
    with Session(engine) as db: ensure_default_admin(db)
app.include_router(router,prefix=settings.api_prefix)
app.add_api_websocket_route("/ws/v1/conversations/{conversation_id}",websocket_conversation)
