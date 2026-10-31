/* ══════════════════════════════════════════════════════════════════════════
   NEWEST FIRST, NEAR THE VISITOR FIRST — free and keyless
   ══════════════════════════════════════════════════════════════════════════
   Every home is featured (Joe, 2026-10-31), so the default order is:
     1. homes in or right around the visitor's city (CITY_MILES), newest listed first, then closest
     2. homes within a reasonable drive (NEAR_MILES), same order
     3. every other home, newest listed first
   Homes with no listed date keep their old order (photo first, then address).

   Where "the visitor" is, in this order:
     a) a city the visitor picked in the filters before (kept in THEIR browser
        only, localStorage), or "Near me" on the map;
     b) otherwise one free, keyless approximate-location lookup by IP
        (GeoJS, city level), only for US time zones, 2.5 s timeout, once per
        browser session (sessionStorage). Nothing is sent to us or stored on
        our side. If it fails or is blocked, the list is simply newest first.
   ══════════════════════════════════════════════════════════════════════════ */
(function(){
  const KEY = "gofh_near_v1";
  const CITY_MILES = 20;   // in or right around their city
  const NEAR_MILES = 60;   // a reasonable drive
  const LOOKUP = "https://get.geojs.io/v1/ip/geo.json";
  const listeners = [];
  let near = null;

  const ok = n => n && Number.isFinite(+n.lat) && Number.isFinite(+n.lng);
  function load(name){ try { const v = JSON.parse(window[name].getItem(KEY) || "null"); return ok(v) ? v : null; } catch(e){ return null; } }
  near = load("localStorage") || load("sessionStorage");

  function set(n, remember){
    if (!ok(n)) return;
    near = { lat: +n.lat, lng: +n.lng, label: String(n.label || "").slice(0, 60), src: n.src || "" };
    try { window[remember ? "localStorage" : "sessionStorage"].setItem(KEY, JSON.stringify(near)); } catch(e){}
    listeners.forEach(f => { try { f(near); } catch(e){} });
  }

  function usTimeZone(){
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
      return /^(America\/|US\/|Pacific\/Honolulu)/.test(tz);
    } catch(e){ return true; }
  }

  function lookup(){
    if (near || !window.fetch || !usTimeZone()) return;
    let done = false;
    const ctl = window.AbortController ? new AbortController() : null;
    const timer = setTimeout(() => { done = true; if (ctl) ctl.abort(); }, 2500);
    fetch(LOOKUP, { signal: ctl ? ctl.signal : undefined, credentials: "omit", referrerPolicy: "no-referrer", cache: "no-store" })
      .then(r => r.ok ? r.json() : null)
      .then(j => {
        clearTimeout(timer);
        if (done || !j || near || String(j.country_code || "").toUpperCase() !== "US") return;
        set({ lat: j.latitude, lng: j.longitude, label: j.city || j.region || "", src: "ip" }, false);
      })
      .catch(() => clearTimeout(timer));
  }

  function miles(a, b, c, d){
    const R = 3958.8, rad = x => x * Math.PI / 180;
    const dLat = rad(c - a), dLng = rad(d - b);
    const s = Math.sin(dLat/2) ** 2 + Math.cos(rad(a)) * Math.cos(rad(c)) * Math.sin(dLng/2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(s));
  }

  // listed-dates.js declares `const LISTED_ON`, which is a global name but not a window property.
  function listedOn(){
    try { if (typeof LISTED_ON !== "undefined" && LISTED_ON) return LISTED_ON; } catch(e){}
    return window.LISTED_ON || {};
  }

  function listedTime(h){
    const t = Date.parse((listedOn()[h.id]) || "");
    return Number.isFinite(t) ? t : 0;
  }

  // Comparator for the default ("Featured") order. tie(a, b) breaks equal cases.
  function compare(tie){
    const n = near;
    const dist = h => (n && Number.isFinite(+h.lat) && Number.isFinite(+h.lng) && (+h.lat || +h.lng))
      ? miles(n.lat, n.lng, +h.lat, +h.lng) : Infinity;
    const cache = new Map();
    const d = h => { if (!cache.has(h)) cache.set(h, dist(h)); return cache.get(h); };
    const tier = h => d(h) <= CITY_MILES ? 2 : d(h) <= NEAR_MILES ? 1 : 0;  // their city, nearby, everything else
    return (a, b) => {
      const ra = tier(a), rb = tier(b);
      if (ra !== rb) return rb - ra;
      const ta = listedTime(a), tb = listedTime(b);
      if (ta !== tb) return tb - ta;
      if (ra && d(a) !== d(b)) return d(a) - d(b);
      return tie ? tie(a, b) : 0;
    };
  }

  // The visitor picked a city: remember the middle of that city's homes (their browser only).
  function rememberCity(homes, city, state){
    const pts = (homes || []).filter(h => h.city === city && (!state || h.state === state)
      && Number.isFinite(+h.lat) && Number.isFinite(+h.lng) && (+h.lat || +h.lng));
    if (!pts.length) return;
    const lat = pts.reduce((s, h) => s + +h.lat, 0) / pts.length;
    const lng = pts.reduce((s, h) => s + +h.lng, 0) / pts.length;
    set({ lat, lng, label: city, src: "city" }, true);
  }

  window.VisitorNear = {
    get: () => near,
    set,
    rememberCity,
    compare,
    onChange: f => listeners.push(f),
    listedOn,
    NEAR_MILES
  };
  if (document.readyState === "complete") lookup();
  else window.addEventListener("load", lookup);
})();
