"""Entry point for the Laser Studio MCP server.

Examples::

    # Talk to a Laser Studio running on localhost:4444, over stdio (default).
    laserstudio_mcp

    # Custom Laser Studio REST endpoint.
    laserstudio_mcp --host 192.168.0.10 --port 4444

    # Serve over HTTP instead of stdio.
    laserstudio_mcp --transport streamable-http
"""

from __future__ import annotations

import argparse
import os

from ..lsapi.lsapi import LSAPI
from .server import build_server


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="laserstudio_mcp",
        description="MCP server exposing Laser Studio actions to MCP clients.",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("LASERSTUDIO_HOST", "localhost"),
        help="Host of the Laser Studio REST API (default: localhost).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("LASERSTUDIO_PORT", LSAPI.PORT)),
        help=f"Port of the Laser Studio REST API (default: {LSAPI.PORT}).",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="MCP transport to use (default: stdio).",
    )
    args = parser.parse_args()

    server = build_server(host=args.host, port=args.port)
    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
