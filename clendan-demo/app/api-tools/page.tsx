import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { ApiCodeBlock } from "@/components/ui/ApiCodeBlock";
import { API_TOOLS } from "@/lib/constants";

const CODE_SAMPLES: Record<string, { python?: string; nodejs?: string; curl?: string }> = {
  "invoice-parser": {
    python: `import requests

response = requests.post(
    "https://api.clendan.com/v1/parse/invoice",
    headers={"Authorization": "Bearer YOUR_API_KEY"},
    files={"file": open("invoice.pdf", "rb")}
)

data = response.json()
print(data["vendor"])       # "Acme Supplies Ltd"
print(data["total_amount"]) # 1240.00
print(data["confidence"])   # 0.97`,
    nodejs: `const FormData = require('form-data');
const fs = require('fs');

const form = new FormData();
form.append('file', fs.createReadStream('invoice.pdf'));

const response = await fetch('https://api.clendan.com/v1/parse/invoice', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY',
    ...form.getHeaders()
  },
  body: form
});

const data = await response.json();
console.log(data.vendor);        // "Acme Supplies Ltd"
console.log(data.total_amount);  // 1240.00`,
    curl: `curl -X POST https://api.clendan.com/v1/parse/invoice \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -F "file=@invoice.pdf"`,
  },
  "receipt-ocr": {
    python: `import requests

response = requests.post(
    "https://api.clendan.com/v1/parse/receipt",
    headers={"Authorization": "Bearer YOUR_API_KEY"},
    json={
        "image_url": "https://storage.example.com/receipt.jpg",
        "policy_id": "policy-expense-001"
    }
)

data = response.json()
print(data["merchant"])   # "Costa Coffee"
print(data["total"])      # 4.75
print(data["decision"])   # "AUTO_APPROVE"`,
    curl: `curl -X POST https://api.clendan.com/v1/parse/receipt \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"image_url": "https://...receipt.jpg", "policy_id": "policy-001"}'`,
  },
  "document-reconciliation": {
    python: `import requests

response = requests.post(
    "https://api.clendan.com/v1/reconcile",
    headers={"Authorization": "Bearer YOUR_API_KEY"},
    json={
        "invoice_id": "INV-2026-0041",
        "po_number": "PO-2026-0089",
        "grn_number": "GRN-2026-0055"
    }
)

data = response.json()
print(data["status"])        # "MATCHED"
print(data["discrepancies"]) # []`,
    curl: `curl -X POST https://api.clendan.com/v1/reconcile \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"invoice_id": "INV-2026-0041", "po_number": "PO-2026-0089"}'`,
  },
  "fraud-signal": {
    python: `import requests

response = requests.post(
    "https://api.clendan.com/v1/fraud/score",
    headers={"Authorization": "Bearer YOUR_API_KEY"},
    json={
        "amount": 12400,
        "currency": "GBP",
        "vendor_id": "vendor-unknown",
        "payment_method": "bank_transfer"
    }
)

data = response.json()
print(data["score"])      # 94
print(data["action"])     # "BLOCK"
print(data["signals"])    # ["new_vendor", "unusual_time", ...]`,
    curl: `curl -X POST https://api.clendan.com/v1/fraud/score \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"amount": 12400, "currency": "GBP", "vendor_id": "vendor-unknown"}'`,
  },
  "contract-extraction": {
    python: `import requests

response = requests.post(
    "https://api.clendan.com/v1/parse/contract",
    headers={"Authorization": "Bearer YOUR_API_KEY"},
    files={"file": open("contract.pdf", "rb")}
)

data = response.json()
print(data["parties"])        # ["Clendan Ltd", "Acme Corp"]
print(data["payment_terms"])  # "Net 30"
print(data["renewal_date"])   # "2027-01-01"`,
    curl: `curl -X POST https://api.clendan.com/v1/parse/contract \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -F "file=@contract.pdf"`,
  },
};

export default function ApiToolsPage() {
  return (
    <>
      <Navbar />
      <main className="pt-20 min-h-screen">
        {/* Hero */}
        <div className="max-w-4xl mx-auto px-6 py-20 text-center border-b border-brand-border">
          <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-3">API Tools</p>
          <h1 className="font-heading text-4xl md:text-5xl font-extrabold text-brand-text mb-4">
            5 APIs. Plug Into Any Stack.
          </h1>
          <p className="text-brand-muted font-mono text-sm max-w-xl mx-auto">
            Use Clendan APIs standalone or as the backbone of your AI workers.
            All endpoints are RESTful, authenticated with Bearer tokens, and return structured JSON.
          </p>
        </div>

        <div className="max-w-5xl mx-auto px-6 py-16 space-y-24">
          {API_TOOLS.map((tool) => {
            const samples = CODE_SAMPLES[tool.id] ?? {};
            return (
              <section key={tool.id} className="border-t border-brand-border pt-16 first:border-0 first:pt-0">
                <div className="mb-6">
                  <p className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-1">API Tool</p>
                  <h2 className="font-heading text-2xl font-bold text-brand-text mb-2">{tool.name}</h2>
                  <div className="font-mono text-sm text-brand-green bg-[rgba(0,200,83,0.06)] border border-[rgba(0,200,83,0.15)] px-3 py-1.5 rounded-sm inline-block mb-3">
                    {tool.endpoint}
                  </div>
                  <p className="text-brand-muted font-mono text-sm leading-relaxed max-w-2xl">{tool.description}</p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                  <ApiCodeBlock samples={samples} />

                  <div>
                    <div className="text-[10px] font-mono text-brand-muted uppercase tracking-widest mb-3">Use Cases</div>
                    <ul className="space-y-2">
                      {tool.useCases.map((uc) => (
                        <li key={uc} className="flex items-start gap-2 text-xs font-mono text-brand-text">
                          <span className="text-brand-green mt-0.5">→</span>
                          {uc}
                        </li>
                      ))}
                    </ul>
                    <button className="mt-6 text-xs font-mono text-brand-muted border border-brand-border px-4 py-2 rounded-sm hover:text-brand-text hover:border-brand-text transition-colors">
                      View Docs →
                    </button>
                  </div>
                </div>
              </section>
            );
          })}
        </div>
      </main>
      <Footer />
    </>
  );
}
