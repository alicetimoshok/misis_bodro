"""Смоук-тест интерфейса: приложение запускается и основные сценарии работают без исключений."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def at(tmp_path, monkeypatch):
    monkeypatch.setenv("BODRO_ORDERS_PATH", str(tmp_path / "orders.json"))
    app = AppTest.from_file(APP, default_timeout=60)
    app.run()
    assert not app.exception
    return app


def test_all_pages_render(at):
    for page in ["quiz", "orders", "barista", "analytics", "menu"]:
        at.button(key=f"nav_{page}").click().run()
        assert not at.exception, page


def test_add_to_cart_and_checkout(at):
    at.button(key="add_cappuccino").click().run()
    at.button(key="add_croissant").click().run()
    assert at.session_state["cart"].total == 380
    at.text_input(key="cust_name").input("Анна").run()
    at.text_input(key="cust_phone").input("+7 900 123-45-67").run()
    at.button(key="cta_checkout").click().run()
    assert not at.exception
    assert at.session_state["cart"].is_empty
    assert len(at.session_state["my_orders"]) == 1


def test_checkout_validation_error(at):
    at.button(key="add_cappuccino").click().run()
    at.button(key="cta_checkout").click().run()  # имя и телефон пустые
    assert not at.exception
    assert not at.session_state["cart"].is_empty
    assert len(at.error) == 1


def test_quiz_flow(at):
    at.button(key="nav_quiz").click().run()
    at.button(key="quiz_submit").click().run()  # без ответов -> ошибка валидации
    assert len(at.error) == 1
    for qid, value in [("mood", "energy"), ("temp", "hot"), ("strength", "strong"),
                       ("sweetness", "none"), ("milk", "none"), ("snack", "sweet")]:
        at.radio(key=f"quiz_{qid}").set_value(value)
    at.button(key="quiz_submit").click().run()
    assert not at.exception
    assert at.session_state["quiz_result"] is not None
    assert len(at.session_state["quiz_result"]["recs"]) == 3
