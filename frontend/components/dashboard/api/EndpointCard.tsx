import { CodeBlock } from './CodeBlock'

type Method = 'GET' | 'POST' | 'PUT' | 'DELETE'

const METHOD_COLORS: Record<Method, string> = {
  GET:    'text-[#00a8cc] border-[#00a8cc]/30 bg-[#00a8cc]/08',
  POST:   'text-brand-green border-brand-green/30 bg-brand-green/08',
  PUT:    'text-[#f5a623] border-[#f5a623]/30 bg-[#f5a623]/08',
  DELETE: 'text-[#ff4d6d] border-[#ff4d6d]/30 bg-[#ff4d6d]/08',
}

interface Header { name: string; required: boolean; description: string }

interface EndpointCardProps {
  method: Method
  path: string
  description: string
  headers?: Header[]
  example: string
  exampleLang?: string
}

export function EndpointCard({ method, path, description, headers, example, exampleLang }: EndpointCardProps) {
  return (
    <div className="border border-brand-border rounded-sm overflow-hidden">
      <div className="bg-brand-surface px-5 py-4 flex items-start gap-3">
        <span className={`shrink-0 mt-0.5 text-[10px] font-body font-semibold px-2 py-0.5 rounded-sm border ${METHOD_COLORS[method]}`}>
          {method}
        </span>
        <div className="flex-1 min-w-0">
          <code className="text-sm font-body text-brand-text break-all">{path}</code>
          <p className="text-xs font-body text-brand-muted mt-1">{description}</p>
        </div>
      </div>

      {headers && headers.length > 0 && (
        <div className="border-t border-brand-border px-5 py-3 bg-brand-bg">
          <p className="text-[10px] font-body uppercase tracking-widest text-brand-muted mb-2">Required headers</p>
          <div className="space-y-1">
            {headers.map(h => (
              <div key={h.name} className="flex items-baseline gap-3 text-xs font-body">
                <code className="text-[#f5a623] shrink-0">{h.name}</code>
                <span className="text-brand-muted">{h.description}</span>
                {h.required && <span className="text-[#ff4d6d] text-[10px] shrink-0">required</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="border-t border-brand-border">
        <CodeBlock code={example} lang={exampleLang ?? 'bash'} />
      </div>
    </div>
  )
}
