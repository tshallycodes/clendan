"""
Base tool interface for all Clendan financial AI tools.
All tools subclass BaseTool and implement execute().
Tools are invoked exclusively through this interface via direct dispatch.
Tools never call each other directly.
"""
from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel


class ToolType(str, Enum):
    INVOICE_PROCESSING = "invoice_processing"
    RECEIPT_PROCESSING = "receipt_processing"
    RECONCILIATION = "reconciliation"
    EXPENSE_CONTROL = "expense_control"
    COLLECTIONS = "collections"
    FRAUD_DETECTION = "fraud_detection"
    TREASURY = "treasury"
    REVENUE_RECOGNITION = "revenue_recognition"
    CREDIT_UNDERWRITING = "credit_underwriting"
    COMPLIANCE = "compliance"
    # Merged tool types
    DOCUMENT_INTELLIGENCE = "document_intelligence"
    SPEND_CONTROL = "spend_control"
    AR_COLLECTIONS = "ar_collections"
    RISK_COMPLIANCE = "risk_compliance"
    TREASURY_CASH = "treasury_cash"
    TAX_COMPLIANCE = "tax_compliance"
    FINANCIAL_REPORTING = "financial_reporting"
    PAYMENT_RUN = "payment_run"
    BUDGETING = "budgeting"


class ToolOutput(BaseModel):
    tool_type: ToolType
    decision: str
    confidence: float
    reasoning: str
    actions_taken: list[str]
    output_data: dict


class BaseTool(ABC):
    """
    Abstract base for all Clendan financial AI tools.
    Each tool is a sub-agent dispatched directly to its arq job.
    """
    TOOL_TYPE: ToolType
    REQUIRED_TOOLS: list[str] = []
    VERSION: int = 1

    @abstractmethod
    async def execute(self, input_data: dict, tenant_id: str) -> ToolOutput:
        """
        Execute the tool task.
        Mandatory flow: receive → validate → execute → policy check → output → audit
        """
        ...
