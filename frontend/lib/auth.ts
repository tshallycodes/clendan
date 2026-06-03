import { auth } from '@clerk/nextjs/server'

export async function getAuthHeaders(): Promise<Record<string, string>> {
  const session = await auth()
  const token = await session.getToken()
  if (!token) {
    throw new Error('Not authenticated')
  }
  return {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  }
}

export async function getBackendToken(): Promise<string | null> {
  const session = await auth()
  return session.getToken()
}
