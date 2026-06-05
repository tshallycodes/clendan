"""
Collections Worker — sub-agent worker. Called by Financial Orchestrator as a tool.
Determines next action for overdue invoices: reminder, escalation, payment plan, or write-off.
# TODO: wire crm_api and email_dispatch_api in Phase 2
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.workers.base import BaseWorker, WorkerOutput, WorkerType


class CollectionsInput(BaseModel):
    tenant_id: str
    invoice_id: str
    vendor: str
    amount_minor: int
    currency: str
    due_date: date
    days_overdue: int
    previous_reminders_sent: int
    customer_payment_history: dict


class CollectionsOutput(BaseModel):
    action: Literal["reminder_sent", "escalated", "payment_plan_offered", "written_off"]
    message_draft: str
    next_action_date: date
    confidence: float
    reasoning: str


class CollectionsWorker(BaseWorker):
    WORKER_TYPE = WorkerType.COLLECTIONS
    REQUIRED_TOOLS = ["crm_api", "email_dispatch_api"]
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> WorkerOutput:
        # TODO: wire crm_api and email_dispatch_api
        validated = CollectionsInput(tenant_id=tenant_id, **input_data)
        result = CollectionsOutput(
            action="reminder_sent",
            message_draft="Stub",
            next_action_date=date.today(),
            confidence=0.0,
            reasoning="Stub — wire crm_api and email_dispatch_api",
        )
        return WorkerOutput(
            worker_type=self.WORKER_TYPE,
            decision=result.action,
            confidence=result.confidence,
            reasoning=result.reasoning,
            actions_taken=[],
            output_data=result.model_dump(),
        )
