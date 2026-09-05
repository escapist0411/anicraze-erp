import logging
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.config.settings import get_settings
from app.exceptions.domain import DomainError
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.schemas.common import ErrorDetail, ErrorResponse
from app.startup.lifecycle import lifespan

settings = get_settings()
logger = logging.getLogger(__name__)
app = FastAPI(title=settings.app_name, version="1.1.0", openapi_url=f"{settings.api_v1_prefix}/openapi.json", docs_url=f"{settings.api_v1_prefix}/docs", redoc_url=None, lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type", "X-Request-ID"], expose_headers=["X-Request-ID"])
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


def error_response(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    body = ErrorResponse(message=message, error=ErrorDetail(code=code, request_id=request_id))
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


@app.exception_handler(DomainError)
async def handle_domain_error(request: Request, error: DomainError) -> JSONResponse:
    return error_response(request, error.status_code, error.code, error.message)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    logger.info("Request validation failed for path=%s error_count=%s", request.url.path, len(error.errors()))
    return error_response(request, status.HTTP_422_UNPROCESSABLE_ENTITY, "validation_error", "Request validation failed")


@app.exception_handler(HTTPException)
async def handle_http_error(request: Request, error: HTTPException) -> JSONResponse:
    code = "rate_limit_exceeded" if error.status_code == status.HTTP_429_TOO_MANY_REQUESTS else "http_error"
    message = error.detail if isinstance(error.detail, str) else "Request could not be completed"
    return error_response(request, error.status_code, code, message)


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
    logger.exception("Unhandled request error", exc_info=error)
    return error_response(request, status.HTTP_500_INTERNAL_SERVER_ERROR, "internal_error", "An unexpected server error occurred")


app.include_router(api_router, prefix=settings.api_v1_prefix)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
