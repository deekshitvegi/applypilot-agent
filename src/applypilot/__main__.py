"""``python -m applypilot`` / the ``applypilot`` command."""

from __future__ import annotations

import argparse

from . import __version__
from .config import load_settings


def main() -> None:
    settings = load_settings()
    parser = argparse.ArgumentParser(prog="applypilot", description="ApplyPilot local service")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    parser.add_argument("--reload", action="store_true", help="restart on code changes")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args()

    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        parser.error(
            "ApplyPilot holds your personal data and only ever listens on the loopback "
            "interface. Refusing to bind to " + args.host
        )

    import uvicorn

    print(f"ApplyPilot {__version__} on http://{args.host}:{args.port}")
    print(f"Data directory: {settings.data_dir}")
    uvicorn.run(
        "applypilot.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
