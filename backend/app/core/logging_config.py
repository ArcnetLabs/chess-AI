"""Custom logging configuration to reduce verbosity."""

import logging
from typing import Optional


class HTTPRequestFilter(logging.Filter):
    """
    Filter to reduce verbosity of routine HTTP requests.
    
    Suppresses INFO level logs for:
    - GET requests (polling endpoints)
    - OPTIONS requests (CORS preflight)
    
    Keeps logs for:
    - POST/PUT/DELETE requests (state changes)
    - Error responses (4xx, 5xx)
    - Analysis-related operations
    """
    
    # Endpoints to suppress when they're GET requests
    SUPPRESS_GET_ENDPOINTS = [
        "/api/v1/games/",
        "/api/v1/analysis/",
        "/api/v1/users/by-username/",
        "/api/v1/insights/",
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log records.
        
        Returns:
            True to keep the log, False to suppress it
        """
        # Only filter INFO level logs
        if record.levelno != logging.INFO:
            return True
        
        message = record.getMessage()
        
        # Suppress OPTIONS requests (CORS preflight)
        if "OPTIONS" in message:
            return False
        
        # Suppress routine GET requests to polling endpoints
        if "GET" in message:
            for endpoint in self.SUPPRESS_GET_ENDPOINTS:
                if endpoint in message and "200 OK" in message:
                    return False
        
        # Keep all other logs
        return True


def configure_logging():
    """Configure logging with custom filters."""
    # Add filter to uvicorn access logger
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.addFilter(HTTPRequestFilter())
