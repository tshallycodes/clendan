import { cookies } from 'next/headers'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// When a firm member has switched to a client tenant, the switcher stores it in a same-site
// cookie. Forward it as X-Clendan-Client so the backend (resolve_active_context) can re-scope
// the request to that client. Absent/failed cookie read => normal own-tenant behaviour.
async function activeClientHeaders(): Promise<Record<string, string>> {
  try {
    const active = (await cookies()).get('clendan_active_client')?.value
    return active ? { 'X-Clendan-Client': active } : {}
  } catch {
    return {}
  }
}

export async function apiGet<T = unknown>(path: string, token: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...(await activeClientHeaders()),
    },
    cache: 'no-store',
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`)
  const json = await res.json()
  return json.data as T
}

export async function apiPost<T = unknown>(path: string, body: unknown, token: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...(await activeClientHeaders()),
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`)
  const json = await res.json()
  return json.data as T
}
