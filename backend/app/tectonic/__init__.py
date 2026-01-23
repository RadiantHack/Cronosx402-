"""
Tectonic A2A Integration Module

Provides complete integration of Tectonic lending protocol into the A2A application.

Exports:
- TectonicService: High-level lending operations
- TectonicStrategy: Automated position management
- API Router: FastAPI endpoints for A2A integration
"""

from .service import TectonicService
from .strategy import TectonicStrategy
from .routes import router

__all__ = [
    "TectonicService",
    "TectonicStrategy",
    "router",
]
