'use client'

import { useState, useCallback } from 'react'
import { useAuth } from '@clerk/nextjs'
import { TEST_PAYLOADS } from './workerTestPayloads'
import type { TestResult } from './WorkerTestResult'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function useRunTest(workerId: string, workerType: string) {
  const { getToken } = useAuth()
  const [running, setRunning]         = useState(false)
  const [result, setResult]           = useState<TestResult | null>(null)

  const run = useCallback(async () => {
    setRunning(true)
    setResult(null)
    try {
      const token = await getToken()
      const testPayload = TEST_PAYLOADS[workerType]
      if (!testPayload) {
        setResult({ decision: 'failed', confidence: null, error: 'No test payload defined for this worker type.' })
        return
      }
      const res = await fetch(`${API}/v1/events`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Idempotency-Key': `test-${workerId}-${Date.now()}`,
        },
        body: JSON.stringify({ ...testPayload, worker_id: workerId }),
      })
      if (!res.ok) {
        setResult({ decision: 'failed', confidence: null, error: `Request failed (${res.status})` })
        return
      }
      const json = await res.json()
      setResult({ decision: json.data?.decision ?? 'queued', confidence: json.data?.confidence ?? null })
    } catch {
      setResult({ decision: 'failed', confidence: null, error: 'Could not reach the backend.' })
    } finally {
      setRunning(false)
    }
  }, [getToken, workerId, workerType])

  const dismiss = useCallback(() => setResult(null), [])

  return { run, running, result, dismiss }
}
