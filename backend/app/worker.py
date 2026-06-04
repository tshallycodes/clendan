"""
arq worker process — runs background jobs via Redis.
Start with: python -m arq app.worker.WorkerSettings
"""
from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.db import connect_db, disconnect_db
from app.core.logging import get_logger
from app.integrations.quickbooks.sync import sync_quickbooks_connection
from app.integrations.plaid.sync import sync_plaid_transactions, reconcile_plaid_transactions
from app.workers.ai_accountant import run_ai_accountant
from app.workers.invoice_processing import run_invoice_job
from app.workers.receipt_processing import run_receipt_job
from app.api.v1.parse.invoice import run_parse_invoice_job
from app.api.v1.parse.receipt import run_parse_receipt_job

logger = get_logger(__name__)


async def startup(ctx: dict) -> None:
    await connect_db()
    logger.info("arq worker started")


async def shutdown(ctx: dict) -> None:
    await disconnect_db()
    logger.info("arq worker stopped")


class WorkerSettings:
    functions = [sync_quickbooks_connection, sync_plaid_transactions, reconcile_plaid_transactions, run_ai_accountant, run_invoice_job, run_receipt_job, run_parse_invoice_job, run_parse_receipt_job]
    on_startup = startup
    on_shutdown = shutdown

    @property
    def redis_settings(self) -> RedisSettings:
        settings = get_settings()
        return RedisSettings.from_dsn(settings.redis_url)

    max_jobs = 10
    job_timeout = 300
    max_tries = 3
