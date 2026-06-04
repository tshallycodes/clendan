def format_minor_units(amount_minor: int, currency: str) -> str:
    """Convert integer minor units to display string. Only called at display layer."""
    return f"{amount_minor / 100:.2f} {currency}"


def major_to_minor(amount_major: float) -> int:
    """Convert decimal major units to integer minor units for storage."""
    return round(amount_major * 100)
