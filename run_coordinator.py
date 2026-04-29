from __future__ import annotations

import uvicorn

from app.main import app
from app.core.config import settings
from app.services.ngrok_manager import NgrokManager


if __name__ == "__main__":
    ngrok = NgrokManager(
        enabled=settings.ngrok_autostart,
        app_port=settings.port,
        executable_path=settings.ngrok_path,
        authtoken=settings.ngrok_authtoken,
        api_base_url=settings.ngrok_api_base_url,
        url=settings.ngrok_url,
    )
    try:
        ngrok.start()
        uvicorn.run(app, host=settings.host, port=settings.port)
    finally:
        ngrok.stop()
