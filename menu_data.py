"""Демонстрационные данные: меню, вопросы опроса, генератор тестовых заказов."""
from __future__ import annotations

import random
from collections import Counter
from datetime import datetime, time, timedelta
from typing import Sequence

from logic import (
    CLOSE_TIME,
    OPEN_TIME,
    POPULAR,
    SLOT_CAPACITY,
    SLOT_STEP_MIN,
    MenuItem,
    Order,
    Question,
    available_slots,
    fmt_pickup,
)

CATEGORIES = [POPULAR, "Классика", "Авторский кофе", "Чай", "Перекусить"]
CITIES = ["Москва", "Санкт-Петербург", "Казань"]


def _drink(id, name, category, desc, price, emoji, temp, strength, sweet, milk, plant, tags, **kw):
    return MenuItem(
        id=id, name=name, category=category, description=desc, price=price, emoji=emoji,
        kind="drink", temp=temp, strength=strength, sweetness=sweet, milk=milk,
        plant_ok=plant, tags=tuple(tags), **kw,
    )


def _snack(id, name, desc, price, emoji, tags, **kw):
    return MenuItem(
        id=id, name=name, category="Перекусить", description=desc, price=price, emoji=emoji,
        kind="snack", tags=tuple(tags), **kw,
    )


MENU: list[MenuItem] = [
    # --- Классика
    _drink("espresso", "Эспрессо", "Классика", "Двойной шот с насыщенным вкусом", 150, "☕",
           "hot", 5, 1, False, False, ["energy"]),
    _drink("americano", "Американо", "Классика", "Эспрессо и горячая вода", 180, "☕",
           "hot", 4, 1, False, False, ["energy"]),
    _drink("cappuccino", "Капучино", "Классика", "Эспрессо, молоко, воздушная пенка", 220, "☕",
           "hot", 3, 2, True, True, ["calm", "treat"], badge="Хит", popular=True),
    _drink("latte", "Латте", "Классика", "Нежный кофе с большим количеством молока", 250, "🥛",
           "hot", 2, 2, True, True, ["calm"], popular=True),
    _drink("flat_white", "Флэт уайт", "Классика", "Двойной эспрессо и бархатное молоко", 260, "☕",
           "hot", 4, 2, True, True, ["energy"]),
    _drink("iced_latte", "Айс-латте", "Классика", "Эспрессо, молоко, лёд", 290, "🧊",
           "cold", 2, 2, True, True, ["refresh"], badge="Освежает", popular=True),
    # --- Авторский кофе
    _drink("raf", "Раф", "Авторский кофе", "Сливки, ваниль и эспрессо", 310, "🍦",
           "hot", 2, 4, True, False, ["treat", "calm"], popular=True),
    _drink("caramel_latte", "Карамельный латте", "Авторский кофе", "Латте с домашним карамельным сиропом", 290, "🍮",
           "hot", 2, 5, True, True, ["treat"]),
    _drink("matcha_latte", "Матча-латте", "Авторский кофе", "Японская матча и молоко", 300, "🍵",
           "hot", 2, 3, True, True, ["calm", "energy"]),
    _drink("espresso_tonic", "Эспрессо-тоник", "Авторский кофе", "Эспрессо, тоник, лёд и лимон", 290, "🍋",
           "cold", 4, 2, False, False, ["refresh", "energy"]),
    _drink("cold_brew", "Колд брю", "Авторский кофе", "Холодная экстракция 12 часов", 270, "🧊",
           "cold", 4, 1, False, False, ["energy", "refresh"]),
    _drink("bodro_orange", "Бодро-апельсин", "Авторский кофе", "Эспрессо, апельсиновый фреш и лёд", 320, "🍊",
           "cold", 3, 3, False, False, ["refresh", "energy"]),
    # --- Чай
    _drink("black_tea", "Чёрный чай", "Чай", "Классический чай с бергамотом", 150, "🫖",
           "hot", 2, 1, False, False, ["calm"]),
    _drink("green_tea", "Зелёный чай с жасмином", "Чай", "Лёгкий и ароматный", 150, "🍵",
           "hot", 1, 1, False, False, ["calm", "refresh"]),
    _drink("sea_buckthorn", "Облепиховый чай", "Чай", "Облепиха, апельсин и мёд", 220, "🍊",
           "hot", 1, 3, False, False, ["calm", "treat"]),
    _drink("herbal", "Травяной сбор", "Чай", "Мята, чабрец и мелисса", 170, "🌿",
           "hot", 1, 1, False, False, ["calm"]),
    _drink("iced_tea", "Айс-ти лимон-мята", "Чай", "Освежающий чай со льдом", 200, "🍹",
           "cold", 1, 3, False, False, ["refresh"]),
    # --- Перекусить
    _snack("croissant", "Круассан", "С хрустящей корочкой и нежной начинкой", 160, "🥐",
           ["sweet"], badge="Бестселлер", popular=True),
    _snack("cheese_croissant", "Круассан с сыром", "Слоёный, с расплавленным сыром", 190, "🥐", ["salty"]),
    _snack("syrnik", "Сырники", "Три сырника со сметаной и ягодами", 220, "🥞", ["sweet"]),
    _snack("cheesecake", "Чизкейк", "Нью-Йорк с ягодным соусом", 260, "🍰", ["sweet"], popular=True),
    _snack("sandwich_turkey", "Сэндвич с индейкой", "Индейка, сыр, свежие овощи", 290, "🥪", ["salty"]),
    _snack("toast_salmon", "Тост с лососем", "Авокадо, слабосолёный лосось", 340, "🥑", ["salty"]),
    _snack("oat_cookie", "Овсяное печенье", "Домашнее, с шоколадом", 90, "🍪", ["sweet"]),
]

ITEMS_BY_ID = {i.id: i for i in MENU}


QUIZ: list[Question] = [
    Question("mood", "Чего вам хочется сейчас?", (
        ("energy", "⚡ Бодрости и энергии"),
        ("calm", "🧘 Спокойствия и уюта"),
        ("treat", "🎁 Порадовать себя"),
        ("refresh", "🌿 Свежести"),
    )),
    Question("temp", "Горячее или холодное?", (
        ("hot", "🔥 Горячее"),
        ("cold", "🧊 Холодное"),
        ("any", "🤷 Без разницы"),
    )),
    Question("strength", "Насколько крепким?", (
        ("strong", "Покрепче"),
        ("medium", "Средне"),
        ("soft", "Помягче"),
    )),
    Question("sweetness", "Что со сладостью?", (
        ("none", "Без сахара"),
        ("some", "Чуть-чуть"),
        ("sweet", "Сладкий"),
    )),
    Question("milk", "Как насчёт молока?", (
        ("dairy", "Люблю с молоком"),
        ("none", "Без молока"),
        ("plant", "Растительное"),
    )),
    Question("snack", "Хотите что-нибудь к напитку?", (
        ("sweet", "Сладкое"),
        ("salty", "Солёное"),
        ("none", "Нет, только напиток"),
    )),
]


# --------------------------------------------------------------------------- #
# Демо-заказы (для баристы и аналитики)
# --------------------------------------------------------------------------- #
_NAMES = ["Анна", "Игорь", "Мария", "Дмитрий", "Елена", "Сергей", "Ольга", "Максим",
          "Юлия", "Алексей", "Наталья", "Павел", "Виктория", "Роман", "Ксения"]
_HOUR_WEIGHTS = [5, 5, 3, 2, 4, 5, 3, 2, 2, 3, 5, 5, 3, 2]  # 08..21


def generate_demo_orders(
    menu: Sequence[MenuItem],
    now: datetime,
    days: int = 7,
    seed: int = 42,
) -> list[Order]:
    """Детерминированно генерирует историю заказов за `days` дней и несколько заказов на сегодня."""
    rng = random.Random(seed)
    used_ids: set[str] = set()
    loads: Counter = Counter()
    orders: list[Order] = []
    weights = [3 if i.popular else 1 for i in menu]
    hours = list(range(OPEN_TIME.hour, CLOSE_TIME.hour))

    def new_id() -> str:
        while True:
            oid = f"BD-{rng.randrange(0x100000, 0xFFFFFF):06X}"
            if oid not in used_ids:
                used_ids.add(oid)
                return oid

    def make(pickup: datetime, status: str) -> Order:
        picked = Counter()
        for it in rng.choices(menu, weights=weights, k=rng.choice([1, 1, 2, 2, 3])):
            picked[it.id] += 1
        items = [{"id": i, "name": next(m.name for m in menu if m.id == i),
                  "qty": q, "price": next(m.price for m in menu if m.id == i)}
                 for i, q in picked.items()]
        return Order(
            id=new_id(),
            customer_name=rng.choice(_NAMES),
            phone="+7900" + "".join(str(rng.randrange(10)) for _ in range(7)),
            pickup_time=fmt_pickup(pickup),
            items=items,
            total=sum(i["qty"] * i["price"] for i in items),
            comment=rng.choice(["", "", "", "Без сахара", "Побольше льда", "Овсяное молоко"]),
            status=status,
            created_at=(pickup - timedelta(minutes=25)).isoformat(timespec="seconds"),
        )

    def random_pickup(day) -> datetime:
        h = rng.choices(hours, weights=_HOUR_WEIGHTS)[0]
        m = rng.randrange(0, 60, SLOT_STEP_MIN)
        return datetime.combine(day, time(h, m))

    # история за прошлые дни
    for d in range(days, 0, -1):
        day = (now - timedelta(days=d)).date()
        for _ in range(rng.randint(14, 26)):
            pickup = random_pickup(day)
            if loads[pickup] >= SLOT_CAPACITY:
                continue
            loads[pickup] += 1
            orders.append(make(pickup, "cancelled" if rng.random() < 0.05 else "issued"))

    # сегодня: уже выданные
    for _ in range(rng.randint(4, 9)):
        pickup = random_pickup(now.date())
        if pickup > now - timedelta(minutes=15) or loads[pickup] >= SLOT_CAPACITY:
            continue
        loads[pickup] += 1
        orders.append(make(pickup, "issued"))

    # сегодня/ближайший день: предзаказы на будущее
    free = [s for s in available_slots(orders, now) if s.start.date() == now.date()][:12]
    for slot in rng.sample(free, k=min(len(free), 6)) if free else []:
        soon = slot.start - now <= timedelta(minutes=30)
        orders.append(make(slot.start, "preparing" if soon else "new"))

    orders.sort(key=lambda o: o.pickup_time)
    return orders
