"""Бизнес-логика приложения «Бодро кофе».

Модуль не зависит от Streamlit, поэтому его легко тестировать отдельно.
Содержит:
  * модель меню и корзину;
  * слоты предзаказа «ко времени» с ограничением по загрузке (чтобы не было очереди);
  * валидацию ввода и создание заказа;
  * хранилище заказов (JSON-файл);
  * опрос и подбор напитка;
  * аналитику.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Iterable, Optional, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# --------------------------------------------------------------------------- #
# Константы
# --------------------------------------------------------------------------- #
TZ_NAME = "Europe/Moscow"
OPEN_TIME = time(8, 0)          # открытие кофейни
CLOSE_TIME = time(22, 0)        # закрытие (последний слот начинается за 10 мин до закрытия)
SLOT_STEP_MIN = 10              # шаг слотов
MIN_LEAD_MIN = 10               # минимум минут до получения заказа
MAX_DAYS_AHEAD = 2              # на сколько дней вперёд можно заказывать
SLOT_CAPACITY = 4               # сколько заказов бариста готовит в один слот
MAX_ITEM_QTY = 10               # максимум одной позиции
MAX_COMMENT_LEN = 200

POPULAR = "Популярное"

STATUS_LABELS = {
    "new": "Принят",
    "preparing": "Готовится",
    "ready": "Готов к выдаче",
    "issued": "Выдан",
    "cancelled": "Отменён",
}
NEXT_STATUS = {"new": "preparing", "preparing": "ready", "ready": "issued"}
ALLOWED_TRANSITIONS = {
    "new": {"preparing", "cancelled"},
    "preparing": {"ready"},
    "ready": {"issued"},
    "issued": set(),
    "cancelled": set(),
}
ACTIVE_STATUSES = ("new", "preparing", "ready")


class ValidationError(ValueError):
    """Ошибка пользовательского ввода или нарушение бизнес-правила."""


class StorageError(RuntimeError):
    """Ошибка чтения/записи хранилища заказов."""


def now_local() -> datetime:
    """Текущее время в часовом поясе кофеен (без tzinfo)."""
    try:
        return datetime.now(ZoneInfo(TZ_NAME)).replace(tzinfo=None)
    except ZoneInfoNotFoundError:  # нет базы часовых поясов
        return datetime.now()


# --------------------------------------------------------------------------- #
# Меню и корзина
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class MenuItem:
    id: str
    name: str
    category: str
    description: str
    price: int
    emoji: str = "☕"
    kind: str = "drink"                  # drink | snack
    badge: Optional[str] = None
    popular: bool = False
    # атрибуты для подбора напитка
    temp: Optional[str] = None           # hot | cold
    strength: int = 0                    # 1..5
    sweetness: int = 0                   # 1..5
    milk: bool = False
    plant_ok: bool = False               # можно заменить на растительное молоко
    tags: tuple = ()                     # energy | calm | treat | refresh | sweet | salty


def filter_menu(menu: Iterable[MenuItem], category: str) -> list[MenuItem]:
    if category == POPULAR:
        return [i for i in menu if i.popular]
    return [i for i in menu if i.category == category]


@dataclass
class CartLine:
    item: MenuItem
    qty: int

    @property
    def total(self) -> int:
        return self.item.price * self.qty


class Cart:
    """Корзина: хранит количество по id позиции."""

    def __init__(self, menu: Iterable[MenuItem]):
        self._menu = {i.id: i for i in menu}
        self._qty: dict[str, int] = {}

    def add(self, item_id: str, qty: int = 1) -> None:
        if item_id not in self._menu:
            raise ValidationError("Такой позиции нет в меню.")
        if not isinstance(qty, int) or qty < 1:
            raise ValidationError("Количество должно быть положительным числом.")
        new_qty = self._qty.get(item_id, 0) + qty
        if new_qty > MAX_ITEM_QTY:
            raise ValidationError(f"Не более {MAX_ITEM_QTY} шт. одной позиции в заказе.")
        self._qty[item_id] = new_qty

    def decrease(self, item_id: str) -> None:
        if item_id not in self._qty:
            return
        self._qty[item_id] -= 1
        if self._qty[item_id] <= 0:
            del self._qty[item_id]

    def remove(self, item_id: str) -> None:
        self._qty.pop(item_id, None)

    def clear(self) -> None:
        self._qty.clear()

    @property
    def lines(self) -> list[CartLine]:
        return [CartLine(self._menu[i], q) for i, q in self._qty.items()]

    @property
    def total(self) -> int:
        return sum(line.total for line in self.lines)

    @property
    def count(self) -> int:
        return sum(self._qty.values())

    @property
    def is_empty(self) -> bool:
        return not self._qty

    def snapshot(self) -> list[dict]:
        return [
            {"id": l.item.id, "name": l.item.name, "qty": l.qty, "price": l.item.price}
            for l in self.lines
        ]


# --------------------------------------------------------------------------- #
# Заказы
# --------------------------------------------------------------------------- #
@dataclass
class Order:
    id: str
    customer_name: str
    phone: str
    pickup_time: str          # ISO "YYYY-MM-DDTHH:MM"
    items: list
    total: int
    comment: str = ""
    status: str = "new"
    created_at: str = ""

    @property
    def pickup(self) -> datetime:
        return datetime.fromisoformat(self.pickup_time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Order":
        try:
            order = cls(
                id=str(d["id"]),
                customer_name=str(d["customer_name"]),
                phone=str(d["phone"]),
                pickup_time=str(d["pickup_time"]),
                items=list(d["items"]),
                total=int(d["total"]),
                comment=str(d.get("comment", "")),
                status=str(d.get("status", "new")),
                created_at=str(d.get("created_at", "")),
            )
            order.pickup  # проверка формата даты
            if order.status not in STATUS_LABELS:
                raise ValueError("unknown status")
            return order
        except (KeyError, TypeError, ValueError) as exc:
            raise StorageError(f"Повреждённая запись заказа: {exc}") from exc


def new_order_id() -> str:
    return "BD-" + uuid.uuid4().hex[:6].upper()


def fmt_pickup(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


# ----- Валидация ввода ------------------------------------------------------ #
_NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё\s\-']{1,39}$")
_PHONE_CHARS_RE = re.compile(r"^[\d\s()+\-]+$")


def validate_name(name: str) -> str:
    name = re.sub(r"\s+", " ", (name or "").strip())
    if not name:
        raise ValidationError("Укажите имя, чтобы бариста мог позвать вас.")
    if not _NAME_RE.match(name):
        raise ValidationError("Имя: 2–40 символов, только буквы, пробел и дефис.")
    return name


def normalize_phone(phone: str) -> str:
    """Приводит телефон к формату +7XXXXXXXXXX или бросает ValidationError."""
    raw = (phone or "").strip()
    if not raw:
        raise ValidationError("Укажите номер телефона.")
    if not _PHONE_CHARS_RE.match(raw):
        raise ValidationError("Телефон может содержать только цифры, пробелы, скобки, + и дефис.")
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] in "78":
        digits = digits[1:]
    if len(digits) != 10:
        raise ValidationError("Введите телефон в формате +7 900 123-45-67.")
    return "+7" + digits


def validate_comment(comment: str) -> str:
    comment = (comment or "").strip()
    if len(comment) > MAX_COMMENT_LEN:
        raise ValidationError(f"Комментарий не длиннее {MAX_COMMENT_LEN} символов.")
    return comment


# ----- Слоты «ко времени» --------------------------------------------------- #
@dataclass(frozen=True)
class Slot:
    start: datetime
    free: int

    @property
    def label(self) -> str:
        return self.start.strftime("%H:%M")


def _ceil_to_step(dt: datetime, step: int = SLOT_STEP_MIN) -> datetime:
    base = dt.replace(second=0, microsecond=0)
    if dt > base:
        base += timedelta(minutes=1)
    extra = (-(base.hour * 60 + base.minute)) % step
    return base + timedelta(minutes=extra)


def slot_loads(orders: Iterable[Order]) -> dict[datetime, int]:
    """Сколько активных заказов приходится на каждый слот."""
    loads: dict[datetime, int] = {}
    for o in orders:
        if o.status == "cancelled":
            continue
        try:
            t = o.pickup
        except ValueError:
            continue
        loads[t] = loads.get(t, 0) + 1
    return loads


def _day_slots(day, earliest: datetime, loads: dict, capacity: int) -> list[Slot]:
    slots: list[Slot] = []
    cur = datetime.combine(day, OPEN_TIME)
    end = datetime.combine(day, CLOSE_TIME)
    while cur < end:
        if cur >= earliest:
            free = capacity - loads.get(cur, 0)
            if free > 0:
                slots.append(Slot(cur, free))
        cur += timedelta(minutes=SLOT_STEP_MIN)
    return slots


def available_slots(
    orders: Iterable[Order],
    now: Optional[datetime] = None,
    capacity: int = SLOT_CAPACITY,
) -> list[Slot]:
    """Свободные слоты на ближайший рабочий день (сегодня, а если уже закрыто — завтра)."""
    now = now or now_local()
    loads = slot_loads(orders)
    earliest = _ceil_to_step(now + timedelta(minutes=MIN_LEAD_MIN))
    for offset in range(0, MAX_DAYS_AHEAD):
        day = earliest.date() + timedelta(days=offset)
        slots = _day_slots(day, earliest, loads, capacity)
        if slots:
            return slots
    return []


def validate_pickup(
    pickup: datetime,
    orders: Iterable[Order],
    now: Optional[datetime] = None,
    capacity: int = SLOT_CAPACITY,
) -> None:
    now = now or now_local()
    if pickup.second or pickup.microsecond or pickup.minute % SLOT_STEP_MIN:
        raise ValidationError(f"Время получения должно быть кратно {SLOT_STEP_MIN} минутам.")
    if not (OPEN_TIME <= pickup.time() < CLOSE_TIME):
        raise ValidationError(
            f"Кофейня работает с {OPEN_TIME:%H:%M} до {CLOSE_TIME:%H:%M}."
        )
    if pickup < now + timedelta(minutes=MIN_LEAD_MIN):
        raise ValidationError(
            f"Заказ нужно оформить минимум за {MIN_LEAD_MIN} минут до получения."
        )
    if pickup > now + timedelta(days=MAX_DAYS_AHEAD):
        raise ValidationError(f"Предзаказ доступен не более чем на {MAX_DAYS_AHEAD} дня вперёд.")
    if slot_loads(orders).get(pickup, 0) >= capacity:
        raise ValidationError("На это время все места уже заняты — выберите другое.")


def create_order(
    cart: Cart,
    name: str,
    phone: str,
    pickup: datetime,
    existing_orders: Sequence[Order],
    comment: str = "",
    now: Optional[datetime] = None,
    capacity: int = SLOT_CAPACITY,
) -> Order:
    """Проверяет все данные и собирает заказ (сохранением занимается репозиторий)."""
    now = now or now_local()
    if cart.is_empty:
        raise ValidationError("Корзина пуста — добавьте напиток или закуску.")
    name = validate_name(name)
    phone = normalize_phone(phone)
    comment = validate_comment(comment)
    validate_pickup(pickup, existing_orders, now, capacity)
    return Order(
        id=new_order_id(),
        customer_name=name,
        phone=phone,
        pickup_time=fmt_pickup(pickup),
        items=cart.snapshot(),
        total=cart.total,
        comment=comment,
        status="new",
        created_at=now.isoformat(timespec="seconds"),
    )


# ----- Хранилище ------------------------------------------------------------ #
class OrderRepository:
    """Простое хранилище заказов в JSON-файле (атомарная запись)."""

    def __init__(self, path):
        self.path = Path(path)

    def load(self) -> list[Order]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raise ValueError("ожидался список")
        except (json.JSONDecodeError, ValueError):
            # файл повреждён: сохраняем копию и начинаем с чистого листа
            try:
                self.path.replace(self.path.with_suffix(".corrupt"))
            except OSError:
                pass
            return []
        except OSError as exc:
            raise StorageError(f"Не удалось прочитать заказы: {exc}") from exc
        orders = []
        for d in raw:
            try:
                orders.append(Order.from_dict(d))
            except StorageError:
                continue  # пропускаем битые записи
        return orders

    def save(self, orders: Iterable[Order]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump([o.to_dict() for o in orders], f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except OSError as exc:
            raise StorageError(f"Не удалось сохранить заказы: {exc}") from exc

    def add(self, order: Order) -> None:
        orders = self.load()
        orders.append(order)
        self.save(orders)

    def update_status(self, order_id: str, new_status: str) -> Order:
        if new_status not in STATUS_LABELS:
            raise ValidationError("Неизвестный статус.")
        orders = self.load()
        for o in orders:
            if o.id == order_id:
                if new_status not in ALLOWED_TRANSITIONS[o.status]:
                    raise ValidationError(
                        f"Нельзя перевести заказ из «{STATUS_LABELS[o.status]}» "
                        f"в «{STATUS_LABELS[new_status]}»."
                    )
                o.status = new_status
                self.save(orders)
                return o
        raise ValidationError("Заказ не найден.")

    def cancel(self, order_id: str) -> Order:
        return self.update_status(order_id, "cancelled")


# --------------------------------------------------------------------------- #
# Опрос и подбор напитка
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Question:
    id: str
    text: str
    options: tuple  # ((value, label), ...)


@dataclass(frozen=True)
class Recommendation:
    item: MenuItem
    score: int
    percent: int
    reasons: tuple


MAX_SCORE = 13  # 3 (температура) + 3 (крепость) + 3 (сладость) + 2 (молоко) + 2 (настроение)
_STRENGTH_TARGET = {"strong": 5, "medium": 3, "soft": 1}
_SWEET_TARGET = {"none": 1, "some": 3, "sweet": 5}
_MOOD_TEXT = {
    "energy": "бодрит",
    "calm": "успокаивает и согревает",
    "treat": "порадует вас",
    "refresh": "освежает",
}


def validate_answers(answers: dict, questions: Sequence[Question]) -> dict:
    clean = {}
    for q in questions:
        value = (answers or {}).get(q.id)
        valid = {v for v, _ in q.options}
        if value not in valid:
            raise ValidationError(f"Ответьте на вопрос: «{q.text}»")
        clean[q.id] = value
    return clean


def score_item(item: MenuItem, a: dict) -> tuple[int, list[str]]:
    score, reasons = 0, []

    # температура
    if a["temp"] != "any":
        if item.temp == a["temp"]:
            score += 3
            reasons.append("горячий, как вы хотели" if a["temp"] == "hot" else "холодный и освежающий")
        else:
            score -= 5

    # крепость
    diff = abs(item.strength - _STRENGTH_TARGET[a["strength"]])
    score += 3 - diff
    if diff == 0:
        reasons.append("крепость в точку")
    elif diff == 1:
        reasons.append("подходящая крепость")

    # сладость
    diff = abs(item.sweetness - _SWEET_TARGET[a["sweetness"]])
    score += 3 - diff
    if diff == 0:
        reasons.append("сладость как вы любите")
    elif diff == 1:
        reasons.append("в меру сладкий")

    # молоко
    milk = a["milk"]
    if milk == "dairy":
        if item.milk:
            score += 2
            reasons.append("с нежным молоком")
    elif milk == "none":
        if not item.milk:
            score += 2
            reasons.append("без молока")
        else:
            score -= 3
    elif milk == "plant":
        if item.milk and item.plant_ok:
            score += 2
            reasons.append("можно на растительном молоке")
        elif item.milk:
            score -= 2
        else:
            score += 1

    # настроение
    if a["mood"] in item.tags:
        score += 2
        reasons.append(_MOOD_TEXT[a["mood"]])

    return score, reasons


def recommend(
    answers: dict,
    menu: Sequence[MenuItem],
    questions: Sequence[Question],
    top_n: int = 3,
) -> list[Recommendation]:
    a = validate_answers(answers, questions)
    scored = []
    for item in menu:
        if item.kind != "drink":
            continue
        score, reasons = score_item(item, a)
        percent = max(0, min(100, round(max(score, 0) / MAX_SCORE * 100)))
        scored.append(Recommendation(item, score, percent, tuple(reasons)))
    scored.sort(key=lambda r: (-r.score, not r.item.popular, r.item.name))
    return scored[:top_n]


def recommend_snack(answers: dict, menu: Sequence[MenuItem]) -> Optional[MenuItem]:
    pref = (answers or {}).get("snack")
    if pref not in ("sweet", "salty"):
        return None
    candidates = [i for i in menu if i.kind == "snack" and pref in i.tags]
    candidates.sort(key=lambda i: (not i.popular, i.price))
    return candidates[0] if candidates else None


# --------------------------------------------------------------------------- #
# Аналитика
# --------------------------------------------------------------------------- #
def compute_analytics(orders: Sequence[Order]) -> dict:
    valid = [o for o in orders if o.status != "cancelled"]
    revenue = sum(o.total for o in valid)
    count = len(valid)
    items: Counter = Counter()
    for o in valid:
        for it in o.items:
            items[it["name"]] += int(it["qty"])
    hours = Counter(o.pickup.hour for o in valid)
    by_hour = {h: hours.get(h, 0) for h in range(OPEN_TIME.hour, CLOSE_TIME.hour)}
    return {
        "orders": count,
        "revenue": revenue,
        "avg_check": round(revenue / count) if count else 0,
        "cancelled": sum(1 for o in orders if o.status == "cancelled"),
        "top_items": items.most_common(7),
        "by_hour": by_hour,
        "peak_hour": max(by_hour, key=by_hour.get) if count else None,
        "by_status": dict(Counter(o.status for o in orders)),
    }
