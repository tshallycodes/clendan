import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { TransactionsClient, type Transaction } from '@/components/dashboard/transactions/TransactionsClient'

interface TransactionsData {
  transactions: Transaction[]
  total: number
  total_out_minor: number
  total_in_minor: number
}

export default async function TransactionsPage() {
  let transactions: Transaction[] = []
  let total = 0
  let totalOutMinor = 0
  let totalInMinor = 0
  const ytdStart = `${new Date().getFullYear()}-01-01`
  try {
    const token = await getBackendToken()
    if (token) {
      const data = await apiGet<TransactionsData>(`/v1/transactions?limit=50&from_date=${ytdStart}`, token)
      transactions = data.transactions ?? []
      total = data.total ?? transactions.length
      totalOutMinor = data.total_out_minor ?? 0
      totalInMinor = data.total_in_minor ?? 0
    }
  } catch { /* backend not running */ }

  return (
    <TransactionsClient
      initialTransactions={transactions}
      total={total}
      totalOutMinor={totalOutMinor}
      totalInMinor={totalInMinor}
      fromDate={ytdStart}
    />
  )
}
