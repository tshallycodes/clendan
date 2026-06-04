import pytest
from app.models.currency import format_minor_units, major_to_minor


def test_format_gbp():
    assert format_minor_units(10050, "GBP") == "100.50 GBP"


def test_format_zero():
    assert format_minor_units(0, "USD") == "0.00 USD"


def test_format_whole_pounds():
    assert format_minor_units(100_00, "EUR") == "100.00 EUR"


def test_major_to_minor_rounds_correctly():
    # 10.005 should round to 1001 (banker's rounding doesn't apply here — round() in Python 3 uses banker's rounding)
    assert major_to_minor(10.00) == 1000
    assert major_to_minor(100.50) == 10050
    assert major_to_minor(0.01) == 1
    assert major_to_minor(0.001) == 0  # sub-pence rounds to zero


def test_major_to_minor_large_amount():
    assert major_to_minor(9999.99) == 999999


def test_major_to_minor_handles_float_precision():
    # Common floating-point trap: 0.1 + 0.2 != 0.3 in IEEE 754
    # Verify round() saves us here
    result = major_to_minor(0.1 + 0.2)
    assert result == 30  # 30 pence, not 29 or 31


def test_roundtrip_display_does_not_affect_storage():
    amount_minor = 123456
    display = format_minor_units(amount_minor, "GBP")
    assert display == "1234.56 GBP"
    # Storage value must never be modified by display
    assert amount_minor == 123456
