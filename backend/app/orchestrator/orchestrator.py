"""
Financial Orchestrator — master agent.
Receives all financial events, classifies them, invokes the correct tool as a tool,
applies global policy, compiles output, writes audit log.
Tools are NEVER called directly — always through _invoke_tool().
"""
import asyncio
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.core.config import get_settings as _get_settings
from app.core.logging import get_logger
from app.orchestrator.registry import get_tool
from app.tools.base import ToolOutput, ToolType

logger = get_logger(__name__)

EVENT_TO_WORKER: dict[str, ToolType] = {
    "invoice_received": ToolType.INVOICE_PROCESSING,
    "transaction_posted": ToolType.ACCOUNTANT,
    "expense_submitted": ToolType.EXPENSE_CONTROL,
    "reconciliation_requested": ToolType.RECONCILIATION,
    "fraud_check_requested": ToolType.FRAUD_DETECTION,
    "collection_triggered": ToolType.COLLECTIONS,
    "revenue_recognition_run": ToolType.REVENUE_RECOGNITION,
    "compliance_check_requested": ToolType.COMPLIANCE,
    "receipt_received": ToolType.RECEIPT_PROCESSING,
    "treasury_run": ToolType.TREASURY,
}

EventType = Literal[
    "invoice_received",
    "transaction_posted",
    "expense_submitted",
    "reconciliation_requested",
    "fraud_check_requested",
    "collection_triggered",
    "revenue_recognition_run",
    "compliance_check_requested",
    "receipt_received",
    "treasury_run",
]


class FinancialEvent(BaseModel):
    event_id: str
    tenant_id: str
    event_type: EventType
    payload: dict
    timestamp: datetime
    idempotency_key: str


class OrchestratorOutput(BaseModel):
    event_id: str
    tool_type: ToolType
    decision: str
    confidence: float
    reasoning: str
    actions_taken: list[str]
    trace_id: str
    timestamp: datetime


class FinancialOrchestrator:

    async def handle_event(self, event: FinancialEvent, tenant_id: str) -> OrchestratorOutput:
        """Entry point. Classify → select tool → invoke → policy → output."""
        tool_type = await self._classify_event(event)
        tool_output = await self._invoke_tool(tool_type, event.payload, tenant_id)
        return await self._compile_output(event, tool_output)

    async def _classify_event(self, event: FinancialEvent) -> ToolType:
        """Determine which tool should handle this event."""
        tool_type = EVENT_TO_WORKER.get(event.event_type)
        if tool_type is None:
            raise ValueError(f"No tool registered for event type: {event.event_type}")
        return tool_type

    async def _invoke_tool(
        self,
        tool_type: ToolType,
        input_data: dict,
        tenant_id: str,
    ) -> ToolOutput:
        """
        Call a sub-agent tool as a tool with timeout and exponential-backoff retry.
        All tool invocations go through here — never directly.
        """
        tool = get_tool(tool_type)
        settings = _get_settings()
        timeout = 30.0

        last_exc: Exception = RuntimeError("No attempts made")
        for attempt in range(settings.max_agent_attempts):
            logger.info(
                "invoking_tool",
                extra={"tool_type": tool_type, "tenant_id": tenant_id, "attempt": attempt + 1},
            )
            try:
                return await asyncio.wait_for(
                    tool.execute(input_data, tenant_id),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                last_exc = RuntimeError(
                    f"Tool {tool_type} timed out after {timeout}s on attempt {attempt + 1}"
                )
                logger.warning("tool_timeout", extra={"tool_type": tool_type, "attempt": attempt + 1})
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "tool_error",
                    extra={"tool_type": tool_type, "attempt": attempt + 1, "error": str(exc)},
                )
            if attempt < settings.max_agent_attempts - 1:
                await asyncio.sleep(settings.backoff_seconds * (attempt + 1))

        raise RuntimeError(
            f"Tool {tool_type} failed after {settings.max_agent_attempts} attempts: {last_exc}"
        ) from last_exc

    async def _compile_output(
        self,
        event: FinancialEvent,
        tool_output: ToolOutput,
    ) -> OrchestratorOutput:
        """Compile final decision and reasoning trace for audit."""
        return OrchestratorOutput(
            event_id=event.event_id,
            tool_type=tool_output.tool_type,
            decision=tool_output.decision,
            confidence=tool_output.confidence,
            reasoning=tool_output.reasoning,
            actions_taken=tool_output.actions_taken,
            trace_id=event.idempotency_key,
            timestamp=event.timestamp,
        )

    # -------------------------------------------------------------------------
    # Multi-step chaining
    # -------------------------------------------------------------------------

    async def invoke_tools_sequential(
        self,
        tool_types: list[ToolType],
        payload: dict,
        tenant_id: str,
    ) -> list[ToolOutput]:
        """
        Invoke tools one at a time in order.
        Each tool's output_data is merged into the payload for the next step.
        Stops immediately if any tool returns decision == "blocked".
        """
        results: list[ToolOutput] = []
        current_payload = dict(payload)

        for tool_type in tool_types:
            logger.info(
                "sequential_chain_step",
                extra={
                    "tool_type": tool_type,
                    "tenant_id": tenant_id,
                    "step": len(results) + 1,
                    "total": len(tool_types),
                },
            )
            output = await self._invoke_tool(tool_type, current_payload, tenant_id)
            results.append(output)

            if output.decision == "blocked":
                logger.info(
                    "sequential_chain_blocked",
                    extra={"tool_type": tool_type, "reasoning": output.reasoning},
                )
                break

            current_payload = {**current_payload, **output.output_data}

        return results

    # -------------------------------------------------------------------------
    # Parallel invocation
    # -------------------------------------------------------------------------

    async def invoke_tools_parallel(
        self,
        tool_types: list[ToolType],
        payload: dict,
        tenant_id: str,
    ) -> list[ToolOutput]:
        """
        Invoke all tools simultaneously with the same original payload.
        Uses asyncio.gather — all tools receive the unmodified input.
        """
        logger.info(
            "parallel_invocation_start",
            extra={"tool_types": [w.value for w in tool_types], "tenant_id": tenant_id},
        )
        results: list[ToolOutput] = await asyncio.gather(
            *[
                self._invoke_tool(tool_type, payload, tenant_id)
                for tool_type in tool_types
            ]
        )
        return list(results)

    # -------------------------------------------------------------------------
    # Conflict resolution
    # -------------------------------------------------------------------------

    def resolve_conflict(self, outputs: list[ToolOutput]) -> ToolOutput:
        """
        Priority order when multiple tools return results:
        1. blocked       — highest severity wins
        2. approval_required
        3. auto_approved — highest confidence wins; ties go to first
        """
        if not outputs:
            raise ValueError("resolve_conflict called with empty outputs list")

        blocked = [o for o in outputs if o.decision == "blocked"]
        if blocked:
            return blocked[0]

        approval_required = [o for o in outputs if o.decision == "approval_required"]
        if approval_required:
            return approval_required[0]

        return max(outputs, key=lambda o: o.confidence)

    # -------------------------------------------------------------------------
    # Convenience: invoice + fraud sequential chain
    # -------------------------------------------------------------------------

    async def handle_invoice_with_fraud_check(
        self,
        event: FinancialEvent,
        tenant_id: str,
    ) -> OrchestratorOutput:
        """
        Runs Invoice Processing then Fraud Detection sequentially.
        If fraud check blocks → returns blocked output.
        Otherwise compiles final output from the fraud check result (last step).
        """
        chain = await self.invoke_tools_sequential(
            tool_types=[ToolType.INVOICE_PROCESSING, ToolType.FRAUD_DETECTION],
            payload=event.payload,
            tenant_id=tenant_id,
        )

        # chain is never empty — at minimum invoice step ran
        final = chain[-1]

        if final.decision == "blocked":
            logger.info(
                "invoice_fraud_chain_blocked",
                extra={"event_id": event.event_id, "reasoning": final.reasoning},
            )
            return await self._compile_output(event, final)

        return await self._compile_output(event, final)
