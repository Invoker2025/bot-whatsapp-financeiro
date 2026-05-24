import time

import main
import state


def _isolate_state(tmp_path):
    state.DB_NAME = str(tmp_path / "state.db")
    state._init_table()
    if hasattr(state.get_pending, "_cache"):
        state.get_pending._cache.clear()


def test_debit_expense_flow(monkeypatch, tmp_path):
    _isolate_state(tmp_path)
    user = "test-debit-flow"
    saved = []

    monkeypatch.setattr(main, "save_to_api", lambda data: saved.append(dict(data)) or True)

    first = main.receive_message(
        main.Message(user_id=user, text="Gastei 20 de lanche", channel="twilio")
    )
    second = main.receive_message(main.Message(user_id=user, text="2", channel="twilio"))

    assert "Qual o meio de pagamento" in first["reply"]
    assert "GASTO CAPTURADO" in second["reply"]
    assert saved[0]["meio"] == "Débito"
    assert saved[0]["categoria"] == "Alimentação"
    assert saved[0]["subcategoria"] == "Lanche"


def test_credit_installment_flow(monkeypatch, tmp_path):
    _isolate_state(tmp_path)
    user = "test-credit-flow"
    background_saves = []

    def fake_background(data, user_id="", channel=""):
        background_saves.append((dict(data), user_id, channel))

    monkeypatch.setattr(main, "save_in_background", fake_background)

    main.receive_message(main.Message(user_id=user, text="Gastei 15 almoço", channel="twilio"))
    credit = main.receive_message(main.Message(user_id=user, text="3", channel="twilio"))
    final = main.receive_message(main.Message(user_id=user, text="2", channel="twilio"))

    assert "CARTÃO DE CRÉDITO SELECIONADO" in credit["reply"]
    assert "GASTO CAPTURADO" in final["reply"]
    assert "2x de R$ 7.50" in final["reply"]
    assert background_saves[0][0]["meio"] == "Crédito"
    assert background_saves[0][0]["total_parcelas"] == 2


def test_delayed_numeric_reply_waits_for_pending(monkeypatch, tmp_path):
    _isolate_state(tmp_path)
    user = "test-delayed-pending"
    monkeypatch.setattr(main, "save_in_background", lambda *args, **kwargs: None)

    def late_pending():
        time.sleep(0.2)
        state.set_pending(
            user,
            {
                "tipo": "GASTO",
                "valor": 20,
                "categoria": "Alimentação",
                "subcategoria": "Jantar",
                "descricao": "Jantar",
                "meio": "Crédito",
                "parcelado": "Pendente",
                "total_parcelas": 1,
            },
            channel="twilio",
        )

    import threading

    threading.Thread(target=late_pending).start()
    final = main.receive_message(main.Message(user_id=user, text="2", channel="twilio"))

    assert "GASTO CAPTURADO" in final["reply"]
    assert "2x de R$ 10.00" in final["reply"]
