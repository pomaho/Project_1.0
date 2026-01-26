from app.keywords import normalize_keyword


def test_normalize_keyword():
    assert normalize_keyword("  Ёлка  тест  ") == "елка тест"
    assert normalize_keyword("") == ""
    assert normalize_keyword("  ") == ""
