export interface Currency {
  code: string
  name: string
  symbol: string
  region: string
  decimals: number  // ISO 4217 display decimal places
}

export const CURRENCIES: Currency[] = [
  // Americas
  { code: 'USD', name: 'US Dollar',                     symbol: '$',    region: 'Americas',     decimals: 2 },
  { code: 'CAD', name: 'Canadian Dollar',               symbol: 'CA$',  region: 'Americas',     decimals: 2 },
  { code: 'BRL', name: 'Brazilian Real',                symbol: 'R$',   region: 'Americas',     decimals: 2 },
  { code: 'MXN', name: 'Mexican Peso',                  symbol: 'MX$',  region: 'Americas',     decimals: 2 },
  { code: 'ARS', name: 'Argentine Peso',                symbol: 'AR$',  region: 'Americas',     decimals: 2 },
  { code: 'COP', name: 'Colombian Peso',                symbol: 'COP$', region: 'Americas',     decimals: 2 },
  { code: 'CLP', name: 'Chilean Peso',                  symbol: 'CLP$', region: 'Americas',     decimals: 0 },
  // Caribbean
  { code: 'JMD', name: 'Jamaican Dollar',               symbol: 'J$',   region: 'Caribbean',    decimals: 2 },
  { code: 'TTD', name: 'Trinidad & Tobago Dollar',      symbol: 'TT$',  region: 'Caribbean',    decimals: 2 },
  // Europe
  { code: 'EUR', name: 'Euro',                          symbol: '€',    region: 'Europe',       decimals: 2 },
  { code: 'GBP', name: 'British Pound',                 symbol: '£',    region: 'Europe',       decimals: 2 },
  { code: 'CHF', name: 'Swiss Franc',                   symbol: 'CHF',  region: 'Europe',       decimals: 2 },
  { code: 'SEK', name: 'Swedish Krona',                 symbol: 'kr',   region: 'Europe',       decimals: 2 },
  { code: 'NOK', name: 'Norwegian Krone',               symbol: 'kr',   region: 'Europe',       decimals: 2 },
  { code: 'PLN', name: 'Polish Zloty',                  symbol: 'zł',   region: 'Europe',       decimals: 2 },
  { code: 'TRY', name: 'Turkish Lira',                  symbol: '₺',    region: 'Europe',       decimals: 2 },
  { code: 'HUF', name: 'Hungarian Forint',              symbol: 'Ft',   region: 'Europe',       decimals: 2 },
  // Eastern Europe
  { code: 'CZK', name: 'Czech Koruna',                  symbol: 'Kč',   region: 'Eastern Europe', decimals: 2 },
  // Asia
  { code: 'JPY', name: 'Japanese Yen',                  symbol: '¥',    region: 'Asia',         decimals: 0 },
  { code: 'CNY', name: 'Chinese Yuan',                  symbol: '¥',    region: 'Asia',         decimals: 2 },
  { code: 'INR', name: 'Indian Rupee',                  symbol: '₹',    region: 'Asia',         decimals: 2 },
  { code: 'KRW', name: 'South Korean Won',              symbol: '₩',    region: 'Asia',         decimals: 0 },
  { code: 'SGD', name: 'Singapore Dollar',              symbol: 'S$',   region: 'Asia',         decimals: 2 },
  { code: 'HKD', name: 'Hong Kong Dollar',              symbol: 'HK$',  region: 'Asia',         decimals: 2 },
  { code: 'IDR', name: 'Indonesian Rupiah',             symbol: 'Rp',   region: 'Asia',         decimals: 0 },
  { code: 'PHP', name: 'Philippine Peso',               symbol: '₱',    region: 'Asia',         decimals: 2 },
  { code: 'VND', name: 'Vietnamese Dong',               symbol: '₫',    region: 'Asia',         decimals: 0 },
  { code: 'THB', name: 'Thai Baht',                     symbol: '฿',    region: 'Asia',         decimals: 2 },
  { code: 'MYR', name: 'Malaysian Ringgit',             symbol: 'RM',   region: 'Asia',         decimals: 2 },
  { code: 'PKR', name: 'Pakistani Rupee',               symbol: '₨',    region: 'Asia',         decimals: 2 },
  { code: 'BDT', name: 'Bangladeshi Taka',              symbol: '৳',    region: 'Asia',         decimals: 2 },
  // Central Asia
  { code: 'KZT', name: 'Kazakhstani Tenge',             symbol: '₸',    region: 'Central Asia', decimals: 2 },
  // Middle East
  { code: 'AED', name: 'UAE Dirham',                    symbol: 'د.إ',  region: 'Middle East',  decimals: 2 },
  { code: 'SAR', name: 'Saudi Riyal',                   symbol: '﷼',    region: 'Middle East',  decimals: 2 },
  { code: 'ILS', name: 'Israeli Shekel',                symbol: '₪',    region: 'Middle East',  decimals: 2 },
  { code: 'QAR', name: 'Qatari Riyal',                  symbol: 'ر.ق',  region: 'Middle East',  decimals: 2 },
  { code: 'KWD', name: 'Kuwaiti Dinar',                 symbol: 'د.ك',  region: 'Middle East',  decimals: 3 },
  // Africa
  { code: 'NGN', name: 'Nigerian Naira',                symbol: '₦',    region: 'Africa',       decimals: 2 },
  { code: 'ZAR', name: 'South African Rand',            symbol: 'R',    region: 'Africa',       decimals: 2 },
  { code: 'EGP', name: 'Egyptian Pound',                symbol: '£',    region: 'Africa',       decimals: 2 },
  { code: 'KES', name: 'Kenyan Shilling',               symbol: 'KSh',  region: 'Africa',       decimals: 2 },
  { code: 'GHS', name: 'Ghanaian Cedi',                 symbol: 'GH₵',  region: 'Africa',       decimals: 2 },
  { code: 'MAD', name: 'Moroccan Dirham',               symbol: 'MAD',  region: 'Africa',       decimals: 2 },
  { code: 'TZS', name: 'Tanzanian Shilling',            symbol: 'TSh',  region: 'Africa',       decimals: 2 },
  { code: 'UGX', name: 'Ugandan Shilling',              symbol: 'USh',  region: 'Africa',       decimals: 0 },
  { code: 'XOF', name: 'West African CFA Franc',        symbol: 'CFA',  region: 'Africa',       decimals: 0 },
  { code: 'XAF', name: 'Central African CFA Franc',     symbol: 'FCFA', region: 'Africa',       decimals: 0 },
  { code: 'ETB', name: 'Ethiopian Birr',                symbol: 'Br',   region: 'Africa',       decimals: 2 },
  // Oceania
  { code: 'AUD', name: 'Australian Dollar',             symbol: 'A$',   region: 'Oceania',      decimals: 2 },
  { code: 'NZD', name: 'New Zealand Dollar',            symbol: 'NZ$',  region: 'Oceania',      decimals: 2 },
]

export const CURRENCY_MAP: Record<string, Currency> = Object.fromEntries(
  CURRENCIES.map((c) => [c.code, c])
)

export const CURRENCY_GROUPS: Record<string, Currency[]> = CURRENCIES.reduce<Record<string, Currency[]>>(
  (acc, c) => {
    if (!acc[c.region]) acc[c.region] = []
    acc[c.region].push(c)
    return acc
  },
  {}
)

// Ordered region list for the selector dropdown
export const REGION_ORDER = [
  'Americas', 'Caribbean', 'Europe', 'Eastern Europe',
  'Asia', 'Central Asia', 'Middle East', 'Africa', 'Oceania',
]

/**
 * Convert amount in minor units from source currency to target currency.
 * All conversions route through USD (rates are stored as USD base).
 * Returns the target amount as a plain number (not yet formatted).
 */
export function convertToDisplay(
  amountMinor: number,
  sourceCurrency: string,
  targetCurrency: string,
  rates: Record<string, number>,
): number {
  const sourceDecimals = CURRENCY_MAP[sourceCurrency]?.decimals ?? 2
  const amountMajor = amountMinor / 100

  if (sourceCurrency === targetCurrency) return amountMajor

  // Step 1: source → USD
  let amountUSD: number
  if (sourceCurrency === 'USD') {
    amountUSD = amountMajor
  } else {
    const sourceRate = rates[sourceCurrency]
    if (!sourceRate) return amountMajor
    amountUSD = amountMajor / sourceRate
  }

  // Step 2: USD → target
  if (targetCurrency === 'USD') return amountUSD
  const targetRate = rates[targetCurrency]
  if (!targetRate) return amountUSD
  return amountUSD * targetRate
}

/**
 * Format a converted display amount with the correct symbol and decimal places.
 */
export function formatCurrency(
  amountMinor: number,
  sourceCurrency: string,
  targetCurrency: string,
  rates: Record<string, number>,
): string {
  const converted = convertToDisplay(amountMinor, sourceCurrency, targetCurrency, rates)
  const target = CURRENCY_MAP[targetCurrency]
  const decimals = target?.decimals ?? 2
  const symbol = target?.symbol ?? targetCurrency
  return `${symbol}${converted.toFixed(decimals)}`
}

/**
 * Format a plain USD major amount (not minor units) into the target currency.
 * Use this when the backend already returns USD amounts as floats.
 */
export function convertFromUSD(
  amountUSD: number,
  targetCurrency: string,
  rates: Record<string, number>,
): string {
  if (targetCurrency === 'USD') {
    return `$${amountUSD.toFixed(2)}`
  }
  const rate = rates[targetCurrency]
  const converted = rate ? amountUSD * rate : amountUSD
  const target = CURRENCY_MAP[targetCurrency]
  const decimals = target?.decimals ?? 2
  const symbol = target?.symbol ?? targetCurrency
  return `${symbol}${converted.toFixed(decimals)}`
}
