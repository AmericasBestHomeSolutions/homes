"""Condition, cash, and terms blocks read from data/home-facts.json.

The generator (scripts/seo_pages.py) bakes the HTML into each listing page.
Prices, down payment, monthly payment, and status stay in homes.js. This file
never stores them. A missing fact renders as "Not yet known".

Seed rows come only from the contractor note on a home, and only when that
note names the system. Status is "reported", never "verified". Descriptions
are not read. Same file in the homes and casas repos.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

PATH = Path("data") / "home-facts.json"

# Joe confirmed both on 2026-11-26. They still publish the navy hold line,
# the listing-step hold sentence, and the Wyoming address on the navy block.
# The scam answer is only scam_paragraphs.
CONFIRM_TOUR_BEFORE_PAY = True
CONFIRM_WYOMING_ADDRESS = True


def scam_paragraphs(lang: str = "en") -> list[str]:
    """The scam answer, one paragraph per item. Nothing else is appended."""
    if lang == "es":
        return [
            "No. Suena diferente porque casi todos conocen una sola forma de comprar casa: con un préstamo del banco. Aquí, el vendedor financia la casa, así que no hay banco de por medio.",
            "Solo necesita una identificación válida, el enganche y un pago mensual que se ajuste a su presupuesto. La página de cada casa muestra su enganche y su pago mensual.",
            "Las casas se venden tal como están, por eso usted las visita en persona antes de pagar cualquier cosa para apartarlas. Firma los papeles antes de recibir las llaves.",
            "Joseph Hernandez, Director Ejecutivo de Americas Best Home Solutions LLC, y su equipo lo acompañan desde la primera visita hasta las llaves.",
        ]
    return [
        "No. It sounds unusual because most people only know one way to buy a home: a bank loan. Here, the seller finances the home, so there's no bank in the middle.",
        "All you need is a valid ID, the down payment, and a monthly payment that fits your budget. Each home shows its down payment and monthly on its page.",
        "Homes are sold as-is, so you tour in person before you pay anything to hold one. You sign the paperwork before you get the keys.",
        "Joseph Hernandez, Executive Director of Americas Best Home Solutions LLC, and his team are with you from first tour to keys.",
    ]


def scam_answer(lang: str = "en") -> str:
    """Scam answer as one line for JSON-LD. Paragraphs are joined with spaces."""
    return " ".join(scam_paragraphs(lang))


def scam_answer_html(lang: str = "en") -> str:
    """Scam answer as separate paragraphs for HTML."""
    return "".join(f"<p>{_esc(part)}</p>" for part in scam_paragraphs(lang))


def walkthrough_line(lang: str = "en") -> str:
    """Navy-block line. Hold and office sentences follow the flags above."""
    if lang == "es":
        line = (
            'Cada casa se recorre en persona, y no le pediremos dinero para "apartar" una casa en la que no ha estado.'
            if CONFIRM_TOUR_BEFORE_PAY
            else "Cada casa se recorre en persona antes de decidir."
        )
        if CONFIRM_WYOMING_ADDRESS:
            line += " La oficina está en 30 N Gould St, Ste R, Sheridan, WY 82801."
        return line
    line = (
        'Every home is walked in person, and you\'ll never be asked for money to "hold" a home you haven\'t stood in.'
        if CONFIRM_TOUR_BEFORE_PAY
        else "Every home is walked in person before you decide."
    )
    if CONFIRM_WYOMING_ADDRESS:
        line += " The office address is 30 N Gould St, Ste R, Sheridan, WY 82801."
    return line


def pets_qa(lang: str = "en") -> tuple[str, str]:
    """Question and answer for the sheet and the FAQ."""
    if lang == "es":
        return ("¿Se permiten mascotas?", "Sí, se permiten mascotas.")
    return ("Are pets allowed?", "Yes, pets are allowed.")


def hold_line(lang: str = "en") -> str:
    """Extra listing sentence. Empty unless CONFIRM_TOUR_BEFORE_PAY is True."""
    if not CONFIRM_TOUR_BEFORE_PAY:
        return ""
    if lang == "es":
        return "No le pediremos dinero para apartar una casa que no ha visto."
    return "We'll never ask for money to hold a home you haven't seen."


SYSTEMS = ("furnace", "plumbing", "electrical", "roof", "foundation")
SYSTEM_LABELS = {
    "en": {
        "furnace": "Furnace / heating",
        "plumbing": "Plumbing",
        "electrical": "Electrical",
        "roof": "Roof",
        "foundation": "Foundation",
    },
    "es": {
        "furnace": "Calefacción",
        "plumbing": "Plomería",
        "electrical": "Electricidad",
        "roof": "Techo",
        "foundation": "Cimientos",
    },
}
# A system is recorded only when the contractor note names it.
_RULES = (
    ("furnace", re.compile(r"\b(furnaces?|hvac|heating)\b", re.I)),
    ("plumbing", re.compile(r"\bplumb(?:ing|er)\b", re.I)),
    ("electrical", re.compile(r"\b(electrical|electric|wiring|rewire)\b", re.I)),
    ("roof", re.compile(r"\broofs?\b", re.I)),
    ("foundation", re.compile(r"\bfoundations?\b", re.I)),
)
# Spanish for the clauses this catalog actually produces. Unknown clauses stay
# out of the file rather than being guessed.
_ES = {
    "Slate roof needs repair or replacement (duplex)": "El techo de pizarra necesita reparación o reemplazo (dúplex)",
    "No electrical (copper wiring taken)": "No hay instalación eléctrica (se llevaron el cableado de cobre)",
    "Furnace needs work": "La calefacción necesita trabajo",
    "Roof needs some repair": "El techo necesita algo de reparación",
    "Wiring pulled from the fuse box": "El cableado fue retirado de la caja de fusibles",
    "Hole in the roof that needs repair": "Hay un agujero en el techo que necesita reparación",
    "Needs a new roof": "Necesita un techo nuevo",
    "New electrical": "Electricidad nueva",
    "Plumbing": "Plomería",
    "Plumbing needs a licensed plumber": "La plomería necesita un plomero con licencia",
    "Full electrical rewire": "Hay que volver a cablear toda la electricidad",
    "Electric meter removed and power is off": "Quitaron el medidor eléctrico y no hay luz",
    "Electrical service must be updated before power can be restored": "Hay que actualizar el servicio eléctrico antes de restablecer la luz",
    "Basement needs foundation repair": "El sótano necesita reparación de los cimientos",
    "Plumbing, HVAC and electrical all need work from licensed pros": "La plomería, la calefacción y la electricidad necesitan trabajo de profesionales con licencia",
    "Needs plumbing work": "Necesita trabajo de plomería",
    "A new furnace and AC unit": "Una calefacción y un aire acondicionado nuevos",
    "Needs plumbing, electrical and mechanicals": "Necesita plomería, electricidad y sistemas mecánicos",
    "Needs electrical and mechanical work": "Necesita trabajo eléctrico y mecánico",
    "Needs a new roof, new electrical and plumbing, drywall, and a rebuilt kitchen and bath": "Necesita un techo nuevo, electricidad y plomería nuevas, tablaroca, y una cocina y un baño reconstruidos",
    "Needs plumbing work, a new furnace and AC unit, and new siding": "Necesita trabajo de plomería, una calefacción y un aire acondicionado nuevos, y revestimiento nuevo",
}


def _cap(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip(" ,.;")
    if not text:
        return ""
    return text[0].upper() + text[1:]


def notes_to_systems(note: str) -> dict[str, str]:
    """Map a contractor note to {system: English clause}. Unnamed systems are omitted.

    A clause is the semicolon-separated piece that names the system, quoted,
    not a paraphrase. A piece that names several systems is stored on each one.
    """
    found: dict[str, list[str]] = {}
    for segment in re.split(r";", note or ""):
        segment = segment.strip()
        if not segment:
            continue
        clause = _cap(segment)
        for key, rx in _RULES:
            if rx.search(segment) and clause not in found.get(key, []):
                found.setdefault(key, []).append(clause)
    return {key: "; ".join(clauses) for key, clauses in found.items()}


def es_for(clause: str) -> str:
    if clause in _ES:
        return _ES[clause]
    parts = [p.strip() for p in clause.split(";") if p.strip()]
    if parts and all(p in _ES for p in parts):
        return "; ".join(_ES[p] for p in parts)
    raise KeyError(clause)


def load(root: Path) -> dict:
    path = Path(root) / PATH
    if not path.is_file():
        return {"version": 1, "updated": "", "homes": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("homes", {})
    return data


def seed_document(homes: list[dict], updated: str = "2026-11-25") -> dict:
    """Build home-facts.json from contractor notes. Homes with no named system are omitted."""
    body = {}
    for home in homes:
        note = home.get("contractor")
        if not isinstance(note, str) or not note.strip():
            continue
        systems = notes_to_systems(note)
        if not systems:
            continue
        condition = {}
        for key, clause in systems.items():
            condition[key] = {
                "status": "reported",
                "en": clause,
                "es": es_for(clause),
                "source": "listing note",
                "as_of": updated,
            }
        body[home["id"]] = {
            "condition": condition,
            "fit": {"family_en": None, "family_es": None, "rental_en": None, "rental_es": None},
        }
    return {"version": 1, "updated": updated, "homes": body}


def _esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _slot(key: str, needed: str) -> str:
    return (
        f'<!-- JOE-INPUT: {key} -->\n'
        f'<p class="joe-slot" data-joe="{_esc(key)}" hidden>'
        f'<span class="joe-ph">Placeholder: {_esc(needed)}</span></p>'
    )


def _row(label: str, value: str) -> str:
    return f'<li><span class="k">{_esc(label)}</span><span class="v">{_esc(value)}</span></li>'


def _unknown(lang: str) -> str:
    return "Aún no se sabe" if lang == "es" else "Not yet known"


def _condition_row(key: str, entry: dict | None, lang: str) -> str:
    label = SYSTEM_LABELS[lang][key]
    status = (entry or {}).get("status") or "unknown"
    if status == "verified" and (entry or {}).get(lang):
        source = (entry or {}).get("source") or ""
        as_of = (entry or {}).get("as_of") or ""
        detail = entry.get(lang) or ""
        extra = ""
        if source or as_of:
            extra = " (" + ", ".join(p for p in (source, as_of) if p) + ")"
        if lang == "es":
            text = f"Verificado: {detail}{extra}. Lo revisó nuestro equipo."
        else:
            text = f"Verified: {detail}{extra}. Checked by our team."
        icon, name = "✓", "Verified" if lang == "en" else "Verificado"
    elif status == "reported" and (entry or {}).get(lang):
        source = (entry or {}).get("source") or ""
        detail = entry.get(lang) or ""
        if lang == "es":
            text = f"El vendedor informa: {detail}." + (f" Fuente: {source}." if source else "")
            icon, name = "“", "El vendedor informa"
        else:
            text = f"Seller reports: {detail}." + (f" Source: {source}." if source else "")
            icon, name = "“", "Seller reports"
    else:
        text = _unknown(lang)
        icon = "?"
    return (
        f'<li class="cond-{_esc(status)}"><span class="cond-ic" aria-hidden="true">{icon}</span>'
        f'<span class="cond-name">{_esc(label)}</span>'
        f'<span class="cond-state">{_esc(text)}</span></li>'
    )


def _fit_facts(home: dict, lang: str) -> list[str]:
    facts = []
    beds, baths = home.get("beds"), home.get("baths")
    try:
        beds_n = float(beds) if beds not in (None, "") else 0
    except (TypeError, ValueError):
        beds_n = 0
    try:
        baths_n = float(baths) if baths not in (None, "") else 0
    except (TypeError, ValueError):
        baths_n = 0
    if beds_n:
        n = int(beds_n) if beds_n == int(beds_n) else beds_n
        if lang == "es":
            facts.append(f"{n} {'recámara' if n == 1 else 'recámaras'}")
        else:
            facts.append(f"{n} {'bedroom' if n == 1 else 'bedrooms'}")
    if baths_n:
        n = int(baths_n) if baths_n == int(baths_n) else baths_n
        if lang == "es":
            facts.append(f"{n} {'baño' if n == 1 else 'baños'}")
        else:
            facts.append(f"{n} {'bathroom' if n == 1 else 'bathrooms'}")
    sq = str(home.get("sqft") or "").replace(",", "").strip()
    if sq.endswith(".0"):
        sq = sq[:-2]
    try:
        sq_n = float(sq) if sq else 0
    except ValueError:
        sq_n = 0
    if sq_n:
        shown = f"{int(sq_n):,}" if sq_n == int(sq_n) else f"{sq_n:,}"
        facts.append(f"{shown} pies cuadrados" if lang == "es" else f"{shown} sqft")
    features = home.get("features") or {}
    if not isinstance(features, dict):
        features = {}
    labels = {
        "en": {
            "backyard": "Yard",
            "fenced_yard": "Fenced yard",
            "garage": "Garage",
            "basement": "Basement",
            "off_street_parking": "Parking",
        },
        "es": {
            "backyard": "Patio",
            "fenced_yard": "Patio con cerca",
            "garage": "Garaje",
            "basement": "Sótano",
            "off_street_parking": "Estacionamiento",
        },
    }[lang]
    for key, label in labels.items():
        if features.get(key) == "yes":
            facts.append(label)
    extra = (home.get("fit") or {}).get("family_es" if lang == "es" else "family_en")
    if isinstance(extra, str) and extra.strip():
        facts.append(extra.strip())
    return facts


def qualify_sentence(lang: str = "en") -> str:
    """Soft qualify line. English stays the published sentence."""
    if lang == "es":
        return "No necesita préstamo de banco. Si el enganche y la mensualidad se ajustan a su presupuesto, nuestro equipo lo acompaña en cada paso."
    return "No bank loan needed. If the down payment and monthly fit your budget, our team will guide you through every step."


def eval_html(home: dict, facts_doc: dict, lang: str) -> str:
    """The three blocks under the price row. Static HTML, no post-load injection."""
    lang = "es" if lang == "es" else "en"
    record = (facts_doc.get("homes") or {}).get(home.get("id") or "") or {}
    condition = record.get("condition") or {}
    down = home.get("_down_text") or ""
    monthly = home.get("_monthly_text") or ""
    price = home.get("_price_text") or ""
    term = (home.get("termText") or "").strip()

    state = str(home.get("state") or "").strip().upper()
    if lang == "es":
        cash_title, down_label = "Enganche para mudarse", "Enganche"
        paperwork = "Las condiciones finales se confirman en sus documentos."
        month_title = "Su pago mensual y las condiciones"
        month_l, price_l = "Pago mensual", "Precio"
        qualify = qualify_sentence("es")
        cond_title = "Condición: se vende como está"
        cond_copy = ("Cada casa se vende como está. Necesita algo de trabajo y el precio lo refleja. "
                     "Usted se encarga de las reparaciones. Recorra la casa antes de firmar.")
        fit_title = "Cómo podría servirle esta casa"
        family_title, rental_title = "Para una familia", "Para renovar y rentar"
        illustrate = "Es un ejemplo con los datos de este anuncio, no la historia de un comprador."
        keys_title = "De la primera visita a sus llaves, en 5 pasos"
        keys = [
            "Agende una hora y nuestro equipo le muestra la casa en persona.",
            "Le enviamos un paquete de bienvenida",
            "Usted envía el enganche que aparece en la página de la casa, o el depósito.",
            "Preparamos el papeleo, y usted lo revisa y lo firma antes de recibir las llaves.",
            "Las llaves son suyas.",
        ]
        if state == "IL":
            keys_note = "En Illinois primero tiene 3 días después de firmar para cambiar de opinión."
        else:
            keys_note = "En los demás estados, recibe las llaves al firmar."
        scam_q = "¿Es esto una estafa?"
        scam_a = scam_answer("es")
        scam_html = scam_answer_html("es")
    else:
        cash_title, down_label = "Down payment to move in", "Down payment"
        paperwork = "Final terms are confirmed in your paperwork."
        month_title = "Your monthly payment and terms"
        month_l, price_l = "Monthly payment", "Price"
        qualify = qualify_sentence("en")
        cond_title = "Condition: sold as-is"
        cond_copy = ("Every home is sold as-is. It needs some work, and the price reflects that. "
                     "You handle the repairs. Walk through the home before you sign.")
        fit_title = "How this home could fit"
        family_title, rental_title = "For a family", "To renovate and rent"
        illustrate = "An illustration from this listing's own facts, not a buyer's story."
        keys_title = "From first tour to your keys, in 5 steps"
        keys = [
            "Book a time and our team shows you the home in person.",
            "We send a welcome packet",
            "You send the down payment shown on the home's page, or the deposit.",
            "We prepare the paperwork, and you review and sign it before you get the keys.",
            "The keys are yours.",
        ]
        if state == "IL":
            keys_note = "In Illinois you first have 3 days after signing to change your mind."
        else:
            keys_note = "In other states, you get the keys right after signing."
        scam_q = "Is this a scam?"
        scam_a = scam_answer("en")
        scam_html = scam_answer_html("en")

    cash_rows = []
    if down:
        cash_rows.append(_row(down_label, down))
    cond_rows = "".join(_condition_row(key, condition.get(key), lang) for key in SYSTEMS)
    family = _fit_facts({**home, "fit": record.get("fit") or {}}, lang)
    if price:
        family.append(price if lang == "es" else f"{price} price")
    if monthly:
        family.append(f"{monthly}/mes" if lang == "es" else f"{monthly}/mo")
    family_html = ""
    if family:
        items = "".join(f"<li>{_esc(item)}</li>" for item in family)
        family_html = (
            f'<article class="fit-card"><h3>{_esc(family_title)}</h3><ul>{items}</ul>'
            f'<p class="fit-note">{_esc(illustrate)}</p></article>'
        )
    rental_bits = []
    if price:
        rental_bits.append(price if lang == "es" else f"Purchase price {price}")
    if monthly:
        rental_bits.append(f"{monthly} al mes" if lang == "es" else f"Monthly payment {monthly}")
    rental_html = ""
    if rental_bits:
        rental_html = (
            f'<article class="fit-card"><h3>{_esc(rental_title)}</h3>'
            f'<ul>{"".join(f"<li>{_esc(bit)}</li>" for bit in rental_bits)}</ul>'
            f'<p class="fit-note">{_esc(illustrate)}</p></article>'
        )
    fit_block = ""
    if family_html or rental_html:
        fit_block = (
            f'<section class="eval-block" id="fitBlock"><h2>{_esc(fit_title)}</h2>'
            f'<div class="fit-grid">{family_html}{rental_html}</div></section>'
        )
    key_items = "".join(f"<li>{_esc(step)}</li>" for step in keys)
    price_small = f'<p class="price-small">{_esc(price_l)} {_esc(price)}</p>' if price else ""
    return (
        '<div class="buyer-eval" id="buyerEval" data-baked="1">\n'
        f'<p class="qualify-line">{_esc(qualify)}</p>\n'
        f'<section class="eval-block" id="cashKeys"><h2>{_esc(cash_title)}</h2>'
        f'<ul class="eval-lines">{"".join(cash_rows)}</ul>'
        f'{price_small}'
        f'<p class="eval-total">{_esc(paperwork)}</p></section>\n'
        f'<details class="scam-note" id="scamNote"><summary>{_esc(scam_q)}</summary>'
        f'{scam_html}</details>\n'
        f'<script type="application/ld+json">{json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": scam_q, "acceptedAnswer": {"@type": "Answer", "text": scam_a}}]}, ensure_ascii=False).replace("<", "\\u003c")}</script>\n'
        f'<section class="eval-block" id="keysBlock"><h2>{_esc(keys_title)}</h2>'
        f'<ol class="key-steps">{key_items}</ol><p>{_esc(keys_note)}</p></section>\n'
        f'<section class="eval-block" id="conditionBlock"><h2>{_esc(cond_title)}</h2>'
        f'<p class="eval-copy">{_esc(cond_copy)}</p><ul class="cond-rows">{cond_rows}</ul></section>\n'
        f'{fit_block}</div>'
    )


def finance_line(homes: list[dict], lang: str) -> tuple[str, int, str]:
    """Lowest Available down payment, and how many Available homes are at $2,500 down or less."""
    downs = []
    for home in homes:
        if str(home.get("status") or "").strip().lower() == "pending":
            continue
        try:
            value = float(str(home.get("moveIn") if home.get("moveIn") is not None else home.get("down") or "").replace(",", "").replace("$", ""))
        except (TypeError, ValueError):
            continue
        if value > 0:
            downs.append(value)
    if not downs:
        return ("", 0, "")
    lowest = int(min(downs)) if min(downs) == int(min(downs)) else min(downs)
    count = sum(1 for value in downs if value <= 2500)
    lowest_txt = f"${lowest:,}" if isinstance(lowest, int) else f"${lowest:,.2f}"
    if lang == "es":
        line = (f"El enganche más bajo entre las casas disponibles es {lowest_txt}. "
                f"{count} casas disponibles piden {('$2,500' )} de enganche o menos.")
    else:
        line = (f"The lowest down payment on an available home is {lowest_txt}. "
                f"{count} available homes are $2,500 down or less.")
    return lowest_txt, count, line
