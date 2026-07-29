"""Run the service with Uvicorn."""

import os

import uvicorn

from .api import app


def main() -> None:
    """Start the HTTP server."""
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        access_log=False,
        log_config=None,
    )


if __name__ == "__main__":
    main()
