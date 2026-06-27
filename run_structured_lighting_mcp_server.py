#!/usr/bin/env python3
"""Startup script for the nano-dlna Structured Lighting MCP server."""

import asyncio
import logging
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "web", "backend")
for path in (ROOT, BACKEND):
    if path not in sys.path:
        sys.path.insert(0, path)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def main():
    from web.backend.mcp_structured_lighting_server import mcp

    logger.info("Starting nano-dlna Structured Lighting MCP server")
    await mcp.run_stdio()


if __name__ == "__main__":
    asyncio.run(main())
