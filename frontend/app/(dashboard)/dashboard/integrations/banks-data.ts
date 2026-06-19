export interface BankDef {
  id: string
  name: string
  abbr: string
  color: string
  domain: string
  provider: 'plaid' | 'truelayer' | 'mono'
  institution_id?: string
  region: 'us' | 'eu' | 'africa'
}

export const BANKS: BankDef[] = [
  // US Banks (via Plaid)
  { id: 'chase', name: 'Chase', abbr: 'CH', color: '#117ACA', domain: 'chase.com', provider: 'plaid', institution_id: 'ins_3', region: 'us' },
  { id: 'bofa', name: 'Bank of America', abbr: 'BoA', color: '#E31837', domain: 'bankofamerica.com', provider: 'plaid', institution_id: 'ins_4', region: 'us' },
  { id: 'wells_fargo', name: 'Wells Fargo', abbr: 'WF', color: '#CC0000', domain: 'wellsfargo.com', provider: 'plaid', institution_id: 'ins_5', region: 'us' },
  { id: 'citi', name: 'Citibank', abbr: 'CITI', color: '#003B70', domain: 'citi.com', provider: 'plaid', institution_id: 'ins_7', region: 'us' },
  { id: 'capital_one', name: 'Capital One', abbr: 'C1', color: '#004877', domain: 'capitalone.com', provider: 'plaid', region: 'us' },
  { id: 'usbank', name: 'US Bank', abbr: 'USB', color: '#AC145A', domain: 'usbank.com', provider: 'plaid', institution_id: 'ins_1', region: 'us' },
  { id: 'pnc', name: 'PNC Bank', abbr: 'PNC', color: '#F58025', domain: 'pnc.com', provider: 'plaid', institution_id: 'ins_8', region: 'us' },
  { id: 'td', name: 'TD Bank', abbr: 'TD', color: '#34B233', domain: 'tdbank.com', provider: 'plaid', institution_id: 'ins_9', region: 'us' },
  { id: 'amex', name: 'Amex', abbr: 'AMEX', color: '#2E77BC', domain: 'americanexpress.com', provider: 'plaid', institution_id: 'ins_10', region: 'us' },
  { id: 'usaa', name: 'USAA', abbr: 'USAA', color: '#003087', domain: 'usaa.com', provider: 'plaid', institution_id: 'ins_11', region: 'us' },
  { id: 'ally', name: 'Ally Bank', abbr: 'ALLY', color: '#6A3290', domain: 'ally.com', provider: 'plaid', region: 'us' },
  { id: 'revolut-us', name: 'Revolut', abbr: 'REV', color: '#3D3D3D', domain: 'revolut.com', provider: 'plaid', region: 'us' },
  // EU & UK Banks (via TrueLayer Open Banking)
  { id: 'barclays', name: 'Barclays', abbr: 'BARC', color: '#00AEEF', domain: 'barclays.co.uk', provider: 'truelayer', region: 'eu' },
  { id: 'hsbc', name: 'HSBC', abbr: 'HSBC', color: '#DB0011', domain: 'hsbc.com', provider: 'truelayer', region: 'eu' },
  { id: 'lloyds', name: 'Lloyds', abbr: 'LLOY', color: '#006A4D', domain: 'lloydsbank.com', provider: 'truelayer', region: 'eu' },
  { id: 'natwest', name: 'NatWest', abbr: 'NW', color: '#6F2C91', domain: 'natwest.com', provider: 'truelayer', region: 'eu' },
  { id: 'monzo', name: 'Monzo', abbr: 'MNZ', color: '#FF3366', domain: 'monzo.com', provider: 'truelayer', region: 'eu' },
  { id: 'starling', name: 'Starling', abbr: 'SB', color: '#6935AA', domain: 'starlingbank.com', provider: 'truelayer', region: 'eu' },
  { id: 'revolut', name: 'Revolut', abbr: 'REV', color: '#3D3D3D', domain: 'revolut.com', provider: 'truelayer', region: 'eu' },
  { id: 'n26', name: 'N26', abbr: 'N26', color: '#30373E', domain: 'n26.com', provider: 'truelayer', region: 'eu' },
  { id: 'ing', name: 'ING', abbr: 'ING', color: '#FF6200', domain: 'ing.com', provider: 'truelayer', region: 'eu' },
  { id: 'bunq', name: 'Bunq', abbr: 'BUNQ', color: '#00B9A9', domain: 'bunq.com', provider: 'truelayer', region: 'eu' },
  { id: 'deutsche', name: 'Deutsche Bank', abbr: 'DB', color: '#0018A8', domain: 'db.com', provider: 'truelayer', region: 'eu' },
  // African Banks (via Mono)
  { id: 'gtbank', name: 'GTBank', abbr: 'GTB', color: '#F3830A', domain: 'gtbank.com', provider: 'mono', region: 'africa' },
  { id: 'zenith', name: 'Zenith Bank', abbr: 'ZEN', color: '#CC0000', domain: 'zenithbank.com', provider: 'mono', region: 'africa' },
  { id: 'access', name: 'Access Bank', abbr: 'ACC', color: '#F5831F', domain: 'accessbankplc.com', provider: 'mono', region: 'africa' },
  { id: 'firstbank', name: 'First Bank', abbr: 'FBN', color: '#003087', domain: 'firstbanknigeria.com', provider: 'mono', region: 'africa' },
  { id: 'uba', name: 'UBA', abbr: 'UBA', color: '#CC0000', domain: 'ubagroup.com', provider: 'mono', region: 'africa' },
  { id: 'sterling', name: 'Sterling Bank', abbr: 'STB', color: '#CC0000', domain: 'sterlingbank.com', provider: 'mono', region: 'africa' },
  { id: 'stanbic_ng', name: 'Stanbic IBTC', abbr: 'SIB', color: '#009BD7', domain: 'stanbicibtcbank.com', provider: 'mono', region: 'africa' },
  { id: 'gcb', name: 'GCB Bank', abbr: 'GCB', color: '#006B3E', domain: 'gcbbank.com.gh', provider: 'mono', region: 'africa' },
  { id: 'ecobank', name: 'Ecobank', abbr: 'ECO', color: '#003399', domain: 'ecobank.com', provider: 'mono', region: 'africa' },
  { id: 'equity', name: 'Equity Bank', abbr: 'EQB', color: '#E31837', domain: 'equitybank.co.ke', provider: 'mono', region: 'africa' },
  { id: 'kcb', name: 'KCB Bank', abbr: 'KCB', color: '#006600', domain: 'kcbbankgroup.com', provider: 'mono', region: 'africa' },
  { id: 'coop_ke', name: 'Co-op Bank', abbr: 'CO-OP', color: '#0B5C2A', domain: 'co-opbank.co.ke', provider: 'mono', region: 'africa' },
]
