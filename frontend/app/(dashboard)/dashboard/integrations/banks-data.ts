export interface BankDef {
  id: string
  name: string
  abbr: string
  color: string
  domain: string
  provider: 'plaid' | 'truelayer'
  institution_id?: string
  region: 'us' | 'uk' | 'eu'
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
  // UK Banks (via Plaid)
  { id: 'barclays', name: 'Barclays', abbr: 'BARC', color: '#00AEEF', domain: 'barclays.co.uk', provider: 'plaid', region: 'uk' },
  { id: 'hsbc', name: 'HSBC', abbr: 'HSBC', color: '#DB0011', domain: 'hsbc.com', provider: 'plaid', region: 'uk' },
  { id: 'lloyds', name: 'Lloyds', abbr: 'LLOY', color: '#006A4D', domain: 'lloydsbank.com', provider: 'plaid', region: 'uk' },
  { id: 'natwest', name: 'NatWest', abbr: 'NW', color: '#6F2C91', domain: 'natwest.com', provider: 'plaid', region: 'uk' },
  { id: 'santander', name: 'Santander', abbr: 'SAN', color: '#EA1D25', domain: 'santander.co.uk', provider: 'plaid', region: 'uk' },
  { id: 'halifax', name: 'Halifax', abbr: 'HAL', color: '#009FE3', domain: 'halifax.co.uk', provider: 'plaid', region: 'uk' },
  { id: 'nationwide', name: 'Nationwide', abbr: 'NBS', color: '#103C75', domain: 'nationwide.co.uk', provider: 'plaid', region: 'uk' },
  { id: 'monzo', name: 'Monzo', abbr: 'MNZ', color: '#FF3366', domain: 'monzo.com', provider: 'plaid', region: 'uk' },
  { id: 'starling', name: 'Starling', abbr: 'SB', color: '#6935AA', domain: 'starlingbank.com', provider: 'plaid', region: 'uk' },
  { id: 'revolut', name: 'Revolut', abbr: 'REV', color: '#3D3D3D', domain: 'revolut.com', provider: 'plaid', region: 'uk' },
  { id: 'first_direct', name: 'First Direct', abbr: 'FD', color: '#1A1A1A', domain: 'firstdirect.com', provider: 'plaid', region: 'uk' },
  // EU Banks (TrueLayer only)
  { id: 'n26', name: 'N26', abbr: 'N26', color: '#30373E', domain: 'n26.com', provider: 'truelayer', region: 'eu' },
  { id: 'ing', name: 'ING', abbr: 'ING', color: '#FF6200', domain: 'ing.com', provider: 'truelayer', region: 'eu' },
  { id: 'bunq', name: 'Bunq', abbr: 'BUNQ', color: '#00B9A9', domain: 'bunq.com', provider: 'truelayer', region: 'eu' },
  { id: 'deutsche', name: 'Deutsche Bank', abbr: 'DB', color: '#0018A8', domain: 'db.com', provider: 'truelayer', region: 'eu' },
]
