"""
Production server entrypoint.

Usage:
    python run_server.py                         # development
    ENVIRONMENT=production python run_server.py  # production
"""

from __future__ import annotations

import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()

from config.settings import get_settings


def main():
    settings = get_settings()

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║       Doctor Appointment Orchestration Platform          ║
╠══════════════════════════════════════════════════════════════╣
║  Environment:  {settings.environment.value:<45}║
║  Host:         {settings.api_host:<45}║
║  Port:         {str(settings.api_port):<45}║
║  Workers:      {str(settings.api_workers):<45}║
║  Debug:        {str(settings.debug):<45}║
║  Tracing:      {str(settings.langsmith.tracing_v2):<45}║
║  Log Level:    {settings.log_level:<45}║
╚══════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "api:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers if not settings.debug else 1,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
