from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

ALLOWED_CATEGORIES = {
    "advertising", "bank_fees", "consulting", "equipment", "insurance",
    "legal", "meals", "office_supplies", "payroll", "rent", "software",
    "tax", "travel", "utilities", "other",
}


class ParsedReceipt(BaseModel):
    merchant: str
    amount_minor: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    date: Optional[date] = None
    category: str
    confidence: float = Field(ge=0.0, le=1.0)

    def model_post_init(self, __context) -> None:
        if self.category not in ALLOWED_CATEGORIES:
            self.category = "other"
