"""
Base tool interface for all Clendan financial AI tools.
All tools subclass BaseTool and implement execute().
The Financial Orchestrator invokes tools exclusively through this interface.
Tools never call each other directly — all coordination flows through the Orchestrator.
"""
from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel


class ToolType(str, Enum):
    INVOICE_PROCESSING = "invoice_processing"
    ACCOUNTANT = "ai_accountant"
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
    Tools are sub-agents called as tools by the Financial Orchestrator.
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
