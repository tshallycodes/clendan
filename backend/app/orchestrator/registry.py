"""
Tool registry — maps ToolType to tool class.
Orchestrator never imports tools directly; it calls them through this registry.
"""
from app.tools.base import BaseTool, ToolOutput, ToolType
from app.tools.collections import CollectionsTool
from app.tools.compliance import ComplianceTool
from app.tools.credit_underwriting import CreditUnderwritingTool
from app.tools.expense_control import ExpenseControlTool
from app.tools.fraud_detection import FraudDetectionTool
from app.tools.reconciliation import ReconciliationTool
from app.tools.revenue_recognition import RevenueRecognitionTool
from app.tools.treasury import TreasuryTool


class InvoiceProcessingToolStub(BaseTool):
    """Thin stub — real implementation runs via arq queue."""
    TOOL_TYPE = ToolType.INVOICE_PROCESSING
    REQUIRED_TOOLS = ["invoice_ingestion_api", "ocr_document_tool", "accounting_api"]
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> ToolOutput:
        return ToolOutput(
            tool_type=self.TOOL_TYPE,
            decision="queued",
            confidence=1.0,
            reasoning="Routed to arq queue for async execution",
            actions_taken=[],
            output_data={},
        )


class AccountantToolStub(BaseTool):
    """Thin stub — real implementation runs via arq queue."""
    TOOL_TYPE = ToolType.ACCOUNTANT
    REQUIRED_TOOLS = ["bank_transaction_api", "accounting_ledger_api", "invoice_system_api"]
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> ToolOutput:
        return ToolOutput(
            tool_type=self.TOOL_TYPE,
            decision="queued",
            confidence=1.0,
            reasoning="Routed to arq queue for async execution",
            actions_taken=[],
            output_data={},
        )


class ReceiptProcessingToolStub(BaseTool):
    """Thin stub — real implementation runs via arq queue."""
    TOOL_TYPE = ToolType.RECEIPT_PROCESSING
    REQUIRED_TOOLS = ["receipt_ocr_tool", "policy_engine_api"]
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> ToolOutput:
        return ToolOutput(
            tool_type=self.TOOL_TYPE,
            decision="queued",
            confidence=1.0,
            reasoning="Routed to arq queue for async execution",
            actions_taken=[],
            output_data={},
        )


WORKER_REGISTRY: dict[ToolType, type[BaseTool]] = {
    ToolType.INVOICE_PROCESSING: InvoiceProcessingToolStub,
    ToolType.ACCOUNTANT: AccountantToolStub,
    ToolType.RECEIPT_PROCESSING: ReceiptProcessingToolStub,
    ToolType.RECONCILIATION: ReconciliationTool,
    ToolType.EXPENSE_CONTROL: ExpenseControlTool,
    ToolType.COLLECTIONS: CollectionsTool,
    ToolType.FRAUD_DETECTION: FraudDetectionTool,
    ToolType.TREASURY: TreasuryTool,
    ToolType.REVENUE_RECOGNITION: RevenueRecognitionTool,
    ToolType.CREDIT_UNDERWRITING: CreditUnderwritingTool,
    ToolType.COMPLIANCE: ComplianceTool,
}


def get_tool(tool_type: ToolType) -> BaseTool:
    """Instantiate and return a tool for the given type."""
    cls = WORKER_REGISTRY.get(tool_type)
    if cls is None:
        raise ValueError(f"No tool registered for type: {tool_type}")
    return cls()
