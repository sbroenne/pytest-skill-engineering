"""CLI test server for integration testing.

Run as: python -m pytest_aitest.testing.cli_server
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from pytest_aitest.testing.store import KeyValueStore


class CLITestServer:
    """Interactive CLI server wrapping the test store."""

    def __init__(self) -> None:
        self.store = KeyValueStore()

    def parse_args(self, line: str) -> tuple[str, dict]:
        """Parse a command line into tool name and arguments."""
        parts = line.strip().split(maxsplit=1)
        if not parts:
            return "", {}

        cmd = parts[0].lower()
        args_str = parts[1] if len(parts) > 1 else ""

        # Map commands to tools and parse arguments
        if cmd == "get":
            return "get", {"key": args_str}
        elif cmd == "set":
            key_value = args_str.split(maxsplit=1)
            if len(key_value) < 2:
                return "set", {"key": key_value[0] if key_value else "", "value": ""}
            return "set", {"key": key_value[0], "value": key_value[1]}
        elif cmd == "delete":
            return "delete", {"key": args_str}
        elif cmd == "list" or cmd == "list_keys" or cmd == "keys":
            return "list_keys", {}
        elif cmd == "calc" or cmd == "calculate":
            return "calculate", {"expression": args_str}
        elif cmd == "compare":
            ab = args_str.split(maxsplit=1)
            if len(ab) < 2:
                return "compare", {"a": ab[0] if ab else "", "b": ""}
            return "compare", {"a": ab[0], "b": ab[1]}
        elif cmd == "search":
            return "search", {"pattern": args_str}
        elif cmd == "transform":
            key_op = args_str.split(maxsplit=1)
            if len(key_op) < 2:
                return "transform", {
                    "key": key_op[0] if key_op else "",
                    "operation": "",
                }
            return "transform", {"key": key_op[0], "operation": key_op[1]}
        elif cmd == "fail":
            return "fail", {"message": args_str}
        elif cmd == "slow":
            ms_msg = args_str.split(maxsplit=1)
            try:
                ms = int(ms_msg[0]) if ms_msg else 0
            except ValueError:
                ms = 0
            msg = ms_msg[1] if len(ms_msg) > 1 else ""
            return "slow", {"ms": ms, "message": msg}
        elif cmd == "help":
            return "help", {}
        else:
            return cmd, {"raw": args_str}

    async def run_interactive(self) -> None:
        """Run in interactive mode."""
        print("pytest-aitest test server (CLI mode)")
        print("Type 'help' for available commands, 'quit' to exit")
        print()

        while True:
            try:
                line = input("> ")
            except (EOFError, KeyboardInterrupt):
                print()
                break

            line = line.strip()
            if not line:
                continue

            if line.lower() in ("quit", "exit", "q"):
                break

            cmd, args = self.parse_args(line)

            if cmd == "help":
                self.print_help()
                continue

            if cmd not in [
                "get",
                "set",
                "delete",
                "list_keys",
                "calculate",
                "compare",
                "search",
                "transform",
                "fail",
                "slow",
            ]:
                print(f"Unknown command: {cmd}")
                continue

            result = await self.store.call_tool_async(cmd, args)
            if result.success:
                print(json.dumps(result.value))
            else:
                print(f"ERROR: {result.error}")

    def print_help(self) -> None:
        """Print help message."""
        print("""
Available commands:
  get <key>                  - Get value at key
  set <key> <value>          - Set key to value
  delete <key>               - Delete key
  list (or keys)             - List all keys
  calc <expression>          - Evaluate math (e.g., calc 2+3*4)
  compare <a> <b>            - Compare two values
  search <pattern>           - Find keys matching regex
  transform <key> <operation> - Transform value (uppercase, lowercase, reverse, length, trim)
  fail <message>             - Always error (for testing)
  slow <ms> <message>        - Return after delay
  help                       - Show this help
  quit                       - Exit
""")


async def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="pytest-aitest CLI test server")
    parser.add_argument("--json", action="store_true", help="JSON-RPC mode (for programmatic use)")
    args = parser.parse_args()

    server = CLITestServer()

    if args.json:
        # JSON-RPC mode: read JSON from stdin, write JSON to stdout
        for line in sys.stdin:
            try:
                request = json.loads(line)
                cmd = request.get("tool", "")
                tool_args = request.get("arguments", {})
                result = await server.store.call_tool_async(cmd, tool_args)
                print(json.dumps(result.to_dict()))
            except json.JSONDecodeError:
                print(json.dumps({"success": False, "error": "Invalid JSON"}))
    else:
        await server.run_interactive()


if __name__ == "__main__":
    asyncio.run(main())
