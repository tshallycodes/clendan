from decimal import Decimal, ROUND_HALF_UP

# ISO 4217 decimal places per currency. Currencies not listed default to 2.
CURRENCY_DECIMAL_PLACES: dict[str, int] = {
    # 0 decimal places
    "JPY": 0, "KRW": 0, "VND": 0, "IDR": 0,
    "UGX": 0, "XOF": 0, "XAF": 0, "CLP": 0,
    # 3 decimal places
    "KWD": 3,
}

# All 50 supported currencies for exchange rate tracking
SUPPORTED_CURRENCIES: list[str] = [
    # Americas
    "USD", "CAD", "BRL", "MXN", "ARS", "COP", "CLP",
    # Europe
    "EUR", "GBP", "CHF", "SEK", "NOK", "PLN", "TRY", "HUF",
    # Asia
    "JPY", "CNY", "INR", "KRW", "SGD", "HKD", "IDR", "PHP",
    "VND", "THB", "MYR", "PKR", "BDT",
    # Middle East
    "AED", "SAR", "ILS", "QAR", "KWD",
    # Africa
    "NGN", "ZAR", "EGP", "KES", "GHS", "MAD", "TZS", "UGX",
    "XOF", "XAF", "ETB",
    # Oceania
    "AUD", "NZD",
    # Caribbean
    "JMD", "TTD",
    # Central Asia
    "KZT",
    # Eastern Europe
    "CZK",
]


def format_minor_units(amount_minor: int, currency: str) -> str:
    """Convert integer minor units to display string. Only called at display layer."""
    decimals = CURRENCY_DECIMAL_PLACES.get(currency, 2)
    amount = amount_minor / 100
    return f"{amount:.{decimals}f} {currency}"


def major_to_minor(amount_major: float) -> int:
    """Convert decimal major units to integer minor units for storage."""
    return round(amount_major * 100)


def convert_minor_to_target(
    amount_minor: int,
    source_currency: str,
    target_currency: str,
    rates: dict[str, Decimal],
) -> Decimal:
    """
    Convert amount in source_currency minor units to target_currency major units.
    All conversions route through USD as pivot (base_currency = USD in ExchangeRate table).
    Never call at storage time — display layer only.
    """
    amount_major = Decimal(amount_minor) / Decimal(100)

    if source_currency == target_currency:
        target_decimals = CURRENCY_DECIMAL_PLACES.get(target_currency, 2)
        quantizer = Decimal(10) ** -target_decimals
        return amount_major.quantize(quantizer, rounding=ROUND_HALF_UP)

    # Convert to USD
    if source_currency == "USD":
        amount_usd = amount_major
    else:
        source_rate = rates.get(source_currency)
        if not source_rate or source_rate == 0:
            return amount_major
        amount_usd = amount_major / source_rate

    # Convert USD → target
    if target_currency == "USD":
        result = amount_usd
    else:
        target_rate = rates.get(target_currency)
        if not target_rate:
            return amount_usd
        result = amount_usd * target_rate

    target_decimals = CURRENCY_DECIMAL_PLACES.get(target_currency, 2)
    quantizer = Decimal(10) ** -target_decimals
    return result.quantize(quantizer, rounding=ROUND_HALF_UP)
