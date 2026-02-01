"""Weather MCP server for integration testing.

Run as: python -m pytest_aitest.testing.weather_mcp
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from pytest_aitest.testing.weather import WeatherStore


class WeatherMCPServer:
    """MCP stdio server wrapping the weather store."""

    def __init__(self) -> None:
        self.store = WeatherStore()
        self.running = True

    async def handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Handle a JSON-RPC request."""
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "pytest-aitest-weather-server",
                        "version": "1.0.0",
                    },
                },
            }

        if method == "notifications/initialized":
            return None

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": self.store.get_tool_schemas()},
            }

        if method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            result = await self.store.call_tool_async(tool_name, arguments)

            if result.success:
                content = [{"type": "text", "text": json.dumps(result.value)}]
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": content, "isError": False},
                }
            else:
                content = [{"type": "text", "text": result.error}]
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": content, "isError": True},
                }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    def run_sync(self) -> None:
        """Run the stdio server using newline-delimited JSON."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
                response = asyncio.run(self.handle_request(request))

                if response is not None:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()

            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}", file=sys.stderr)
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)


def main() -> None:
    """Entry point."""
    server = WeatherMCPServer()
    server.run_sync()


if __name__ == "__main__":
    main()
