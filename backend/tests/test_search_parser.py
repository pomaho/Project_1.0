from app.search_parser import evaluate, parse_query


def test_simple_and():
    ast = parse_query("wedding summer")
    assert evaluate(ast, {"wedding", "summer"}) is True
    assert evaluate(ast, {"wedding"}) is False


def test_or():
    ast = parse_query("wedding OR birthday")
    assert evaluate(ast, {"wedding"}) is True
    assert evaluate(ast, {"birthday"}) is True
    assert evaluate(ast, {"studio"}) is False


def test_not():
    ast = parse_query("wedding -studio")
    assert evaluate(ast, {"wedding"}) is True
    assert evaluate(ast, {"wedding", "studio"}) is False


def test_prefix():
    ast = parse_query("wedd*")
    assert evaluate(ast, {"wedding"}) is True
    assert evaluate(ast, {"wed"}) is False
    assert evaluate(ast, {"studio"}) is False


def test_quotes():
    ast = parse_query('"red dress"')
    assert evaluate(ast, {"red dress"}) is True
    assert evaluate(ast, {"red", "dress"}) is False
