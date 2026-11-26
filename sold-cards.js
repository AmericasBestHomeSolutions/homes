/* ══════════════════════════════════════════════════════════════════════════════════
   sold-cards.js — "Recently sold" photo cards.
   Shared by getownerfinancedhomes.com and casasconfinanciamiento.com.
   Language comes from <html lang>. Hand-maintained — NOT generated.

   Reads SOLD_CARDS from homes.js. Each record is {street, city, state, soldOn? or sold_on?, photo?}.
   street is the street name only. photo is images/sold/<letters>.jpg.
   Cards are not links. A photo path that is not letter-only is dropped, so a
   filename that still contains the home id cannot be shown.
   ═══════════════════════════════════════════════════════════════════════════════════ */
(function (root, factory) {
  const host = (root && typeof root === "object") ? root : globalThis;
  host.SoldCards = factory(host);
})(typeof window !== "undefined" ? window : globalThis, function (host) {
  function streetName(address) {
    let text = String(address || "").split(",")[0].trim();
    text = text.replace(/^#?\d+[A-Za-z]?(?:\s*-\s*\d+[A-Za-z]?)?\s+/, "").trim();
    const dir = text.match(/^(?:N|S|E|W|NE|NW|SE|SW|North|South|East|West)\.?\s+(.+)$/i);
    if (dir) text = dir[1].trim();
    return text.replace(/\.$/, "").split(/\s+/).filter(Boolean).map(word =>
      word.charAt(0) === word.charAt(0).toLowerCase() && word.charAt(0) !== word.charAt(0).toUpperCase()
        ? word.charAt(0).toUpperCase() + word.slice(1)
        : word
    ).join(" ").trim();
  }

  function safePhoto(path) {
    return typeof path === "string" && /^images\/sold\/[a-z]{8,32}\.jpg$/.test(path) ? path : "";
  }

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, ch => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[ch]));
  }

  function strings(lang) {
    const es = String(lang || "en").toLowerCase().startsWith("es");
    return es ? {
      title: "Vendidas recientemente",
      sub: "Estas casas ya encontraron a su comprador. La próxima podría ser suya.",
      badge: "Vendida",
      alt: (street, city, state) => `Casa vendida en ${street}, ${city}, ${state}`,
      when: month => `Vendida en ${month}`,
      locale: "es-US"
    } : {
      title: "Recently sold",
      sub: "These homes found their buyer. The next one could be yours.",
      badge: "Sold",
      alt: (street, city, state) => `Sold home on ${street} in ${city}, ${state}`,
      when: month => `Sold ${month}`,
      locale: "en-US"
    };
  }

  function saleDate(record) {
    if (!record) return "";
    const snake = record.sold_on == null ? "" : String(record.sold_on).trim();
    if (snake) return snake;
    return record.soldOn == null ? "" : String(record.soldOn).trim();
  }

  function monthLabel(iso, locale) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(iso || "")) return "";
    const date = new Date(iso + "T12:00:00");
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleDateString(locale, { month: "long", year: "numeric" });
  }

  function renderCard(record, lang) {
    const T = typeof lang === "object" ? lang : strings(lang);
    const city = String(record && record.city || "").trim();
    const state = String(record && record.state || "").trim();
    if (!city || !state) return "";
    const when = monthLabel(saleDate(record), T.locale);
    const date = when ? `<p class="sold-when">${esc(T.when(when))}</p>` : "";
    return `<article class="sold-card"><span class="sold-badge">${esc(T.badge)}</span><p class="sold-label">${esc(city)}, ${esc(state)}</p>${date}</article>`;
  }

  function renderSection(cards, lang) {
    const T = strings(lang);
    return (cards || []).map(card => renderCard(card, T)).filter(Boolean).join("");
  }

  function addStyle(doc) {
    if (doc.getElementById("soldCardStyle")) return;
    const style = doc.createElement("style");
    style.id = "soldCardStyle";
    style.textContent = `
    #soldSec .sold-strip{display:flex;gap:8px;margin-top:12px;overflow-x:auto;scroll-snap-type:x mandatory;padding:2px 2px 12px;-webkit-overflow-scrolling:touch}
    #soldSec .sold-card{flex:0 0 auto;scroll-snap-align:start;background:#fff;border:1px solid var(--line,#e2e8f2);border-radius:999px;padding:10px 14px;min-height:44px}
    #soldSec .sold-label{margin:0;font-weight:800;font-size:15px;color:var(--pine,#15315e)}
    #soldSec .sold-when{margin:2px 0 0;font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:var(--ink-soft,#5b6577)}`;
    doc.head.appendChild(style);
  }

  function mount(doc) {
    doc = doc || document;
    const section = doc.getElementById("soldSec");
    const strip = doc.getElementById("soldStrip");
    if (!section || !strip) return "";
    addStyle(doc);
    const lang = (doc.documentElement && doc.documentElement.lang) || "en";
    const T = strings(lang);
    const heading = section.querySelector("h2");
    const sub = section.querySelector(".spot-sub");
    if (heading) heading.textContent = T.title;
    if (sub) sub.textContent = T.sub;
    // homes.js declares `const SOLD_CARDS`, which other classic scripts can
    // read by name but which is not a property of window.
    const cards = typeof SOLD_CARDS === "undefined" ? [] : SOLD_CARDS;
    const html = renderSection(cards, lang);
    strip.innerHTML = html;
    section.hidden = !html;
    return html;
  }

  return { mount, renderSection, renderCard, streetName, safePhoto, strings };
});
