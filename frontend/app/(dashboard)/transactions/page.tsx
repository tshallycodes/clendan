import { getBackendToken } from '@/lib/auth'
import { apiGet } from '@/lib/api'
import { TransactionsClient, type Transaction } from '@/components/dashboard/transactions/TransactionsClient'

interface TransactionsData {
  transactions: Transaction[]
  total: number
}

export default async function TransactionsPage() {
  let transactions: Transaction[] = []
  let total = 0
  try {
    const token = await getBackendToken()
    if (token) {
      const data = await apiGet<TransactionsData>('/v1/integrations/plaid/transactions?limit=50', token)
      transactions = data.transactions ?? []
      total = data.total ?? transactions.length
    }
  } catch { /* backend not running */ }

  return <TransactionsClient initialTransactions={transactions} total={total} />
}
