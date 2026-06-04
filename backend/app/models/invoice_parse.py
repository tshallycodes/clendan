from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str
    quantity: float
    unit_price_minor: int = Field(ge=0)
    total_minor: int = Field(ge=0)


class ParsedInvoice(BaseModel):
    vendor: str
    invoice_number: str
    line_items: list[LineItem]
    amount_minor: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    due_date: Optional[date] = None
    vat_minor: Optional[int] = Field(default=None, ge=0)
    po_number: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
