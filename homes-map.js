/* ══════════════════════════════════════════════════════════════════════════════════
   homes-map.js — the map for getownerfinancedhomes.com AND casasconfinanciamiento.com
   (hand-maintained; the Spanish site carries an identical copy — language comes from
   <html lang>). Reads lat/lng/geo from homes.js, which refresh_listings.py geocodes.

   Browse page : HomesMap.mount({rerender})  then  HomesMap.applyGeo(list) inside filtered()
                 and HomesMap.update(list) after render().
   Home page   : HomesMap.mini({el, home})
   Leaflet + markercluster load on demand (only when a map is actually opened).
   ═══════════════════════════════════════════════════════════════════════════════════ */
(function(){
  const ES = (document.documentElement.lang || "en").toLowerCase().startsWith("es");
  const T = ES ? {
    list:"Lista", map:"Mapa", near:"Cerca de", nearPh:"Ciudad o código postal", within:"Dentro de",
    mi:"mi", go:"Buscar", loc:"Usar mi ubicación", clear:"Quitar", searchArea:"Buscar en esta área",
    areaChip:"Solo el área del mapa", notFound:"No encontramos ese lugar — pruebe con una ciudad o código postal.",
    locDenied:"No pudimos obtener su ubicación.", mo:"/mes", moveIn:"Para mudarse", view:"Ver esta casa →",
    bed:"hab.", bath:"baños", away:"mi de distancia", approx:"Ubicación aproximada",
    noPins:"Ninguna de estas casas tiene ubicación en el mapa todavía.", shown:"en el mapa",
    sold:"Pendiente", fit:"Ver todas", where:"Dónde está", openG:"Abrir en Google Maps", nearby:"Otras casas cerca",
    attrib:"© OpenStreetMap contributors", you:"Usted está aquí", legendP:"Pendiente", legendA:"Disponible",
    pinNote:"Los precios en los pines son el pago mensual."
  } : {
    list:"List", map:"Map", near:"Near", nearPh:"City or zip code", within:"Within",
    mi:"mi", go:"Search", loc:"Use my location", clear:"Clear", searchArea:"Search this area",
    areaChip:"Map area only", notFound:"We couldn't find that place — try a city or zip code.",
    locDenied:"We couldn't get your location.", mo:"/mo", moveIn:"To move in", view:"View this home →",
    bed:"bd", bath:"ba", away:"mi away", approx:"Approximate location",
    noPins:"None of these homes have a map location yet.", shown:"on the map",
    sold:"Pending", fit:"Show all", where:"Where it is", openG:"Open in Google Maps", nearby:"Other homes nearby",
    attrib:"© OpenStreetMap contributors", you:"You are here", legendP:"Pending", legendA:"Available",
    pinNote:"Prices on the pins are the monthly payment."
  };

  const ALL = () => (typeof HOMES !== "undefined" ? HOMES : []);   // top-level const isn't on window
  const $ = id => document.getElementById(id);
  const money = n => "$" + Math.round(Number(n||0)).toLocaleString();
  const esc = s => String(s==null?"":s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const pinned = h => typeof h.lat === "number" && typeof h.lng === "number";
  const isPending = h => /pend/i.test(h.status || "");
  // OpenStreetMap standard tiles: free, no key, commercial use OK with attribution (tile usage policy).
  // If traffic ever gets heavy, swap this one line for a keyed provider (MapTiler/Stadia free tier).
  const tileURL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

  // great-circle distance in miles
  function miles(a, b, c, d){
    const R = 3958.8, r = Math.PI/180;
    const x = Math.sin((c-a)*r/2)**2 + Math.cos(a*r)*Math.cos(c*r)*Math.sin((d-b)*r/2)**2;
    return 2*R*Math.asin(Math.sqrt(x));
  }

  /* ---------- lazy-load Leaflet (+ clustering) ---------- */
  let libP = null;
  function loadLib(cluster){
    if (libP) return libP;
    const css = h => new Promise((res, rej) => { const l = document.createElement("link"); l.rel="stylesheet"; l.href=h; l.onload=res; l.onerror=rej; document.head.appendChild(l); });
    const js = s => new Promise((res, rej) => { const e = document.createElement("script"); e.src=s; e.onload=res; e.onerror=rej; document.head.appendChild(e); });
    const B = "https://cdnjs.cloudflare.com/ajax/libs/";
    libP = css(B+"leaflet/1.9.4/leaflet.min.css")
      .then(() => js(B+"leaflet/1.9.4/leaflet.min.js"))
      .then(() => cluster ? Promise.all([css(B+"leaflet.markercluster/1.5.3/MarkerCluster.min.css"), js(B+"leaflet.markercluster/1.5.3/leaflet.markercluster.min.js")]) : 0);
    return libP;
  }

  let styled = false;
  function addStyle(){
    if (styled) return; styled = true;
    const s = document.createElement("style");
    s.textContent = `
    .hm-bar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:0 0 14px}
    .hm-seg{display:inline-flex;border:1.5px solid var(--pine,#15315e);border-radius:12px;overflow:hidden}
    .hm-seg button{font:600 14px 'DM Sans',system-ui,sans-serif;padding:10px 18px;border:0;background:#fff;color:var(--pine,#15315e);cursor:pointer;min-height:44px}
    .hm-seg button.on{background:var(--pine,#15315e);color:#fff}
    .hm-near{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;margin:0 0 14px;padding:12px 14px;background:#fff;border:1px solid var(--line,#e2e8f2);border-radius:14px}
    .hm-near label{display:block;font:500 12px 'DM Mono',monospace;color:var(--ink-soft,#5b6577);margin-bottom:4px;text-transform:uppercase;letter-spacing:.04em}
    .hm-near input,.hm-near select{font:500 15px 'DM Sans',system-ui,sans-serif;padding:10px 12px;border:1.5px solid var(--line,#e2e8f2);border-radius:10px;background:#fff;color:var(--ink,#16213a);min-height:44px}
    .hm-near input{width:190px;max-width:100%}
    .hm-btn{font:600 14px 'DM Sans',system-ui,sans-serif;padding:10px 16px;border-radius:10px;border:1.5px solid var(--pine,#15315e);background:var(--pine,#15315e);color:#fff;cursor:pointer;min-height:44px}
    .hm-btn.ghost{background:#fff;color:var(--pine,#15315e)}
    .hm-msg{flex-basis:100%;font-size:13.5px;color:var(--honey,#e23b3b);margin:2px 0 0;min-height:0}
    .hm-wrap{position:relative;margin:0 0 22px}
    .hm-map{height:min(640px,72vh);min-height:380px;border-radius:16px;border:1px solid var(--line,#e2e8f2);overflow:hidden;background:#e8eef7}
    .hm-chip{position:absolute;z-index:500;top:12px;left:50%;transform:translateX(-50%);display:flex;gap:8px;align-items:center}
    .hm-chip button{box-shadow:0 2px 10px rgba(15,36,68,.28)}
    .hm-foot{display:flex;gap:14px;flex-wrap:wrap;align-items:center;font-size:13px;color:var(--ink-soft,#5b6577);margin-top:8px}
    .hm-foot i{display:inline-block;width:12px;height:12px;border-radius:4px;margin-right:5px;vertical-align:-1px}
    .hm-pin{font:700 13px 'DM Sans',system-ui,sans-serif;color:#fff;background:var(--pine,#15315e);border:2px solid #fff;border-radius:999px;padding:3px 9px;white-space:nowrap;box-shadow:0 2px 8px rgba(15,36,68,.45);transform:translate(-50%,-50%);display:inline-block}
    .hm-pin.pend{background:#7b8696}
    .hm-pin.cur{background:var(--honey,#e23b3b);font-size:14px;padding:5px 11px;z-index:1000}
    .hm-pin.dim{background:#fff;color:var(--pine,#15315e);border:2px solid var(--pine,#15315e);box-shadow:0 1px 4px rgba(15,36,68,.3);padding:2px 7px;font-size:12px}
    .hm-pin.you{background:#2a8a4a;padding:4px 9px}
    .hm-pop{width:230px;font-family:'DM Sans',system-ui,sans-serif}
    .hm-pop .ph{height:118px;border-radius:10px;background:linear-gradient(135deg,#15315e,#2f5c96) center/cover no-repeat;margin-bottom:8px;position:relative}
    .hm-pop .pr{font-weight:700;font-size:19px;color:var(--pine,#15315e);line-height:1.1}
    .hm-pop .pr small{font-weight:500;font-size:13px;color:var(--ink-soft,#5b6577)}
    .hm-pop .sp{font-size:13.5px;color:var(--ink,#16213a);margin:3px 0}
    .hm-pop .ad{font-size:13px;color:var(--ink-soft,#5b6577);margin-bottom:8px}
    .hm-pop a.go{display:block;text-align:center;background:var(--go,#e23b3b);color:#fff!important;text-decoration:none;font-weight:700;font-size:14px;padding:10px;border-radius:10px}
    .hm-pop .ap{font-size:12px;color:var(--ink-soft,#5b6577);margin-top:6px}
    .leaflet-popup-content{margin:12px}
    .hm-cl{background:var(--pine,#15315e);color:#fff;border:3px solid #fff;border-radius:50%;font:700 14px 'DM Sans',sans-serif;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(15,36,68,.45)}
    .hm-mini{height:340px;border-radius:16px;border:1px solid var(--line,#e2e8f2);overflow:hidden;background:#e8eef7}
    .hm-minifoot{display:flex;gap:14px;flex-wrap:wrap;align-items:center;justify-content:space-between;margin-top:10px;font-size:14px;color:var(--ink-soft,#5b6577)}
    .hm-minifoot a{font-weight:600;color:var(--pine,#15315e)}
    @media (max-width:640px){.hm-map{min-height:420px}.hm-near input{width:100%}.hm-seg{width:100%}.hm-seg button{flex:1}}
    `;
    document.head.appendChild(s);
  }

  function pinIcon(L, h, cls){
    const label = h.monthlyPayment ? money(h.monthlyPayment) : "•";
    return L.divIcon({ className:"", html:`<span class="hm-pin ${cls||""}${isPending(h)&&!cls?" pend":""}">${label}</span>`, iconSize:[0,0] });
  }
  function popupHTML(h){
    const photo = h.heroPhoto || `images/${h.id}.jpg`;
    const sv = `images/sv/${h.id}.jpg`;
    const specs = [h.beds?`${h.beds} ${T.bed}`:"", h.baths?`${h.baths} ${T.bath}`:"", h.moveIn?`${money(h.moveIn)} ${T.moveIn.toLowerCase()}`:""].filter(Boolean).join(" · ");
    const dist = h._dist != null ? `<div class="sp">${h._dist.toFixed(1)} ${T.away}</div>` : "";
    return `<div class="hm-pop">
      <div class="ph" style="background-image:url('${esc(photo)}'),url('${esc(sv)}'),linear-gradient(135deg,#15315e,#2f5c96)"></div>
      <div class="pr">${money(h.monthlyPayment)}<small> ${T.mo}</small>${isPending(h)?` <small>· ${T.sold}</small>`:""}</div>
      <div class="sp">${esc(specs)}</div>${dist}
      <div class="ad">${esc(h.address||"")}${h.address?", ":""}${esc(h.city)}, ${esc(h.state)}</div>
      <a class="go" href="${encodeURIComponent(h.id)}.html">${T.view}</a>
      ${window.HomesCart?`<div style="display:flex;gap:8px;margin-top:8px;align-items:center">${HomesCart.heart(h,true)}${HomesCart.compare(h)}</div>`:""}
      ${h.geo==="approx"?`<div class="ap">${T.approx}</div>`:""}
    </div>`;
  }

  /* ══════════════════ BROWSE PAGE ══════════════════ */
  const S = { view:"list", near:null, miles:25, area:null, map:null, group:null, youMarker:null, ring:null, rerender:null, last:[], dirty:false, ready:false };

  function applyGeo(list){
    list = list.slice();
    list.forEach(h => { h._dist = null; });
    if (S.near){
      list = list.filter(h => {
        if (!pinned(h)) return false;
        h._dist = miles(S.near.lat, S.near.lng, h.lat, h.lng);
        return h._dist <= S.miles;
      });
      const sortSel = $("fSort");
      if (!sortSel || !sortSel.value) list.sort((a,b) => a._dist - b._dist);
    }
    if (S.area){
      list = list.filter(h => pinned(h) && h.lat >= S.area.s && h.lat <= S.area.n && h.lng >= S.area.w && h.lng <= S.area.e);
    }
    return list;
  }

  // city / zip → coordinates. Our own inventory first (instant, no network); OpenStreetMap otherwise.
  function localPlace(q){
    const t = q.trim().toLowerCase();
    if (!t) return null;
    const zip = t.match(/^\d{5}$/);
    const rows = ALL().filter(pinned).filter(h => zip ? String(h.zip||"").slice(0,5) === t
      : (h.city||"").toLowerCase() === t.replace(/,.*$/, "").trim());
    if (!rows.length) return null;
    return { lat: rows.reduce((a,h)=>a+h.lat,0)/rows.length, lng: rows.reduce((a,h)=>a+h.lng,0)/rows.length, label: q.trim() };
  }
  async function findPlace(q){
    const hit = localPlace(q);
    if (hit) return hit;
    const url = "https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=us&q=" + encodeURIComponent(q);
    const r = await (await fetch(url, { headers:{ "Accept-Language": ES ? "es" : "en" } })).json();
    return r && r[0] ? { lat:+r[0].lat, lng:+r[0].lon, label:q.trim() } : null;
  }

  function setMsg(t){ const m = $("hmMsg"); if (m) m.textContent = t || ""; }
  function setNear(p){
    S.near = p; S.area = null;
    $("hmNear").value = p ? p.label : "";
    $("hmClear").hidden = !p;
    setMsg("");
    S.rerender(false);
    if (S.view === "map") fitAll(true);
    S.sync && S.sync();
  }

  async function doSearch(){
    const q = $("hmNear").value.trim();
    if (!q){ setNear(null); return; }
    setMsg("…");
    try { const p = await findPlace(q); if (p) setNear(p); else setMsg(T.notFound); }
    catch(e){ setMsg(T.notFound); }
  }
  function useMyLocation(){
    if (!navigator.geolocation){ setMsg(T.locDenied); return; }
    setMsg("…");
    navigator.geolocation.getCurrentPosition(
      pos => setNear({ lat:pos.coords.latitude, lng:pos.coords.longitude, label: ES ? "Mi ubicación" : "My location", me:true }),
      () => setMsg(T.locDenied), { enableHighAccuracy:false, timeout:10000, maximumAge:300000 });
  }

  function mount(opts){
    addStyle();
    S.rerender = opts.rerender;
    S.sync = opts.sync;
    const cards = $("cards");
    if (!cards || !ALL().some(pinned)) return;       // no coordinates → no map UI at all
    const host = document.createElement("div");
    host.innerHTML = `
      <div class="hm-bar">
        <div class="hm-seg" role="tablist"><button type="button" id="hmList" class="on">${T.list}</button><button type="button" id="hmMap">${T.map}</button></div>
      </div>
      <div class="hm-near">
        <div><label for="hmNear">${T.near}</label><input id="hmNear" type="text" placeholder="${T.nearPh}" autocomplete="off"></div>
        <div><label for="hmMiles">${T.within}</label>
          <select id="hmMiles"><option value="5">5 ${T.mi}</option><option value="10">10 ${T.mi}</option><option value="15">15 ${T.mi}</option><option value="25" selected>25 ${T.mi}</option><option value="50">50 ${T.mi}</option><option value="100">100 ${T.mi}</option></select></div>
        <button type="button" class="hm-btn" id="hmGo">${T.go}</button>
        <button type="button" class="hm-btn ghost" id="hmLoc">📍 ${T.loc}</button>
        <button type="button" class="hm-btn ghost" id="hmClear" hidden>✕ ${T.clear}</button>
        <div class="hm-msg" id="hmMsg" role="status"></div>
      </div>
      <div class="hm-wrap" id="hmWrap" hidden>
        <div class="hm-map" id="hmMapEl"></div>
        <div class="hm-chip"><button type="button" class="hm-btn" id="hmArea" hidden>${T.searchArea}</button><button type="button" class="hm-btn ghost" id="hmAreaOff" hidden>✕ ${T.areaChip}</button></div>
        <div class="hm-foot"><span><i style="background:#15315e"></i>${T.legendA}</span><span><i style="background:#7b8696"></i>${T.legendP}</span><span>${T.pinNote}</span><span id="hmCount"></span></div>
      </div>`;
    cards.parentNode.insertBefore(host, cards);

    $("hmList").onclick = () => setView("list");
    $("hmMap").onclick  = () => setView("map");
    $("hmGo").onclick = doSearch;
    $("hmNear").addEventListener("keydown", e => { if (e.key === "Enter"){ e.preventDefault(); doSearch(); } });
    $("hmLoc").onclick = useMyLocation;
    $("hmClear").onclick = () => setNear(null);
    $("hmMiles").onchange = () => { S.miles = Number($("hmMiles").value); S.area = null; S.rerender(false); if (S.view==="map") fitAll(true); S.sync && S.sync(); };
    $("hmArea").onclick = () => {
      const b = S.map.getBounds();
      S.area = { s:b.getSouth(), n:b.getNorth(), w:b.getWest(), e:b.getEast() };
      S.dirty = false; $("hmArea").hidden = true; $("hmAreaOff").hidden = false;
      S.rerender(false);
    };
    $("hmAreaOff").onclick = () => { S.area = null; $("hmAreaOff").hidden = true; S.rerender(false); fitAll(true); };
    S.ready = true;
  }

  function setView(v){
    S.view = v;
    $("hmList").classList.toggle("on", v==="list");
    $("hmMap").classList.toggle("on", v==="map");
    $("hmWrap").hidden = v !== "map";
    // the list stays available under the map (it is the same filtered set, one page at a time)
    if (v === "map") initMap().then(() => { S.map.invalidateSize(); drawPins(S.last); fitAll(true); });
    S.sync && S.sync();
  }

  async function initMap(){
    if (S.map) return;
    await loadLib(true);
    const L = window.L;
    S.map = L.map("hmMapEl", { scrollWheelZoom:true, tap:true }).setView([38.6, -89.5], 7);
    L.tileLayer(tileURL, { maxZoom:19, attribution:T.attrib }).addTo(S.map);
    S.group = L.markerClusterGroup({
      showCoverageOnHover:false, maxClusterRadius:46,
      iconCreateFunction: c => L.divIcon({ html:`<div class="hm-cl" style="width:38px;height:38px">${c.getChildCount()}</div>`, className:"", iconSize:[38,38] })
    }).addTo(S.map);
    S.map.on("moveend", () => { if (S.view==="map" && !S._fitting && S.ready){ S.dirty = true; $("hmArea").hidden = false; } });
  }

  function drawPins(list){
    if (!S.map) return;
    const L = window.L;
    S.group.clearLayers();
    const pins = list.filter(pinned);
    S.group.addLayers(pins.map(h => {
      const m = L.marker([h.lat, h.lng], { icon: pinIcon(L, h), riseOnHover:true });
      m.bindPopup(() => popupHTML(h), { maxWidth:260, autoPanPadding:[30,30] });
      m.on("popupopen", () => window.HomesCart && HomesCart.sync());
      return m;
    }));
    if (S.ring){ S.ring.remove(); S.ring = null; }
    if (S.youMarker){ S.youMarker.remove(); S.youMarker = null; }
    if (S.near){
      S.ring = L.circle([S.near.lat, S.near.lng], { radius:S.miles*1609.34, color:"#e23b3b", weight:2, fillColor:"#e23b3b", fillOpacity:.06, interactive:false }).addTo(S.map);
      S.youMarker = L.marker([S.near.lat, S.near.lng], { icon:L.divIcon({ className:"", html:`<span class="hm-pin you">📍 ${esc(S.near.label)}</span>`, iconSize:[0,0] }), interactive:false, keyboard:false }).addTo(S.map);
    }
    const n = pins.length;
    $("hmCount").textContent = n ? `· ${n} ${T.shown}` : "";
    if (!n && list.length) setMsg(T.noPins);
  }

  function fitAll(force){
    if (!S.map) return;
    const L = window.L, pts = S.last.filter(pinned).map(h => [h.lat, h.lng]);
    S._fitting = true;
    if (S.near && S.ring) S.map.fitBounds(S.ring.getBounds(), { padding:[20,20], animate:false });
    else if (pts.length) S.map.fitBounds(L.latLngBounds(pts), { padding:[40,40], maxZoom:13, animate:false });
    // moveend fires synchronously for a non-animated fit; only later pans/zooms are the visitor's
    setTimeout(() => { S._fitting = false; S.dirty = false; const a = $("hmArea"); if (a) a.hidden = true; }, 250);
  }

  // called after every render() with the full filtered set
  function update(list){
    S.last = list;
    if (S.view === "map" && S.map){
      drawPins(list);
      if (!S.area && !S._keepView) fitAll();
    }
  }

  // shareable-link state: ?view=map&near=Decatur&mi=25
  function toURL(p){
    if (S.view === "map") p.set("view", "map");
    if (S.near){ p.set("near", S.near.me ? `${S.near.lat.toFixed(4)},${S.near.lng.toFixed(4)}` : S.near.label); p.set("mi", String(S.miles)); }
  }
  async function fromURL(p){
    if (!S.ready) return;
    const mi = Number(p.get("mi")); if (mi){ S.miles = mi; $("hmMiles").value = String(mi); if ($("hmMiles").value !== String(mi)) { $("hmMiles").value = "25"; S.miles = 25; } }
    const near = p.get("near");
    if (near){
      const m = near.match(/^(-?\d+\.\d+),(-?\d+\.\d+)$/);
      try {
        const pl = m ? { lat:+m[1], lng:+m[2], label: ES ? "Mi ubicación" : "My location", me:true } : await findPlace(near);
        if (pl){ S.near = pl; $("hmNear").value = pl.label; $("hmClear").hidden = false; S.rerender(false); }
      } catch(e){}
    }
    if (p.get("view") === "map") setView("map");
  }

  /* ══════════════════ SINGLE-HOME MINI MAP ══════════════════ */
  async function mini(opts){
    const home = opts.home, el = opts.el;
    if (!home || !pinned(home) || !el) return;
    addStyle();
    const sec = opts.section; if (sec) sec.hidden = false;
    const start = async () => {
      await loadLib(false);
      const L = window.L;
      const map = L.map(el, { scrollWheelZoom:false, tap:true }).setView([home.lat, home.lng], home.geo==="approx" ? 12 : 15);
      L.tileLayer(tileURL, { maxZoom:19, attribution:T.attrib }).addTo(map);
      L.marker([home.lat, home.lng], { icon:pinIcon(L, home, "cur"), zIndexOffset:1000 }).addTo(map);
      // the 10 closest other homes within 10 miles — enough to compare, not a pile-up in dense cities
      const all = ALL().filter(h => h.id !== home.id && pinned(h) && !isPending(h))
        .map(h => (h._dist = miles(home.lat, home.lng, h.lat, h.lng), h)).filter(h => h._dist <= 10)
        .sort((x, y) => x._dist - y._dist);
      const near = all.slice(0, 10);
      near.forEach(h => L.marker([h.lat, h.lng], { icon:pinIcon(L, h, "dim") }).bindPopup(() => popupHTML(h), { maxWidth:260 }).on("popupopen", () => window.HomesCart && HomesCart.sync()).addTo(map));
      if (near.length && home.geo !== "approx"){
        map.fitBounds(L.latLngBounds([[home.lat, home.lng]].concat(near.map(h => [h.lat, h.lng]))), { padding:[36,36], maxZoom:15 });
      }
      setTimeout(() => map.invalidateSize(), 400);
      const note = opts.note; if (note) note.textContent = all.length ? (ES ? `${all.length} casas más a menos de 10 mi · mostrando las ${near.length} más cercanas` : `${all.length} other homes within 10 mi · showing the ${near.length} closest`) : "";
    };
    if ("IntersectionObserver" in window){
      const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)){ io.disconnect(); start(); } }, { rootMargin:"300px" });
      io.observe(el);
    } else start();
  }

  window.HomesMap = { mount, applyGeo, update, toURL, fromURL, mini, T, pinned, miles, nearState: () => (S.near && !S.near.me ? { label:S.near.label, miles:S.miles } : null), active: () => !!(S.near || S.area) };
})();
