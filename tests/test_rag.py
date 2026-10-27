from app.services.rag import remove_invalid_citations


def test_keeps_valid_citations():
    assert remove_invalid_citations("Die Pauschale beträgt 28 EUR [2][1].", 2) == "Die Pauschale beträgt 28 EUR [2][1]."


def test_removes_citations_to_missing_sources():
    assert remove_invalid_citations("Laut [1] [5] gilt eine Frist von 30 Tagen [0].", 4) == "Laut [1] gilt eine Frist von 30 Tagen."
