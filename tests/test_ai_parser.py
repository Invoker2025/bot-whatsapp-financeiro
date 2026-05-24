from ai_parser import parse_message


def test_parser_categorizes_common_food_expense():
    parsed = parse_message("Gastei 42 pastel")

    assert parsed["tipo"] == "GASTO"
    assert parsed["valor"] == 42
    assert parsed["categoria"] == "Alimentação"
    assert parsed["subcategoria"] == "Lanche"
    assert parsed["meio"] == "Pendente"


def test_parser_detects_payment_and_installments():
    parsed = parse_message("comprei 120 shopee credito 3x")

    assert parsed["valor"] == 120
    assert parsed["categoria"] == "Shopping"
    assert parsed["subcategoria"] == "Shopee"
    assert parsed["meio"] == "Crédito"
    assert parsed["parcelado"] == "Sim"
    assert parsed["total_parcelas"] == 3


def test_parser_detects_income():
    parsed = parse_message("recebi 3200 salario")

    assert parsed["tipo"] == "RECEITA"
    assert parsed["valor"] == 3200
    assert parsed["categoria"] == "Salário"
