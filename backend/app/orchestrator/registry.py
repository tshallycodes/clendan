"""
Worker registry — maps WorkerType to worker class.
Orchestrator never imports workers directly; it calls them through this registry.
"""
from app.workers.base import BaseWorker, WorkerOutput, WorkerType
from app.workers.collections import CollectionsWorker
from app.workers.compliance import ComplianceWorker
from app.workers.credit_underwriting import CreditUnderwritingWorker
from app.workers.expense_control import ExpenseControlWorker
from app.workers.fraud_detection import FraudDetectionWorker
from app.workers.reconciliation import ReconciliationWorker
from app.workers.revenue_recognition import RevenueRecognitionWorker
from app.workers.treasury import TreasuryWorker


class InvoiceProcessingWorkerStub(BaseWorker):
    """Thin stub — real implementation runs via arq queue."""
    WORKER_TYPE = WorkerType.INVOICE_PROCESSING
    REQUIRED_TOOLS = ["invoice_ingestion_api", "ocr_document_tool", "accounting_api"]
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> WorkerOutput:
        return WorkerOutput(
            worker_type=self.WORKER_TYPE,
            decision="queued",
            confidence=1.0,
            reasoning="Routed to arq queue for async execution",
            actions_taken=[],
            output_data={},
        )


class AccountantWorkerStub(BaseWorker):
    """Thin stub — real implementation runs via arq queue."""
    WORKER_TYPE = WorkerType.ACCOUNTANT
    REQUIRED_TOOLS = ["bank_transaction_api", "accounting_ledger_api", "invoice_system_api"]
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> WorkerOutput:
        return WorkerOutput(
            worker_type=self.WORKER_TYPE,
            decision="queued",
            confidence=1.0,
            reasoning="Routed to arq queue for async execution",
            actions_taken=[],
            output_data={},
        )


class ReceiptProcessingWorkerStub(BaseWorker):
    """Thin stub — real implementation runs via arq queue."""
    WORKER_TYPE = WorkerType.RECEIPT_PROCESSING
    REQUIRED_TOOLS = ["receipt_ocr_tool", "policy_engine_api"]
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> WorkerOutput:
        return WorkerOutput(
            worker_type=self.WORKER_TYPE,
            decision="queued",
            confidence=1.0,
            reasoning="Routed to arq queue for async execution",
            actions_taken=[],
            output_data={},
        )


WORKER_REGISTRY: dict[WorkerType, type[BaseWorker]] = {
    WorkerType.INVOICE_PROCESSING: InvoiceProcessingWorkerStub,
    WorkerType.ACCOUNTANT: AccountantWorkerStub,
    WorkerType.RECEIPT_PROCESSING: ReceiptProcessingWorkerStub,
    WorkerType.RECONCILIATION: ReconciliationWorker,
    WorkerType.EXPENSE_CONTROL: ExpenseControlWorker,
    WorkerType.COLLECTIONS: CollectionsWorker,
    WorkerType.FRAUD_DETECTION: FraudDetectionWorker,
    WorkerType.TREASURY: TreasuryWorker,
    WorkerType.REVENUE_RECOGNITION: RevenueRecognitionWorker,
    WorkerType.CREDIT_UNDERWRITING: CreditUnderwritingWorker,
    WorkerType.COMPLIANCE: ComplianceWorker,
}


def get_worker(worker_type: WorkerType) -> BaseWorker:
    """Instantiate and return a worker for the given type."""
    cls = WORKER_REGISTRY.get(worker_type)
    if cls is None:
        raise ValueError(f"No worker registered for type: {worker_type}")
    return cls()
