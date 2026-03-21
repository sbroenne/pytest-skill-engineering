"""Banking MCP server for integration testing.

Run as: python -m pytest_skill_engineering.testing.banking_mcp

Supports all three transports:
- stdio (default): ``python -m pytest_skill_engineering.testing.banking_mcp``
- streamable-http: ``python -m pytest_skill_engineering.testing.banking_mcp --transport streamable-http --port 8080``
- sse: ``python -m pytest_skill_engineering.testing.banking_mcp --transport sse --port 8080``

This server maintains state across calls, enabling tests for:
- Multi-turn conversations where account balances change
- Session-based workflows (check → transfer → verify)
- Complex prompts requiring multiple tool calls
"""

from __future__ import annotations

import argparse
import json

from mcp.server.fastmcp import FastMCP

from pytest_skill_engineering.testing.banking import BankingService

# ---------------------------------------------------------------------------
# Server & service
# ---------------------------------------------------------------------------

mcp = FastMCP("pytest-skill-engineering-banking-server")
_service = BankingService()

# ---------------------------------------------------------------------------
# Tools – thin wrappers that delegate to BankingService
# ---------------------------------------------------------------------------


@mcp.tool()
def get_balance(account: str) -> str:
    """Get the current balance for a specific account.

    Args:
        account: Account name (e.g. "checking" or "savings").
    """
    result = _service.get_balance(account)
    if result.success:
        return json.dumps(result.value)
    return f"Error: {result.error}"


@mcp.tool()
def get_all_balances() -> str:
    """Get balances for all accounts at once."""
    result = _service.get_all_balances()
    if result.success:
        return json.dumps(result.value)
    return f"Error: {result.error}"


@mcp.tool()
def transfer(from_account: str, to_account: str, amount: float) -> str:
    """Transfer money between accounts.

    Args:
        from_account: Source account name.
        to_account: Destination account name.
        amount: Amount to transfer (positive number).
    """
    result = _service.transfer(from_account, to_account, amount)
    if result.success:
        return json.dumps(result.value)
    return f"Error: {result.error}"


@mcp.tool()
def deposit(account: str, amount: float) -> str:
    """Deposit money into an account.

    Args:
        account: Account name.
        amount: Amount to deposit (positive number).
    """
    result = _service.deposit(account, amount)
    if result.success:
        return json.dumps(result.value)
    return f"Error: {result.error}"


@mcp.tool()
def withdraw(account: str, amount: float) -> str:
    """Withdraw money from an account.

    Args:
        account: Account name.
        amount: Amount to withdraw (positive number).
    """
    result = _service.withdraw(account, amount)
    if result.success:
        return json.dumps(result.value)
    return f"Error: {result.error}"


@mcp.tool()
def get_transactions(account: str | None = None, limit: int = 10) -> str:
    """View transaction history.

    Args:
        account: Optional account name to filter by.
        limit: Maximum number of transactions to return (default 10).
    """
    result = _service.get_transactions(account=account, limit=limit)
    if result.success:
        return json.dumps(result.value)
    return f"Error: {result.error}"


# ---------------------------------------------------------------------------
# Prompts – reusable prompt templates
# ---------------------------------------------------------------------------


@mcp.prompt()
def account_summary(account: str = "checking") -> str:
    """Get a summary of account activity.

    Args:
        account: Account name to summarize (default: "checking").
    """
    return (
        f"Please provide a summary of the {account} account. "
        f"Include the current balance and recent transactions."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse args and run the server with the chosen transport."""
    parser = argparse.ArgumentParser(description="Banking MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
    )
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    # Configure host/port via FastMCP settings
    mcp.settings.host = args.host
    mcp.settings.port = args.port

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "sse":
        mcp.run(transport="sse")
    elif args.transport == "streamable-http":
        mcp.settings.stateless_http = True
        mcp.settings.json_response = True
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
