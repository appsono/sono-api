from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.core.maintenance_state import maintenance_state

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