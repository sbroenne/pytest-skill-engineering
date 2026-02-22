"""Banking service for testing - stateful account management.

Provides a realistic banking service for testing multi-turn conversations
and session-based workflows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pytest_skill_engineering.testing.types import ToolResult


@dataclass
class Transaction:
    """A banking transaction record."""

    id: str
    timestamp: str
    type: str  # "transfer", "deposit", "withdrawal"
    from_account: str | None
    to_account: str | None
    amount: float
    description: str


@dataclass
class BankingService:
    """In-memory banking service with account management.

    Maintains state across calls, enabling tests for:
    - Multi-turn conversations with state changes
    - Session-based workflows (check balance → transfer → verify)
    - Complex prompts requiring multiple tool calls
    """

    accounts: dict[str, float] = field(
        default_factory=lambda: {
            "checking": 1500.00,
            "savings": 3000.00,
        }
    )
    transactions: list[Transaction] = field(default_factory=list)
    _tx_counter: int = 0

    def _next_tx_id(self) -> str:
        """Generate next transaction ID."""
        self._tx_counter += 1
        return f"TX{self._tx_counter:04d}"

    def _now(self) -> str:
        """Get current timestamp."""
        return datetime.now().isoformat()

    def get_balance(self, account: str) -> ToolResult:
        """Get the balance of an account.

        Args:
            account: Account name ("checking" or "savings")

        Returns:
            ToolResult with balance or error
        """
        account_lower = account.lower()
        if account_lower not in self.accounts:
            return ToolResult(
                success=False,
                value=None,
                error=f"Account '{account}' not found. Available: {list(self.accounts.keys())}",
            )

        balance = self.accounts[account_lower]
        return ToolResult(
            success=True,
            value={
                "account": account_lower,
                "balance": balance,
                "formatted": f"${balance:,.2f}",
            },
        )

    def get_all_balances(self) -> ToolResult:
        """Get balances for all accounts.

        Returns:
            ToolResult with all account balances
        """
        balances = {}
        total = 0.0
        for name, balance in self.accounts.items():
            balances[name] = {
                "balance": balance,
                "formatted": f"${balance:,.2f}",
            }
            total += balance

        return ToolResult(
            success=True,
            value={
                "accounts": balances,
                "total": total,
                "total_formatted": f"${total:,.2f}",
            },
        )

    def transfer(self, from_account: str, to_account: str, amount: float) -> ToolResult:
        """Transfer money between accounts.

        Args:
            from_account: Source account name
            to_account: Destination account name
            amount: Amount to transfer (positive number)

        Returns:
            ToolResult with transfer confirmation or error
        """
        from_lower = from_account.lower()
        to_lower = to_account.lower()

        if from_lower not in self.accounts:
            return ToolResult(
                success=False,
                value=None,
                error=f"Source account '{from_account}' not found.",
            )

        if to_lower not in self.accounts:
            return ToolResult(
                success=False,
                value=None,
                error=f"Destination account '{to_account}' not found.",
            )

        if amount <= 0:
            return ToolResult(
                success=False,
                value=None,
                error="Transfer amount must be positive.",
            )

        if self.accounts[from_lower] < amount:
            return ToolResult(
                success=False,
                value=None,
                error=f"Insufficient funds. {from_account} has ${self.accounts[from_lower]:,.2f}, "
                f"but transfer requires ${amount:,.2f}.",
            )

        # Execute transfer
        self.accounts[from_lower] -= amount
        self.accounts[to_lower] += amount

        # Record transaction
        tx = Transaction(
            id=self._next_tx_id(),
            timestamp=self._now(),
            type="transfer",
            from_account=from_lower,
            to_account=to_lower,
            amount=amount,
            description=f"Transfer from {from_lower} to {to_lower}",
        )
        self.transactions.append(tx)

        return ToolResult(
            success=True,
            value={
                "transaction_id": tx.id,
                "type": "transfer",
                "from_account": from_lower,
                "to_account": to_lower,
                "amount": amount,
                "amount_formatted": f"${amount:,.2f}",
                "new_balance_from": self.accounts[from_lower],
                "new_balance_to": self.accounts[to_lower],
                "message": f"Successfully transferred ${amount:,.2f} from {from_lower} to {to_lower}.",
            },
        )

    def deposit(self, account: str, amount: float) -> ToolResult:
        """Deposit money into an account.

        Args:
            account: Account name
            amount: Amount to deposit (positive number)

        Returns:
            ToolResult with deposit confirmation or error
        """
        account_lower = account.lower()

        if account_lower not in self.accounts:
            return ToolResult(
                success=False,
                value=None,
                error=f"Account '{account}' not found.",
            )

        if amount <= 0:
            return ToolResult(
                success=False,
                value=None,
                error="Deposit amount must be positive.",
            )

        self.accounts[account_lower] += amount

        tx = Transaction(
            id=self._next_tx_id(),
            timestamp=self._now(),
            type="deposit",
            from_account=None,
            to_account=account_lower,
            amount=amount,
            description=f"Deposit to {account_lower}",
        )
        self.transactions.append(tx)

        return ToolResult(
            success=True,
            value={
                "transaction_id": tx.id,
                "type": "deposit",
                "account": account_lower,
                "amount": amount,
                "amount_formatted": f"${amount:,.2f}",
                "new_balance": self.accounts[account_lower],
                "message": f"Successfully deposited ${amount:,.2f} to {account_lower}.",
            },
        )

    def withdraw(self, account: str, amount: float) -> ToolResult:
        """Withdraw money from an account.

        Args:
            account: Account name
            amount: Amount to withdraw (positive number)

        Returns:
            ToolResult with withdrawal confirmation or error
        """
        account_lower = account.lower()

        if account_lower not in self.accounts:
            return ToolResult(
                success=False,
                value=None,
                error=f"Account '{account}' not found.",
            )

        if amount <= 0:
            return ToolResult(
                success=False,
                value=None,
                error="Withdrawal amount must be positive.",
            )

        if self.accounts[account_lower] < amount:
            return ToolResult(
                success=False,
                value=None,
                error=f"Insufficient funds. {account} has ${self.accounts[account_lower]:,.2f}.",
            )

        self.accounts[account_lower] -= amount

        tx = Transaction(
            id=self._next_tx_id(),
            timestamp=self._now(),
            type="withdrawal",
            from_account=account_lower,
            to_account=None,
            amount=amount,
            description=f"Withdrawal from {account_lower}",
        )
        self.transactions.append(tx)

        return ToolResult(
            success=True,
            value={
                "transaction_id": tx.id,
                "type": "withdrawal",
                "account": account_lower,
                "amount": amount,
                "amount_formatted": f"${amount:,.2f}",
                "new_balance": self.accounts[account_lower],
                "message": f"Successfully withdrew ${amount:,.2f} from {account_lower}.",
            },
        )

    def get_transactions(self, account: str | None = None, limit: int = 10) -> ToolResult:
        """Get recent transactions.

        Args:
            account: Optional account to filter by
            limit: Maximum number of transactions to return

        Returns:
            ToolResult with transaction list
        """
        txs = self.transactions

        if account:
            account_lower = account.lower()
            txs = [
                t for t in txs if t.from_account == account_lower or t.to_account == account_lower
            ]

        # Most recent first
        txs = list(reversed(txs[-limit:]))

        return ToolResult(
            success=True,
            value={
                "transactions": [
                    {
                        "id": t.id,
                        "timestamp": t.timestamp,
                        "type": t.type,
                        "from_account": t.from_account,
                        "to_account": t.to_account,
                        "amount": t.amount,
                        "amount_formatted": f"${t.amount:,.2f}",
                        "description": t.description,
                    }
                    for t in txs
                ],
                "count": len(txs),
                "filter": account,
            },
        )

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Get MCP tool schemas for all operations."""
        return [
            {
                "name": "get_balance",
                "description": "Get the current balance of a specific account (checking or savings).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account": {
                            "type": "string",
                            "description": "Account name: 'checking' or 'savings'",
                            "enum": ["checking", "savings"],
                        },
                    },
                    "required": ["account"],
                },
            },
            {
                "name": "get_all_balances",
                "description": "Get balances for all accounts at once, including total.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "transfer",
                "description": "Transfer money between accounts (checking and savings).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "from_account": {
                            "type": "string",
                            "description": "Source account name",
                            "enum": ["checking", "savings"],
                        },
                        "to_account": {
                            "type": "string",
                            "description": "Destination account name",
                            "enum": ["checking", "savings"],
                        },
                        "amount": {
                            "type": "number",
                            "description": "Amount to transfer in dollars",
                        },
                    },
                    "required": ["from_account", "to_account", "amount"],
                },
            },
            {
                "name": "deposit",
                "description": "Deposit money into an account.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account": {
                            "type": "string",
                            "description": "Account to deposit into",
                            "enum": ["checking", "savings"],
                        },
                        "amount": {
                            "type": "number",
                            "description": "Amount to deposit in dollars",
                        },
                    },
                    "required": ["account", "amount"],
                },
            },
            {
                "name": "withdraw",
                "description": "Withdraw money from an account.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account": {
                            "type": "string",
                            "description": "Account to withdraw from",
                            "enum": ["checking", "savings"],
                        },
                        "amount": {
                            "type": "number",
                            "description": "Amount to withdraw in dollars",
                        },
                    },
                    "required": ["account", "amount"],
                },
            },
            {
                "name": "get_transactions",
                "description": "Get recent transaction history, optionally filtered by account.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account": {
                            "type": "string",
                            "description": "Optional: filter by account name",
                            "enum": ["checking", "savings"],
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of transactions to return (default: 10)",
                            "default": 10,
                        },
                    },
                },
            },
        ]

    async def call_tool_async(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Call a tool by name with arguments."""
        match name:
            case "get_balance":
                return self.get_balance(arguments.get("account", ""))
            case "get_all_balances":
                return self.get_all_balances()
            case "transfer":
                return self.transfer(
                    arguments.get("from_account", ""),
                    arguments.get("to_account", ""),
                    arguments.get("amount", 0),
                )
            case "deposit":
                return self.deposit(
                    arguments.get("account", ""),
                    arguments.get("amount", 0),
                )
            case "withdraw":
                return self.withdraw(
                    arguments.get("account", ""),
                    arguments.get("amount", 0),
                )
            case "get_transactions":
                return self.get_transactions(
                    arguments.get("account"),
                    arguments.get("limit", 10),
                )
            case _:
                return ToolResult(
                    success=False,
                    value=None,
                    error=f"Unknown tool: {name}",
                )
        # Unreachable: match is exhaustive, but satisfies static analyzers
        return ToolResult(success=False, value=None, error=f"Unhandled tool: {name}")
