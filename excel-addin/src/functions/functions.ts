/* global CustomFunctions, OfficeRuntime */

const API_BASE = "https://api.clendan.com";
const API_KEY_STORAGE_KEY = "clendan_api_key";

async function getApiKey(): Promise<string> {
  const key = await OfficeRuntime.storage.getItem(API_KEY_STORAGE_KEY);
  return key ?? "";
}

function generateIdempotencyKey(): string {
  return Math.random().toString(36).substr(2, 9);
}

/**
 * Categorises a transaction description using Clendan AI.
 * @customfunction
 * @param transactionDescription The transaction description to categorise
 * @returns Category string from the AI Accountant worker
 */
export async function CATEGORISE(transactionDescription: string): Promise<string> {
  const key = await getApiKey();
  if (!key) {
    return "Not connected — add API key in task pane";
  }

  try {
    const response = await fetch(`${API_BASE}/v1/execute`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
        "Idempotency-Key": generateIdempotencyKey(),
      },
      body: JSON.stringify({
        worker: "ai_accountant",
        payload: { transaction_description: transactionDescription },
      }),
    });

    const body = await response.json();

    if (!response.ok) {
      return `Error: ${body.error ?? response.statusText}`;
    }

    return (body.data?.decision as string) ?? "processed";
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return `Error: ${message}`;
  }
}

/**
 * Processes an invoice document URL using Clendan AI.
 * @customfunction
 * @param documentUrl The URL of the invoice document to process
 * @returns Processing result string with decision and execution ID
 */
export async function PROCESS_INVOICE(documentUrl: string): Promise<string> {
  const key = await getApiKey();
  if (!key) {
    return "Not connected — add API key in task pane";
  }

  try {
    const response = await fetch(`${API_BASE}/v1/execute`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
        "Idempotency-Key": generateIdempotencyKey(),
      },
      body: JSON.stringify({
        worker: "invoice_processing",
        payload: { document_url: documentUrl },
      }),
    });

    const body = await response.json();

    if (!response.ok) {
      return `Error: ${body.error ?? response.statusText}`;
    }

    const decision = (body.data?.decision as string) ?? "processed";
    const executionId = (body.data?.execution_id as string) ?? "";
    return executionId ? `${decision} (id:${executionId})` : decision;
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return `Error: ${message}`;
  }
}
