"""Shared SDK client setup and cleanup for eval and judge sessions."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from copilot.client import CopilotClient
from copilot.generated.rpc import PermissionDecisionApproveOnce

logger = logging.getLogger(__name__)


def get_github_token() -> str | None:
    """Resolve explicit GitHub credentials without changing the environment."""
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def create_client(working_directory: str = ".") -> CopilotClient:
    """Create a client using explicit credentials or the SDK's signed-in user."""
    return CopilotClient(
        working_directory=working_directory,
        log_level="warning",
        github_token=get_github_token(),
    )


def approve_all_permissions(*_args: Any, **_kwargs: Any) -> PermissionDecisionApproveOnce:
    """Approve a permission request when the caller enables automatic approval."""
    return PermissionDecisionApproveOnce()


async def stop_client(client: CopilotClient) -> None:
    """Release the owned runtime without masking an execution failure."""
    try:
        await asyncio.wait_for(client.stop(), timeout=30)
    except Exception:
        logger.warning("Failed to stop Copilot CLI cleanly, force stopping", exc_info=True)
        try:
            await asyncio.wait_for(client.force_stop(), timeout=10)
        except Exception:
            logger.error("Failed to force stop Copilot CLI", exc_info=True)
