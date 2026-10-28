"""Тесты ключевой бизнес-логики «Бодро кофе»."""
from datetime import datetime, timedelta

import pytest

from logic import (
    SLOT_CAPACITY,
    Cart,
    Order,
    OrderRepository,
    ValidationError,
    _ceil_to_step,
    available_slots,
    compute_analytics,
    create_order,
    filter_menu,
    normalize_phone,
    recommend,
    recommend_snack,
    validate_answers,
    validate_name,
)
from menu_data import ITEMS_BY_ID, MENU, QUIZ, generate_demo_orders

NOW = datetime(2026, 10, 28, 10, 3)  # среда, 10:03


def make_cart(*ids):
    cart = Cart(MENU)
    for i in ids:
        cart.add(i)
    return cart


def make_order(pickup, status="new", oid="BD-TEST01", total=220):
    return Order(
        id=oid, customer_name="Анна", phone="+79001234567",
        pickup_time=pickup.strftime("%Y-%m-%dT%H:%M"),
        items=[{"id": "cappuccino", "name": "Капучино", "qty": 1, "price": 220}],
        total=total, status=status,
    )


# ---------------------------- корзина ---------------------------------------
def test_cart_total_and_count():
    cart = make_cart("cappuccino", "croissant")
    assert cart.total == 220 + 160
    assert cart.count == 2


def test_cart_add_decrease_remove():
    cart = make_cart("cappuccino", "cappuccino")
    assert cart.count == 2
    cart.decrease("cappuccino")
    assert cart.count == 1
    cart.decrease("cappuccino")
    assert cart.is_empty
    cart.add("latte")
    cart.remove("latte")
    assert cart.is_empty


def test_cart_unknown_item_and_bad_qty():
    cart = Cart(MENU)
    with pytest.raises(ValidationError):
        cart.add("nope")
    with pytest.raises(ValidationError):
        cart.add("latte", 0)


def test_cart_max_qty():
    cart = Cart(MENU)
    cart.add("latte", 10)
    with pytest.raises(ValidationError):
        cart.add("latte")


def test_filter_menu():
    assert all(i.popular for i in filter_menu(MENU, "Популярное"))
    assert all(i.category == "Чай" for i in filter_menu(MENU, "Чай"))


# ---------------------------- валидация -------------------------------------
@pytest.mark.parametrize("raw", ["+7 900 123-45-67", "8 (900) 123 45 67", "9001234567", "79001234567"])
def test_phone_ok(raw):
    assert normalize_phone(raw) == "+79001234567"


@pytest.mark.parametrize("raw", ["", "123", "abc", "+7 900 123-45", "+7900123456789"])
def test_phone_bad(raw):
    with pytest.raises(ValidationError):
        normalize_phone(raw)


def test_name_validation():
    assert validate_name("  Анна   Мария ") == "Анна Мария"
    for bad in ["", " ", "А", "123", "<script>"]:
        with pytest.raises(ValidationError):
            validate_name(bad)


# ---------------------------- слоты -----------------------------------------
def test_ceil_to_step():
    assert _ceil_to_step(datetime(2026, 1, 1, 10, 13)) == datetime(2026, 1, 1, 10, 20)
    assert _ceil_to_step(datetime(2026, 1, 1, 10, 20)) == datetime(2026, 1, 1, 10, 20)
    assert _ceil_to_step(datetime(2026, 1, 1, 10, 20, 5)) == datetime(2026, 1, 1, 10, 30)


def test_first_slot_respects_lead_time():
    slots = available_slots([], NOW)
    assert slots[0].start == datetime(2026, 10, 28, 10, 20)  # 10:03 + 10 мин -> 10:13 -> 10:20
    assert slots[-1].start == datetime(2026, 10, 28, 21, 50)


def test_full_slot_is_hidden():
    busy = datetime(2026, 10, 28, 10, 20)
    orders = [make_order(busy, oid=f"BD-{i}") for i in range(SLOT_CAPACITY)]
    starts = [s.start for s in available_slots(orders, NOW)]
    assert busy not in starts


def test_cancelled_orders_free_the_slot():
    busy = datetime(2026, 10, 28, 10, 20)
    orders = [make_order(busy, "cancelled", f"BD-{i}") for i in range(SLOT_CAPACITY)]
    assert busy in [s.start for s in available_slots(orders, NOW)]


def test_after_closing_slots_move_to_tomorrow():
    late = datetime(2026, 10, 28, 23, 7)
    slots = available_slots([], late)
    assert slots[0].start == datetime(2026, 10, 29, 8, 0)


# ---------------------------- создание заказа -------------------------------
def test_create_order_success():
    pickup = datetime(2026, 10, 28, 11, 0)
    order = create_order(make_cart("cappuccino", "croissant"), "Анна", "8 900 123 45 67", pickup, [], "Без сахара", NOW)
    assert order.total == 380
    assert order.phone == "+79001234567"
    assert order.pickup == pickup
    assert order.status == "new"
    assert len(order.items) == 2


def test_create_order_empty_cart():
    with pytest.raises(ValidationError):
        create_order(Cart(MENU), "Анна", "9001234567", datetime(2026, 10, 28, 11, 0), [], now=NOW)


def test_create_order_too_soon():
    with pytest.raises(ValidationError):
        create_order(make_cart("latte"), "Анна", "9001234567", datetime(2026, 10, 28, 10, 10), [], now=NOW)


def test_create_order_outside_hours_and_step():
    cart = make_cart("latte")
    with pytest.raises(ValidationError):
        create_order(cart, "Анна", "9001234567", datetime(2026, 10, 29, 7, 0), [], now=NOW)
    with pytest.raises(ValidationError):
        create_order(cart, "Анна", "9001234567", datetime(2026, 10, 28, 11, 5), [], now=NOW)


def test_create_order_full_slot():
    pickup = datetime(2026, 10, 28, 11, 0)
    orders = [make_order(pickup, oid=f"BD-{i}") for i in range(SLOT_CAPACITY)]
    with pytest.raises(ValidationError):
        create_order(make_cart("latte"), "Анна", "9001234567", pickup, orders, now=NOW)


def test_create_order_too_far_ahead():
    with pytest.raises(ValidationError):
        create_order(make_cart("latte"), "Анна", "9001234567", NOW + timedelta(days=5), [], now=NOW)


# ---------------------------- хранилище -------------------------------------
def test_repository_roundtrip_and_status(tmp_path):
    repo = OrderRepository(tmp_path / "orders.json")
    assert repo.load() == []
    order = make_order(datetime(2026, 10, 28, 11, 0))
    repo.add(order)
    assert repo.load()[0].id == order.id
    repo.update_status(order.id, "preparing")
    repo.update_status(order.id, "ready")
    assert repo.load()[0].status == "ready"
    with pytest.raises(ValidationError):  # нельзя отменить готовый заказ
        repo.cancel(order.id)
    with pytest.raises(ValidationError):
        repo.update_status("missing", "preparing")


def test_repository_corrupt_file(tmp_path):
    path = tmp_path / "orders.json"
    path.write_text("{ not json", encoding="utf-8")
    repo = OrderRepository(path)
    assert repo.load() == []
    assert path.with_suffix(".corrupt").exists()


# ---------------------------- подбор напитка --------------------------------
def answers(**kw):
    base = dict(mood="energy", temp="hot", strength="strong", sweetness="none", milk="none", snack="none")
    base.update(kw)
    return base


def test_recommend_strong_black_hot():
    recs = recommend(answers(), MENU, QUIZ)
    assert recs[0].item.id in {"espresso", "americano"}
    assert len(recs) == 3
    assert all(r.item.kind == "drink" for r in recs)


def test_recommend_cold_refreshing():
    recs = recommend(answers(mood="refresh", temp="cold", strength="medium", sweetness="some"), MENU, QUIZ)
    assert all(r.item.temp == "cold" for r in recs)


def test_recommend_sweet_milky_treat():
    recs = recommend(answers(mood="treat", strength="soft", sweetness="sweet", milk="dairy"), MENU, QUIZ)
    assert recs[0].item.id in {"caramel_latte", "raf"}


def test_recommend_percent_in_range():
    for r in recommend(answers(), MENU, QUIZ, top_n=10):
        assert 0 <= r.percent <= 100


def test_recommend_requires_all_answers():
    bad = answers()
    del bad["milk"]
    with pytest.raises(ValidationError):
        recommend(bad, MENU, QUIZ)
    with pytest.raises(ValidationError):
        validate_answers(answers(temp="lava"), QUIZ)


def test_recommend_snack():
    assert "sweet" in recommend_snack(answers(snack="sweet"), MENU).tags
    assert "salty" in recommend_snack(answers(snack="salty"), MENU).tags
    assert recommend_snack(answers(snack="none"), MENU) is None


# ---------------------------- аналитика и демо ------------------------------
def test_analytics():
    orders = [
        make_order(datetime(2026, 10, 27, 9, 0), "issued", "A", 220),
        make_order(datetime(2026, 10, 27, 9, 10), "issued", "B", 380),
        make_order(datetime(2026, 10, 27, 13, 0), "cancelled", "C", 999),
    ]
    stats = compute_analytics(orders)
    assert stats["orders"] == 2
    assert stats["revenue"] == 600
    assert stats["avg_check"] == 300
    assert stats["cancelled"] == 1
    assert stats["peak_hour"] == 9
    assert stats["top_items"][0] == ("Капучино", 2)


def test_analytics_empty():
    stats = compute_analytics([])
    assert stats["orders"] == 0 and stats["avg_check"] == 0 and stats["peak_hour"] is None


def test_demo_orders_deterministic_and_within_capacity():
    a = generate_demo_orders(MENU, NOW)
    b = generate_demo_orders(MENU, NOW)
    assert [o.to_dict() for o in a] == [o.to_dict() for o in b]
    assert len(a) > 50
    from collections import Counter
    loads = Counter(o.pickup_time for o in a)
    assert max(loads.values()) <= SLOT_CAPACITY
    assert all(o.items and o.total == sum(i["qty"] * ITEMS_BY_ID[i["id"]].price for i in o.items) for o in a)
