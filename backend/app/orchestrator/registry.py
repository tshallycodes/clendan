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
from app.tools.tax_compliance import TaxComplianceTool
from app.tools.financial_reporting import FinancialReportingTool
from app.tools.payment_run import PaymentRunTool
from app.tools.budgeting import BudgetingTool
from app.tools.treasury import TreasuryTool

_QUEUED = ToolOutput(
    tool_type=ToolType.RECONCILIATION,  # placeholder overridden per stub
    decision="queued",
    confidence=1.0,
    reasoning="Routed to arq queue for async execution",
    actions_taken=[],
    output_data={},
)


def _queued(tool_type: ToolType) -> ToolOutput:
    return ToolOutput(
        tool_type=tool_type,
        decision="queued",
        confidence=1.0,
        reasoning="Routed to arq queue for async execution",
        actions_taken=[],
        output_data={},
    )


class InvoiceProcessingToolStub(BaseTool):
    TOOL_TYPE = ToolType.INVOICE_PROCESSING
    REQUIRED_TOOLS = ["invoice_ingestion_api", "ocr_document_tool", "accounting_api"]
    VERSION = 1

    async def execute(self, _input_data: dict, _tenant_id: str) -> ToolOutput:
        return _queued(self.TOOL_TYPE)


class AccountantToolStub(BaseTool):
    TOOL_TYPE = ToolType.ACCOUNTANT
    REQUIRED_TOOLS = ["bank_transaction_api", "accounting_ledger_api", "invoice_system_api"]
    VERSION = 1

    async def execute(self, _input_data: dict, _tenant_id: str) -> ToolOutput:
        return _queued(self.TOOL_TYPE)


class ReceiptProcessingToolStub(BaseTool):
    TOOL_TYPE = ToolType.RECEIPT_PROCESSING
    REQUIRED_TOOLS = ["receipt_ocr_tool", "policy_engine_api"]
    VERSION = 1

    async def execute(self, _input_data: dict, _tenant_id: str) -> ToolOutput:
        return _queued(self.TOOL_TYPE)


class DocumentIntelligenceToolStub(BaseTool):
    TOOL_TYPE = ToolType.DOCUMENT_INTELLIGENCE
    REQUIRED_TOOLS = ["ocr_document_tool", "invoice_ingestion_api", "accounting_api"]
    VERSION = 1

    async def execute(self, _input_data: dict, _tenant_id: str) -> ToolOutput:
        return _queued(self.TOOL_TYPE)


class SpendControlToolStub(BaseTool):
    TOOL_TYPE = ToolType.SPEND_CONTROL
    REQUIRED_TOOLS = ["accounting_api", "policy_engine_api"]
    VERSION = 1

    async def execute(self, _input_data: dict, _tenant_id: str) -> ToolOutput:
        return _queued(self.TOOL_TYPE)


class ARCollectionsToolStub(BaseTool):
    TOOL_TYPE = ToolType.AR_COLLECTIONS
    REQUIRED_TOOLS = ["accounting_api", "communication_api"]
    VERSION = 1

    async def execute(self, _input_data: dict, _tenant_id: str) -> ToolOutput:
        return _queued(self.TOOL_TYPE)


class RiskComplianceToolStub(BaseTool):
    TOOL_TYPE = ToolType.RISK_COMPLIANCE
    REQUIRED_TOOLS = ["transaction_api", "regulatory_api"]
    VERSION = 1

    async def execute(self, _input_data: dict, _tenant_id: str) -> ToolOutput:
        return _queued(self.TOOL_TYPE)


class TreasuryCashToolStub(BaseTool):
    TOOL_TYPE = ToolType.TREASURY_CASH
    REQUIRED_TOOLS = ["banking_api", "accounting_api"]
    VERSION = 1

    async def execute(self, _input_data: dict, _tenant_id: str) -> ToolOutput:
        return _queued(self.TOOL_TYPE)


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
    ToolType.DOCUMENT_INTELLIGENCE: DocumentIntelligenceToolStub,
    ToolType.SPEND_CONTROL: SpendControlToolStub,
    ToolType.AR_COLLECTIONS: ARCollectionsToolStub,
    ToolType.RISK_COMPLIANCE: RiskComplianceToolStub,
    ToolType.TREASURY_CASH: TreasuryCashToolStub,
    ToolType.TAX_COMPLIANCE: TaxComplianceTool,
    ToolType.FINANCIAL_REPORTING: FinancialReportingTool,
    ToolType.PAYMENT_RUN: PaymentRunTool,
    ToolType.BUDGETING: BudgetingTool,
}


def get_tool(tool_type: ToolType) -> BaseTool:
    """Instantiate and return a tool for the given type."""
    cls = WORKER_REGISTRY.get(tool_type)
    if cls is None:
        raise ValueError(f"No tool registered for type: {tool_type}")
    return cls()
