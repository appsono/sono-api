from fastapi import Request, status
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from app.core.maintenance_state import maintenance_state
from app.core.config import settings
from app.database import SessionLocal
from app import crud

async def maintenance_mode_middleware(request: Request, call_next):
    """Check if maintenance mode is enabled"""

    #allow health check even in maintenance mode
    if request.url.path == "/health":
        return await call_next(request)

    #allow admin endpoints to control maintenance mode
    if request.url.path.startswith("/api/v1/admin/maintenance"):
        return await call_next(request)

    #check for maintenance mode
    if maintenance_state.is_enabled():
        #check if user is an admin (superuser) => allow them to bypass maintenance
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                username = payload.get("sub")
                if username:
                    db = SessionLocal()
                    try:
                        user = crud.get_user_by_username(db, username=username)
                        if user and user.is_superuser:
                            #admin can bypass maintenance mode
                            return await call_next(request)
                    finally:
                        db.close()
            except JWTError:
                pass  #invalid token => proceed with maintenance block

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": maintenance_state.get_message(),
                "status": "maintenance",
                "retry_after": 3600
            },
            headers={"Retry-After": "3600"}
        )

    return await call_next(request)