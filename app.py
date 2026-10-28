"""Бодро кофе — приложение для предзаказа ко времени и подбора напитка (Streamlit)."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from logic import (
    ACTIVE_STATUSES,
    NEXT_STATUS,
    STATUS_LABELS,
    Cart,
    OrderRepository,
    StorageError,
    ValidationError,
    available_slots,
    compute_analytics,
    create_order,
    filter_menu,
    normalize_phone,
    now_local,
    recommend,
    recommend_snack,
    validate_answers,
)
from menu_data import CATEGORIES, CITIES, ITEMS_BY_ID, MENU, QUIZ, generate_demo_orders
from styles import CSS, card_top_html, hero_html, html

st.set_page_config(page_title="Бодро кофе", page_icon="☕", layout="wide")

ORDERS_PATH = Path(
    os.environ.get("BODRO_ORDERS_PATH", Path(__file__).parent / "runtime_data" / "orders.json")
)
NAV = [
    ("menu", "☕  Меню"),
    ("quiz", "✨  Подбор напитка"),
    ("orders", "🧾  Мои заказы"),
    ("barista", "🧑‍🍳  Для баристы"),
    ("analytics", "📊  Аналитика"),
]
ACTION_LABELS = {"preparing": "Взять в работу", "ready": "Готово", "issued": "Выдать клиенту"}


# --------------------------------------------------------------------------- #
# Служебное
# --------------------------------------------------------------------------- #
def rub(n: int) -> str:
    return f"{n:,}".replace(",", "\u00a0") + "\u00a0₽"


def get_repo() -> OrderRepository:
    return OrderRepository(ORDERS_PATH)


def init_state() -> None:
    ss = st.session_state
    ss.setdefault("page", "menu")
    ss.setdefault("category", CATEGORIES[0])
    ss.setdefault("cart", Cart(MENU))
    ss.setdefault("my_orders", [])
    ss.setdefault("quiz_result", None)
    repo = get_repo()
    if not repo.path.exists():
        try:
            repo.save(generate_demo_orders(MENU, now_local()))
        except StorageError as exc:
            st.error(str(exc))


def flash(kind: str, msg: str) -> None:
    st.session_state["flash"] = (kind, msg)


def show_flash() -> None:
    f = st.session_state.pop("flash", None)
    if f:
        {"success": st.success, "error": st.error, "warning": st.warning}.get(f[0], st.info)(f[1])


def load_orders():
    try:
        return get_repo().load()
    except StorageError as exc:
        st.error(str(exc))
        return []


# ---- callbacks ------------------------------------------------------------- #
def go(page: str) -> None:
    st.session_state.page = page


def set_category(cat: str) -> None:
    st.session_state.category = cat


def add_to_cart(item_id: str) -> None:
    try:
        st.session_state.cart.add(item_id)
        st.toast(f"{ITEMS_BY_ID[item_id].name} — в заказе", icon="✅")
    except ValidationError as exc:
        st.toast(str(exc), icon="⚠️")


def cart_dec(item_id: str) -> None:
    st.session_state.cart.decrease(item_id)


def cart_del(item_id: str) -> None:
    st.session_state.cart.remove(item_id)


def do_checkout() -> None:
    ss = st.session_state
    try:
        iso = ss.get("pickup_choice")
        if not iso:
            raise ValidationError("Выберите время получения.")
        repo = get_repo()
        order = create_order(
            ss.cart,
            ss.get("cust_name", ""),
            ss.get("cust_phone", ""),
            datetime.fromisoformat(iso),
            repo.load(),
            ss.get("cust_comment", ""),
            now_local(),
        )
        repo.add(order)
    except ValidationError as exc:
        flash("error", str(exc))
        return
    except StorageError as exc:
        flash("error", f"Не удалось сохранить заказ: {exc}")
        return
    ss.cart.clear()
    ss.my_orders.append(order.id)
    ss["cust_comment"] = ""
    flash(
        "success",
        f"Предзаказ {order.id} принят! Забирайте в {order.pickup:%H:%M} "
        f"({'сегодня' if order.pickup.date() == now_local().date() else 'завтра'}) — без очереди.",
    )


def change_status(order_id: str, status: str) -> None:
    try:
        get_repo().update_status(order_id, status)
    except (ValidationError, StorageError) as exc:
        flash("error", str(exc))


def reset_demo() -> None:
    try:
        get_repo().save(generate_demo_orders(MENU, now_local()))
        st.session_state.my_orders = []
        flash("success", "Демо-данные пересозданы.")
    except StorageError as exc:
        flash("error", str(exc))


# --------------------------------------------------------------------------- #
# Сайдбар
# --------------------------------------------------------------------------- #
def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(html('<div class="logo">bódro<span>coffee</span></div>'), unsafe_allow_html=True)
        for key, label in NAV:
            active = st.session_state.page == key
            st.button(
                label,
                key=f"{'navon' if active else 'nav'}_{key}",
                on_click=go,
                args=(key,),
                use_container_width=True,
            )
        st.markdown('<div class="hand">Больше,<br>чем просто<br>кофе</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Страница «Меню»
# --------------------------------------------------------------------------- #
def render_cart_panel(orders) -> None:
    cart: Cart = st.session_state.cart
    with st.container(key="cartpanel"):
        st.markdown('<div class="cart-title">ТВОЙ ЗАКАЗ</div>', unsafe_allow_html=True)
        if cart.is_empty:
            st.caption("Пока пусто. Добавьте напиток или закуску из меню — или пройдите опрос, и мы подскажем.")
        for line in cart.lines:
            c1, c2, c3 = st.columns([5, 1, 1], vertical_alignment="center")
            c1.markdown(
                html(f"""<div class="cart-name">{line.item.name}</div>
                <div class="cart-sub">{line.qty} × {rub(line.item.price)} = <b>{rub(line.total)}</b></div>"""),
                unsafe_allow_html=True,
            )
            c2.button("−", key=f"dec_{line.item.id}", on_click=cart_dec, args=(line.item.id,))
            c3.button("✕", key=f"del_{line.item.id}", on_click=cart_del, args=(line.item.id,))
        st.markdown(
            html(f'<div class="cart-total"><span><b style="font-size:1.1rem">Итого</b></span><b>{rub(cart.total)}</b></div>'),
            unsafe_allow_html=True,
        )

        st.markdown("**⏱ Забрать ко времени**")
        slots = available_slots(orders, now_local())
        if not slots:
            st.warning("Свободных слотов нет — попробуйте позже.")
        else:
            labels = {}
            today = now_local().date()
            for s in slots:
                day = "Сегодня" if s.start.date() == today else "Завтра"
                labels[s.start.isoformat(timespec="minutes")] = f"{day}, {s.label} · свободно {s.free}"
            if st.session_state.get("pickup_choice") not in labels:
                st.session_state.pop("pickup_choice", None)
            st.selectbox(
                "Время получения",
                options=list(labels),
                format_func=labels.get,
                key="pickup_choice",
                label_visibility="collapsed",
            )
            st.caption("Ваш заказ будет готов к выбранному времени — очередь не нужна.")

        st.text_input("Имя", key="cust_name", placeholder="Как вас зовут", max_chars=40)
        st.text_input("Телефон", key="cust_phone", placeholder="+7 900 123-45-67", max_chars=20)
        st.text_input("Комментарий", key="cust_comment", placeholder="Например: овсяное молоко", max_chars=200)
        st.button(
            "Оформить предзаказ  →",
            key="cta_checkout",
            on_click=do_checkout,
            use_container_width=True,
            disabled=cart.is_empty or not slots,
        )
        st.markdown('<div class="demo-pay">ⓘ Демо-оплата — деньги не списываются</div>', unsafe_allow_html=True)


def render_menu(orders) -> None:
    left, right = st.columns([3.1, 1.25], gap="large")
    with right:
        st.selectbox("Город", CITIES, key="city", label_visibility="collapsed")
        render_cart_panel(orders)
    with left:
        show_flash()
        st.markdown(
            '<div class="hero-title">Твой кофе,<br><span class="u">твои правила.</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(hero_html(), unsafe_allow_html=True)

        f1, f2 = st.columns(2, gap="medium")
        with f1.container(key="feat_time"):
            st.markdown(
                html("""<div class="feat-t">⏱ Заказ ко времени</div>
                <div class="feat-d">Выберите слот — бариста приготовит напиток к вашему приходу. Без очереди.</div>"""),
                unsafe_allow_html=True,
            )
            st.caption("Выберите время в блоке «Твой заказ» справа →")
        with f2.container(key="feat_quiz"):
            st.markdown(
                html("""<div class="feat-t">✨ Не знаете, что выбрать?</div>
                <div class="feat-d">Ответьте на 6 коротких вопросов — подберём напиток под настроение.</div>"""),
                unsafe_allow_html=True,
            )
            st.button("Пройти опрос", key="cta_quiz", on_click=go, args=("quiz",))

        st.markdown('<div id="menu-anchor" style="height:1rem"></div>', unsafe_allow_html=True)
        pills = st.columns(len(CATEGORIES))
        for col, cat in zip(pills, CATEGORIES):
            active = cat == st.session_state.category
            col.button(
                cat,
                key=f"{'pillon' if active else 'pill'}_{cat}",
                on_click=set_category,
                args=(cat,),
                use_container_width=True,
            )

        items = filter_menu(MENU, st.session_state.category)
        for start in range(0, len(items), 3):
            cols = st.columns(3, gap="medium")
            for col, item in zip(cols, items[start:start + 3]):
                with col.container(key=f"card_{item.id}"):
                    st.markdown(card_top_html(item), unsafe_allow_html=True)
                    c1, c2 = st.columns([3, 1], vertical_alignment="center")
                    c1.markdown(f'<div class="price">{rub(item.price)}</div>', unsafe_allow_html=True)
                    c2.button("＋", key=f"add_{item.id}", on_click=add_to_cart, args=(item.id,))


# --------------------------------------------------------------------------- #
# Страница «Подбор напитка»
# --------------------------------------------------------------------------- #
def render_quiz() -> None:
    st.markdown('<div class="page-title">Подберём напиток<br>под ваше настроение</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">6 вопросов — и мы покажем три лучших варианта.</div>', unsafe_allow_html=True)
    show_flash()

    with st.form("quiz_form"):
        answers = {}
        for q in QUIZ:
            labels = dict(q.options)
            answers[q.id] = st.radio(
                q.text, options=list(labels), format_func=labels.get, index=None, key=f"quiz_{q.id}"
            )
        submitted = st.form_submit_button("Подобрать напиток", key="quiz_submit")

    if submitted:
        try:
            clean = validate_answers(answers, QUIZ)
            st.session_state.quiz_result = {
                "recs": recommend(clean, MENU, QUIZ, top_n=3),
                "snack": recommend_snack(clean, MENU),
            }
        except ValidationError as exc:
            st.session_state.quiz_result = None
            st.error(str(exc))

    result = st.session_state.get("quiz_result")
    if not result:
        return
    st.markdown("### Ваши лучшие совпадения")
    cols = st.columns(len(result["recs"]), gap="medium")
    for col, rec in zip(cols, result["recs"]):
        with col.container(key=f"rec_{rec.item.id}"):
            st.markdown(
                html(f"""<div class="match">{rec.percent}% совпадение</div>
                <div class="pname" style="font-size:1.3rem">{rec.item.emoji} {rec.item.name}</div>
                <div class="pdesc">{rec.item.description}</div>
                <div class="cart-sub">Почему: {', '.join(rec.reasons) if rec.reasons else 'вариант на пробу'}.</div>
                <div class="price" style="margin:.5rem 0">{rub(rec.item.price)}</div>"""),
                unsafe_allow_html=True,
            )
            st.button("Добавить в заказ", key=f"addq_{rec.item.id}", on_click=add_to_cart, args=(rec.item.id,))
    snack = result.get("snack")
    if snack:
        with st.container(key="rec_snack"):
            c1, c2 = st.columns([4, 1], vertical_alignment="center")
            c1.markdown(
                f"**К напитку подойдёт:** {snack.emoji} {snack.name} — {snack.description} · {rub(snack.price)}"
            )
            c2.button("Добавить", key=f"addq_{snack.id}", on_click=add_to_cart, args=(snack.id,))
    st.button("Перейти к оформлению заказа  →", key="cta_to_menu", on_click=go, args=("menu",))


# --------------------------------------------------------------------------- #
# Страница «Мои заказы»
# --------------------------------------------------------------------------- #
def status_badge(status: str) -> str:
    return f'<span class="status {status}">{STATUS_LABELS[status]}</span>'


def cancel_order(order_id: str) -> None:
    try:
        get_repo().cancel(order_id)
        flash("success", "Заказ отменён.")
    except (ValidationError, StorageError) as exc:
        flash("error", str(exc))


def render_orders(orders) -> None:
    st.markdown('<div class="page-title">Мои заказы</div>', unsafe_allow_html=True)
    show_flash()
    phone_raw = st.text_input("Найти заказы по номеру телефона", key="lookup_phone", placeholder="+7 900 123-45-67")
    mine = {o.id: o for o in orders if o.id in st.session_state.my_orders}
    if phone_raw.strip():
        try:
            phone = normalize_phone(phone_raw)
            for o in orders:
                if o.phone == phone:
                    mine[o.id] = o
        except ValidationError as exc:
            st.warning(str(exc))
    if not mine:
        st.info("Здесь появятся ваши предзаказы. Оформите первый на странице «Меню».")
        return
    for o in sorted(mine.values(), key=lambda x: x.pickup_time, reverse=True):
        with st.container(key=f"ord_{o.id}"):
            c1, c2 = st.columns([4, 1], vertical_alignment="center")
            items = ", ".join(f"{i['name']} × {i['qty']}" for i in o.items)
            c1.markdown(
                html(f"""<b>{o.id}</b> &nbsp; {status_badge(o.status)}
                <div class="cart-sub">Получение: {o.pickup:%d.%m в %H:%M} · {o.customer_name}</div>
                <div>{items}</div>
                <div class="cart-name">Итого: {rub(o.total)}</div>"""),
                unsafe_allow_html=True,
            )
            if o.status == "new":
                c2.button("Отменить", key=f"cancel_{o.id}", on_click=cancel_order, args=(o.id,))


# --------------------------------------------------------------------------- #
# Страница «Для баристы»
# --------------------------------------------------------------------------- #
def render_barista(orders) -> None:
    st.markdown('<div class="page-title">Заказы для баристы</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Очередь по времени получения: готовьте напитки заранее.</div>', unsafe_allow_html=True)
    show_flash()
    counts = {s: sum(1 for o in orders if o.status == s) for s in ACTIVE_STATUSES}
    m1, m2, m3 = st.columns(3)
    m1.metric("Новые", counts["new"])
    m2.metric("Готовятся", counts["preparing"])
    m3.metric("Готовы к выдаче", counts["ready"])

    active = sorted((o for o in orders if o.status in ACTIVE_STATUSES), key=lambda o: o.pickup_time)
    if not active:
        st.success("Все заказы выданы. Можно выдохнуть ☕")
        return
    for o in active:
        with st.container(key=f"bo_{o.id}"):
            c1, c2, c3 = st.columns([1.2, 4, 1.6], vertical_alignment="center")
            c1.markdown(
                f'<div class="big-time">{o.pickup:%H:%M}</div><div class="cart-sub">{o.pickup:%d.%m}</div>',
                unsafe_allow_html=True,
            )
            items = ", ".join(f"{i['name']} × {i['qty']}" for i in o.items)
            comment = f'<div class="cart-sub">💬 {o.comment}</div>' if o.comment else ""
            c2.markdown(
                html(f"""<b>{o.id}</b> · {o.customer_name} · {o.phone} &nbsp; {status_badge(o.status)}
                <div>{items}</div>{comment}"""),
                unsafe_allow_html=True,
            )
            nxt = NEXT_STATUS.get(o.status)
            if nxt:
                c3.button(ACTION_LABELS[nxt], key=f"cta_st_{o.id}", on_click=change_status, args=(o.id, nxt))


# --------------------------------------------------------------------------- #
# Страница «Аналитика»
# --------------------------------------------------------------------------- #
def render_analytics(orders) -> None:
    st.markdown('<div class="page-title">Аналитика</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Загрузка по часам помогает планировать смены и сглаживать пики с помощью слотов.</div>', unsafe_allow_html=True)
    show_flash()
    stats = compute_analytics(orders)
    m = st.columns(4)
    m[0].metric("Заказов", stats["orders"])
    m[1].metric("Выручка", rub(stats["revenue"]))
    m[2].metric("Средний чек", rub(stats["avg_check"]))
    m[3].metric("Пик загрузки", f"{stats['peak_hour']:02d}:00" if stats["peak_hour"] is not None else "—")

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("**Топ позиций (порций)**")
        if stats["top_items"]:
            df = pd.DataFrame({"Порций": [q for _, q in stats["top_items"]]}, index=[n for n, _ in stats["top_items"]])
            st.bar_chart(df, color="#FF5A43")
    with c2:
        st.markdown("**Заказы по часам получения**")
        df = pd.DataFrame(
            {"Заказов": list(stats["by_hour"].values())},
            index=[f"{h:02d}:00" for h in stats["by_hour"]],
        )
        st.bar_chart(df, color="#FF5A43")
    st.markdown("**Статусы заказов**")
    st.table(pd.DataFrame(
        {"Заказов": [stats["by_status"].get(s, 0) for s in STATUS_LABELS]},
        index=list(STATUS_LABELS.values()),
    ))
    st.button("Пересоздать демо-данные", key="reset_demo", on_click=reset_demo)


# --------------------------------------------------------------------------- #
# Точка входа
# --------------------------------------------------------------------------- #
def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    init_state()
    render_sidebar()
    orders = load_orders()
    page = st.session_state.page
    if page == "menu":
        render_menu(orders)
    elif page == "quiz":
        render_quiz()
    elif page == "orders":
        render_orders(orders)
    elif page == "barista":
        render_barista(orders)
    elif page == "analytics":
        render_analytics(orders)


main()
