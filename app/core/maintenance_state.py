"""Maintenance mode state manager"""

class MaintenanceState:
    """Thread-safe maintenance mode state"""
    
    def __init__(self):
        self._enabled = False
        self._message = "Service temporarily unavailable for maintenance"
    
    def enable(self, message: str = None):
        """Enable maintenance mode"""
        self._enabled = True
        if message:
            self._message = message
    
    def disable(self):
        """Disable maintenance mode"""
        self._enabled = False
    
    def is_enabled(self) -> bool:
        """Check if maintenance mode is enabled"""
        return self._enabled
    
    def get_message(self) -> str:
        """Get maintenance message"""
        return self._message


#global instance
maintenance_state = MaintenanceState()