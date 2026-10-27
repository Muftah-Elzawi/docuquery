import json
from decimal import Decimal

from app.services.extraction import _to_decimal, extract_fields
from app.services.llm import FakeProvider, LLMError

INVOICE = """Alpenblick Maschinenbau GmbH
Rechnung
Rechnungsnummer: RE-2026-0412
Rechnungsdatum: 14.09.2026
Nettobetrag: 1.200,00 EUR
MwSt. 19%: 228,00 EUR
Gesamtbetrag: 1.428,00 EUR"""


class StubLLM(FakeProvider):
    def __init__(self, reply):
        super().__init__(dim=8)
        self.reply = reply

    def chat(self, system, user, json_mode=False):
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def test_parses_german_and_english_amounts():
    assert _to_decimal("1.234,56") == Decimal("1234.56")
    assert _to_decimal("1,234.56") == Decimal("1234.56")
    assert _to_decimal("€ 99,90") == Decimal("99.90")


def test_rule_based_fallback_when_llm_returns_nothing():
    fields = extract_fields(INVOICE, StubLLM("{}"))
    assert fields.document_type == "invoice"
    assert fields.document_number == "RE-2026-0412"
    assert fields.document_date == "2026-09-14"
    assert (fields.net_amount, fields.tax_amount, fields.gross_amount) == (
        Decimal("1200.00"), Decimal("228.00"), Decimal("1428.00"))
    assert fields.currency == "EUR"
    assert fields.warnings == []


def test_llm_values_win_over_rules():
    reply = json.dumps({"vendor_name": "Alpenblick Maschinenbau GmbH", "gross_amount": "1428.00"})
    fields = extract_fields(INVOICE, StubLLM(reply))
    assert fields.vendor_name == "Alpenblick Maschinenbau GmbH"
    assert fields.gross_amount == Decimal("1428.00")


def test_flags_amounts_that_dont_add_up():
    text = INVOICE.replace("1.428,00", "1.500,00")
    fields = extract_fields(text, StubLLM("{}"))
    assert any("don't add up" in w for w in fields.warnings)


def test_amounts_always_have_two_decimals():
    fields = extract_fields(INVOICE, StubLLM(json.dumps({"net_amount": 1200, "tax_amount": 228.0})))
    assert (str(fields.net_amount), str(fields.tax_amount)) == ("1200.00", "228.00")


def test_unknown_document_type_becomes_other():
    assert extract_fields("Reisekostenrichtlinie", StubLLM('{"document_type": "Richtlinie"}')).document_type == "other"


def test_drops_values_not_backed_by_the_text():
    reply = json.dumps({"vendor_name": "Invented Corp", "document_number": "RE-2026-0412", "due_date": "2026-10-01"})
    fields = extract_fields(INVOICE, StubLLM(reply))
    assert fields.vendor_name is None
    assert fields.document_number == "RE-2026-0412"
    assert fields.due_date is None  # the invoice states no payment term
    assert any("vendor_name, due_date" in w for w in fields.warnings)


def test_keeps_computed_due_date_when_payment_term_is_stated():
    text = INVOICE + "\nZahlbar innerhalb von 14 Tagen ohne Abzug."
    assert extract_fields(text, StubLLM('{"due_date": "2026-09-28"}')).due_date == "2026-09-28"


def test_survives_llm_failure_and_invalid_json():
    assert extract_fields(INVOICE, StubLLM(LLMError("down"))).gross_amount == Decimal("1428.00")
    assert extract_fields(INVOICE, StubLLM("not json")).gross_amount == Decimal("1428.00")
