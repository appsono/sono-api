from fastapi import APIRouter, Depends, HTTPException, Security
from pydantic import BaseModel, Field
from typing import Optional
from app.core.security import get_current_active_superuser
from app import models
from app.core.maintenance_state import maintenance_state

router = APIRouter(prefix="/admin/maintenance", tags=["admin-maintenance"])


class MaintenanceToggle(BaseModel):
    enabled: bool
    message: Optional[str] = Field(None, max_length=200)


class MaintenanceStatus(BaseModel):
    enabled: bool
    message: str


@router.get("/status", response_model=MaintenanceStatus)
def get_maintenance_status():
    """Get current maintenance mode status (public endpoint)"""
    return MaintenanceStatus(
        enabled=maintenance_state.is_enabled(),
        message=maintenance_state.get_message()
    )


@router.post("/toggle", response_model=MaintenanceStatus)
def toggle_maintenance(
    toggle: MaintenanceToggle,
    current_user: models.User = Security(get_current_active_superuser)
):
    """Enable or disable maintenance mode (admin only)"""
    
    if toggle.enabled:
        message = toggle.message or "Service temporarily unavailable for maintenance"
        maintenance_state.enable(message)
        return MaintenanceStatus(
            enabled=True,
            message=maintenance_state.get_message()
        )
    else:
        maintenance_state.disable()
        return MaintenanceStatus(
            enabled=False,
            message=maintenance_state.get_message()
        )


@router.post("/enable", response_model=MaintenanceStatus)
def enable_maintenance(
    message: Optional[str] = None,
    current_user: models.User = Security(get_current_active_superuser)
):
    """Enable maintenance mode (admin only)"""
    
    if message:
        maintenance_state.enable(message)
    else:
        maintenance_state.enable()
    
    return MaintenanceStatus(
        enabled=True,
        message=maintenance_state.get_message()
    )


@router.post("/disable", response_model=MaintenanceStatus)
def disable_maintenance(
    current_user: models.User = Security(get_current_active_superuser)
):
    """Disable maintenance mode (admin only)"""
    
    maintenance_state.disable()
    
    return MaintenanceStatus(
        enabled=False,
        message=maintenance_state.get_message()
    )