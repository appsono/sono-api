from fastapi import FastAPI, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from .routers import users, admin, files, audio, collections, announcements
from .core.storage import create_minio_bucket_if_not_exists
from .core.scheduler import init_scheduler, start_scheduler, shutdown_scheduler

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_minio_bucket_if_not_exists()
    init_scheduler()
    start_scheduler()
    yield
    shutdown_scheduler()

app = FastAPI(
    lifespan=lifespan,
    title="Sono API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None
)

#rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

#security headers
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response

#CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://sono.wtf",
        "https://www.sono.wtf",
        "sono_api",
        "sono_api:8000",
        "localhost",
        "localhost:3001",
    ],
    allow_origin_regex=r"https://.*\.sono\.wtf",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization", 
        "Content-Type", 
        "X-Password-Encrypted",
        "X-Requested-With",
        "Accept",
        "Origin"
    ],
)

#trusted hosts
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "sono.wtf",
        "*.sono.wtf",
        "sono_api",
        "sono_api:8000",
        "localhost",
        "localhost:8000",
    ],
)

api_router = APIRouter(prefix=settings.API_V1_STR)

api_router.include_router(users.router)
api_router.include_router(admin.router)
api_router.include_router(files.router)
api_router.include_router(audio.router)
api_router.include_router(collections.router)
api_router.include_router(announcements.router)

app.include_router(api_router)

@app.get("/", include_in_schema=False)
def read_root():
    return {"message": "OK"}

@app.get("/health", tags=["health"])
def health_check():
    return {
        "status": "healthy",
        "project_name": settings.PROJECT_NAME,
        "version": "1.0.0",
    }

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests"}
    )