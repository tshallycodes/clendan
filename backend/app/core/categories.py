INCOME_CATEGORIES = frozenset({
    "sales", "customer_payment", "refund_received", "other_income",
})

EXPENSE_CATEGORIES = frozenset({
    "advertising", "bank_fees", "consulting", "equipment", "insurance",
    "legal", "meals", "office_supplies", "payroll", "rent", "software",
    "tax", "travel", "utilities", "other",
})

ALLOWED_CATEGORIES = INCOME_CATEGORIES | EXPENSE_CATEGORIES
