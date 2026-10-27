"""Structured field extraction from business documents (invoices, delivery notes, ...).

Strategy: the LLM extracts fields as JSON, Pydantic validates them, values the source text
doesn't support are dropped, regex rules fill gaps, and a plausibility check flags invoices
whose amounts don't add up.
"""

import json
import re
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ValidationError, field_validator

from app.services.llm import LLMError, LLMProvider

EXTRACTION_PROMPT = """You extract fields from business documents (German or English).
Return ONLY a JSON object with these keys (use null when a field is not present):
document_type ("invoice", "delivery_note", "contract", "offer" or "other"),
vendor_name, customer_name, document_number, document_date (YYYY-MM-DD), due_date (YYYY-MM-DD),
currency (ISO code like EUR), net_amount, tax_amount, gross_amount (numbers, no currency symbols)."""

DOCUMENT_TYPES = {"invoice", "delivery_note", "contract", "offer", "other"}
_CENT = Decimal("0.01")


class ExtractedFields(BaseModel):
    document_type: str | None = None
    vendor_name: str | None = None
    customer_name: str | None = None
    document_number: str | None = None
    document_date: str | None = None
    due_date: str | None = None
    currency: str | None = None
    net_amount: Decimal | None = None
    tax_amount: Decimal | None = None
    gross_amount: Decimal | None = None
    warnings: list[str] = []

    @field_validator("net_amount", "tax_amount", "gross_amount", mode="before")
    @classmethod
    def parse_amount(cls, value):
        if value is None:
            return None
        try:
            # str() first so floats don't carry binary noise; always two decimals ("3000" -> 3000.00)
            amount = Decimal(str(value)) if isinstance(value, (int, float, Decimal)) else _to_decimal(str(value))
            return amount.quantize(_CENT)
        except InvalidOperation:
            return None

    @field_validator("document_type", mode="before")
    @classmethod
    def known_type(cls, value):
        if value is None:
            return None
        value = str(value).strip().lower()
        return value if value in DOCUMENT_TYPES else "other"


def _to_decimal(raw: str) -> Decimal:
    """Parse '1.234,56' (German) and '1,234.56' (English) alike."""
    s = re.sub(r"[^\d,.\-]", "", raw)
    if "," in s and (s.rfind(",") > s.rfind(".")):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    return Decimal(s)


_AMOUNT = r"(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})"
_RULES: dict[str, list[str]] = {
    "document_number": [r"(?:Rechnungs(?:nummer|-Nr\.?)|Invoice (?:No\.?|Number))\s*:?\s*([A-Z0-9][\w\-/]+)"],
    "document_date": [r"(?:Rechnungsdatum|Invoice Date|Datum|Date)\s*:?\s*(\d{1,2}\.\d{1,2}\.\d{4}|\d{4}-\d{2}-\d{2})"],
    "net_amount": [rf"(?:Nettobetrag|Netto|Net amount|Subtotal)\s*:?\s*(?:EUR|€)?\s*{_AMOUNT}"],
    "tax_amount": [rf"(?:MwSt\.?|USt\.?|Umsatzsteuer|VAT|Tax)[^\n\d]*?(?:\d{{1,2}}\s*%)?[^\n\d]*?{_AMOUNT}"],
    "gross_amount": [rf"(?:Gesamtbetrag|Bruttobetrag|Brutto|Total|Amount due)\s*:?\s*(?:EUR|€)?\s*{_AMOUNT}"],
}


def _iso_date(value: str | None) -> str | None:
    if value and (m := re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", value)):
        day, month, year = m.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return value


_VERBATIM_FIELDS = ("vendor_name", "customer_name", "document_number")
_DUE_DATE_CUE = re.compile(r"f(?:ä|ae)llig|zahlbar|zahlungsziel|\bdue\b|payable|payment terms", re.I)


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _drop_unsupported(text: str, fields: ExtractedFields) -> None:
    """Remove LLM values the document doesn't back up, instead of storing a hallucination.

    Names and numbers must appear verbatim. A due date is usually computed ("payable within
    14 days"), so it only needs a payment-term cue in the text.
    """
    haystack = _squash(text)
    dropped = [name for name in _VERBATIM_FIELDS
               if (value := getattr(fields, name)) and _squash(value) not in haystack]
    if fields.due_date and not _DUE_DATE_CUE.search(text):
        dropped.append("due_date")
    for name in dropped:
        setattr(fields, name, None)
    if dropped:
        fields.warnings.append(f"Dropped values not found in the document: {', '.join(dropped)}")


def _apply_rules(text: str, fields: ExtractedFields) -> None:
    for name, patterns in _RULES.items():
        if getattr(fields, name) is not None:
            continue
        for pattern in patterns:
            if m := re.search(pattern, text, re.I):
                value = m.group(1)
                setattr(fields, name, _to_decimal(value).quantize(_CENT) if name.endswith("amount") else value)
                break
    if fields.currency is None and re.search(r"€|\bEUR\b", text):
        fields.currency = "EUR"


def _check_plausibility(fields: ExtractedFields) -> None:
    n, t, g = fields.net_amount, fields.tax_amount, fields.gross_amount
    if None not in (n, t, g) and abs((n + t) - g) > Decimal("0.02"):
        fields.warnings.append(f"Amounts don't add up: net {n} + tax {t} != gross {g}")
    if fields.document_type == "invoice" and g is None:
        fields.warnings.append("Invoice without a recognisable total amount")


def extract_fields(text: str, llm: LLMProvider) -> ExtractedFields:
    excerpt = text[:6000]  # header and totals of business documents sit at the start/end
    try:
        raw = llm.chat(EXTRACTION_PROMPT, excerpt, json_mode=True)
        fields = ExtractedFields.model_validate(json.loads(raw or "{}"))
    except (LLMError, json.JSONDecodeError, ValidationError):
        fields = ExtractedFields(warnings=["LLM extraction failed; rule-based fields only"])

    _drop_unsupported(text, fields)
    _apply_rules(text, fields)
    fields.document_date = _iso_date(fields.document_date)
    fields.due_date = _iso_date(fields.due_date)
    if fields.document_type is None and re.search(r"\b(Rechnung|Invoice)\b", text, re.I):
        fields.document_type = "invoice"
    _check_plausibility(fields)
    return fields
