"""Оформление в стиле референса: тёмный сайдбар, кремовый фон, коралловый акцент."""
from __future__ import annotations

from logic import MenuItem


def html(s: str) -> str:
    """Убирает отступы и пустые строки, чтобы Markdown не превратил HTML в блок кода."""
    return "\n".join(line.strip() for line in s.strip().splitlines() if line.strip())


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Caveat:wght@500;700&display=swap');

html, body, .stApp, [data-testid="stMarkdownContainer"], button, input, textarea {
  font-family: 'Manrope', 'Segoe UI', sans-serif !important;
}
.stApp { background: #FBF5EC; color: #1D1512; }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1560px; }

/* ---------- Сайдбар ---------- */
section[data-testid="stSidebar"] { background: #1B1512; }
section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] span { color: #F6EDE3; }
.logo { font-size: 3.2rem; font-weight: 800; color: #fff; line-height: 1; letter-spacing: -0.04em; margin: .4rem 0 1.6rem .4rem; }
.logo span { display: block; font-size: 1.15rem; font-weight: 500; letter-spacing: .32em; margin-top: .25rem; padding-left: .15rem; }
[class*="st-key-nav"] button {
  background: transparent !important; border: none !important; border-radius: 14px !important;
  justify-content: flex-start !important; padding: .75rem 1rem !important; box-shadow: none !important;
}
[class*="st-key-nav"] button p { color: #F6EDE3 !important; font-weight: 600; font-size: 1.02rem; }
[class*="st-key-nav"] button:hover { background: #2A211C !important; }
[class*="st-key-navon_"] button { background: #3A2E29 !important; }
.hand { font-family: 'Caveat', cursive; color: #FF6B55; font-size: 2rem; line-height: 1.05; margin: 7rem 0 0 .6rem;
        transform: rotate(-6deg); }
.hand::after { content: ""; display: block; width: 120px; height: 4px; border-radius: 4px; background: #FF6B55;
               margin: .6rem 0 0 2.2rem; transform: rotate(-4deg); }

/* ---------- Заголовок ---------- */
.hero-title { font-size: 3.5rem; font-weight: 800; line-height: 1.04; letter-spacing: -0.025em; margin: 0 0 1.4rem; color: #14100E; }
.hero-title .u { background: linear-gradient(#FF5A43, #FF5A43) no-repeat 0 100% / 135px 5px; padding-bottom: 12px; display: inline-block; }

/* ---------- Баннер ---------- */
.hero { position: relative; display: flex; align-items: center; justify-content: space-between; overflow: hidden;
        background: linear-gradient(120deg, #FCE9DE, #F9DCCF 60%, #F4D0C0); border-radius: 28px; padding: 2.2rem 2.6rem; min-height: 310px; }
.hero h2 { font-size: 2.7rem; font-weight: 800; line-height: 1.04; margin: 0 0 1rem; letter-spacing: -0.02em; color: #1D1512; }
.hero p { font-size: 1.05rem; line-height: 1.45; margin: 0 0 1.4rem; color: #2B211D; max-width: 330px; }
.hero .cta { display: inline-block; background: #FF5A43; color: #fff !important; padding: .95rem 1.9rem; border-radius: 999px;
             font-weight: 700; text-decoration: none !important; box-shadow: 0 8px 18px rgba(255,90,67,.28); }
.hero .left { position: relative; z-index: 3; }
.hero .cup { width: 300px; z-index: 2; margin-right: 4rem; }
.hero .stroke { position: absolute; background: linear-gradient(120deg, #FF7B66, #FF5A43); opacity: .85; border-radius: 12px; z-index: 1; }
.hero .s1 { width: 70px; height: 230px; right: 330px; bottom: -30px; transform: skewX(-24deg) rotate(14deg); }
.hero .s2 { width: 60px; height: 190px; right: 140px; bottom: -20px; transform: skewX(-24deg) rotate(-26deg); }
.hero .note { position: absolute; right: 2.2rem; top: 1.4rem; font-family: 'Caveat', cursive; font-size: 1.6rem; line-height: 1;
              transform: rotate(-7deg); color: #2B211D; text-align: left; z-index: 3; }

/* ---------- Карточки-преимущества ---------- */
[class*="st-key-feat_"] { background: #FFFDF9; border: 1px solid #F0E5D6; border-radius: 22px; padding: 1.2rem 1.4rem; }
.feat-t { font-weight: 800; font-size: 1.15rem; margin-bottom: .2rem; }
.feat-d { color: #5C4D45; font-size: .95rem; margin-bottom: .4rem; }

/* ---------- Категории ---------- */
[class*="st-key-pill"] button { border-radius: 999px !important; background: #F3E9DC !important; border: none !important; padding: .55rem 1rem !important; box-shadow: none !important; }
[class*="st-key-pill"] button p { color: #1D1512 !important; font-weight: 600; }
[class*="st-key-pillon_"] button { background: #FF5A43 !important; }
[class*="st-key-pillon_"] button p { color: #fff !important; }

/* ---------- Карточки товаров ---------- */
[class*="st-key-card_"] { background: #FFFDF9; border: 1px solid #F0E5D6; border-radius: 20px; padding: 0 0 .9rem 0;
                          box-shadow: 0 4px 14px rgba(80,50,20,.05); overflow: hidden; gap: .35rem; }
[class*="st-key-card_"] > div { padding-left: 1rem; padding-right: 1rem; }
[class*="st-key-card_"] > div:first-child { padding: 0; }
.tile { position: relative; height: 150px; display: flex; align-items: center; justify-content: center; font-size: 4.4rem; }
.badge { position: absolute; left: 12px; top: 12px; background: #FFE3DB; color: #B93A25; font-size: .78rem; font-weight: 700; padding: .25rem .7rem; border-radius: 999px; }
.pname { font-weight: 800; font-size: 1.12rem; margin-top: .2rem; }
.pdesc { color: #6B5B52; font-size: .85rem; min-height: 2.4em; line-height: 1.25; }
.price { font-weight: 800; font-size: 1.3rem; }
[class*="st-key-add_"], [class*="st-key-addq_"] { display: flex; justify-content: flex-end; }
[class*="st-key-add_"] button { width: 44px; height: 44px; min-height: 44px; border-radius: 50% !important; padding: 0 !important;
                                background: #FF5A43 !important; border: none !important; }
[class*="st-key-add_"] button p { color: #fff !important; font-size: 1.4rem; line-height: 1; }

/* ---------- Кнопки-призывы ---------- */
[class*="st-key-cta_"] button, [class*="st-key-addq_"] button {
  border-radius: 999px !important; background: #FF5A43 !important; border: none !important; padding: .8rem 1.4rem !important;
  box-shadow: 0 8px 18px rgba(255,90,67,.25); }
[class*="st-key-cta_"] button p, [class*="st-key-addq_"] button p { color: #fff !important; font-weight: 700; }
[class*="st-key-cta_"] button:hover, [class*="st-key-addq_"] button:hover { background: #E94830 !important; }

/* ---------- Корзина ---------- */
[class*="st-key-cartpanel"] { background: #FFFDF9; border: 1px solid #F0E5D6; border-radius: 24px; padding: 1.4rem 1.4rem 1.2rem;
                              box-shadow: 0 6px 20px rgba(80,50,20,.06); }
.cart-title { font-size: 1.45rem; font-weight: 800; letter-spacing: .01em; margin-bottom: .6rem; }
.cart-line { display: flex; justify-content: space-between; align-items: flex-start; }
.cart-name { font-weight: 600; }
.cart-sub { color: #6B5B52; font-size: .88rem; }
.cart-sum { font-weight: 700; }
.cart-total { display: flex; justify-content: space-between; align-items: baseline; border-top: 1px solid #F0E5D6; padding-top: .9rem; margin-top: .6rem; }
.cart-total b { font-size: 1.9rem; font-weight: 800; }
.demo-pay { color: #7A6B62; font-size: .8rem; text-align: center; margin-top: .5rem; }
[class*="st-key-dec_"] button, [class*="st-key-inc_"] button, [class*="st-key-del_"] button {
  min-height: 32px; padding: 0 !important; border-radius: 10px !important; border: 1px solid #EADFD0 !important; background: #FBF5EC !important; }

/* ---------- Прочее ---------- */
.page-title { font-size: 2.6rem; font-weight: 800; letter-spacing: -0.02em; line-height: 1.05; margin-bottom: .4rem; }
.page-sub { color: #5C4D45; margin-bottom: 1.2rem; }
.status { display: inline-block; padding: .2rem .7rem; border-radius: 999px; font-size: .8rem; font-weight: 700; background: #F3E9DC; }
.status.new { background: #FFE3DB; color: #B93A25; } .status.preparing { background: #FFF0C7; color: #8A6100; }
.status.ready { background: #D8F0D2; color: #2B6A1E; } .status.issued { background: #E8E4DE; color: #5C4D45; }
.status.cancelled { background: #EEE; color: #888; }
[class*="st-key-ord_"], [class*="st-key-bo_"], [class*="st-key-rec_"] { background: #FFFDF9; border: 1px solid #F0E5D6; border-radius: 20px; padding: 1rem 1.2rem; }
.big-time { font-size: 2rem; font-weight: 800; line-height: 1; }
.match { font-weight: 800; color: #FF5A43; font-size: 1.5rem; }
</style>
"""


def tile_colors(item: MenuItem) -> tuple[str, str]:
    if item.kind == "snack":
        return "#F6E2B8", "#E4BC80"
    if item.category == "Чай":
        return "#E1EBCF", "#BBCD9F"
    if item.temp == "cold":
        return "#DCE9EC", "#B0C9D1"
    return "#EFDAC2", "#CDA67E"


def card_top_html(item: MenuItem) -> str:
    c1, c2 = tile_colors(item)
    badge = f'<span class="badge">{item.badge}</span>' if item.badge else ""
    return html(f"""
        <div class="tile" style="background:linear-gradient(135deg,{c1},{c2})">{badge}<span>{item.emoji}</span></div>
        <div class="pname">{item.name}</div>
        <div class="pdesc">{item.description}</div>
    """)


def hero_html() -> str:
    cup = html("""
    <svg class="cup" viewBox="0 0 300 330" xmlns="http://www.w3.org/2000/svg">
      <ellipse cx="150" cy="318" rx="95" ry="9" fill="rgba(60,30,10,.18)"/>
      <path d="M52 62 L248 62 L222 310 L78 310 Z" fill="#1D1715"/>
      <ellipse cx="150" cy="62" rx="100" ry="24" fill="#F6EEE4"/>
      <ellipse cx="150" cy="62" rx="88" ry="19" fill="#C99A6A"/>
      <path d="M150 78 C124 64 118 48 134 46 C144 45 150 51 150 56 C150 51 156 45 166 46 C182 48 176 64 150 78 Z" fill="#F7EAD9"/>
      <text x="150" y="190" text-anchor="middle" fill="#FFFFFF" font-size="40" font-weight="800" font-family="Manrope, sans-serif">bódro</text>
      <text x="150" y="214" text-anchor="middle" fill="#D9CFC6" font-size="14" letter-spacing="4" font-family="Manrope, sans-serif">coffee</text>
    </svg>
    """)
    return html(f"""
    <div class="hero">
      <div class="stroke s1"></div><div class="stroke s2"></div>
      <div class="left">
        <h2>ЗАКАЖИ.<br>ЗАБЕРИ.<br>БОДРО.</h2>
        <p>Предзаказ ко времени — без очереди. Выбери слот и забери готовый напиток.</p>
        <a class="cta" href="#menu-anchor">Выбрать кофе &nbsp;→</a>
      </div>
      {cup}
      <div class="note">Настоящий<br>кофе<br>с собой ↙</div>
    </div>
    """)
