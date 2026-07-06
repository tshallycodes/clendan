"""
Tool stub smoke tests.
Verifies that the reconciliation tool instantiates, accepts minimal valid input,
and returns a correctly shaped ToolOutput without touching any external API.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.tools.base import ToolOutput


_RECON_RESULT = {
    "decision": "auto_approved",
    "confidence": 0.9,
    "reasoning": "test",
    "actions_taken": [],
    "output_data": {},
}


# ---------------------------------------------------------------------------
# ReconciliationTool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reconciliation_tool_returns_tool_output():
    from app.tools.reconciliation import ReconciliationTool

    tool = ReconciliationTool()
    with patch("app.tools.reconciliation._execute_reconciliation", AsyncMock(return_value=_RECON_RESULT)):
        result = await tool.execute(
            input_data={
                "execution_id": "exec_001",
                "tool_id": "tool_001",
                "source_dataset": [],
                "target_dataset": [],
                "period_start": date(2025, 1, 1),
                "period_end": date(2025, 1, 31),
            },
            tenant_id="tenant_001",
        )

    assert isinstance(result, ToolOutput)
    assert isinstance(result.confidence, float)
    assert 0.0 <= result.confidence <= 1.0
    assert isinstance(result.reasoning, str) and result.reasoning
    assert isinstance(result.actions_taken, list)
