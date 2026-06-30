INCOME_CATEGORIES = frozenset({
    "sales",
    "customer_payment",
    "refund_received",
    "interest_income",
    "dividend_income",
    "grant_income",
    "other_income",
})

EXPENSE_CATEGORIES = frozenset({
    "advertising",
    "bank_fees",
    "charitable_donations",
    "consulting",
    "contractor_fees",
    "equipment",
    "insurance",
    "interest_expense",
    "legal",
    "meals",
    "office_supplies",
    "payroll",
    "rent",
    "repairs_maintenance",
    "shipping_postage",
    "software",
    "subscriptions",
    "tax",
    "training",
    "travel",
    "utilities",
    "vehicle",
    "other",
})

ALLOWED_CATEGORIES = INCOME_CATEGORIES | EXPENSE_CATEGORIES
