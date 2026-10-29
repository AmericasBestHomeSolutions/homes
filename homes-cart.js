/* ══════════════════════════════════════════════════════════════════════════════════
   homes-cart.js — "My Homes": saved homes (♥), side-by-side compare, and one-tap tour requests.
   Shared by getownerfinancedhomes.com and casasconfinanciamiento.com (identical copy;
   language comes from <html lang>). Hand-maintained — NOT generated.

   State lives in the visitor's own browser (localStorage), no login:
     savedHomes    ♥ list, up to 30       compareHomes  up to 4 (side-by-side)
   Pages call:  HomesCart.heart(h) / HomesCart.compare(h) to render buttons (data-save / data-cmp),
                HomesCart.sync() after re-rendering cards.
   Saved homes ride along on every lead form (hidden saved_homes field) so the CRM sees interest.
   ═══════════════════════════════════════════════════════════════════════════════════ */
(function(){
  const ES = (document.documentElement.lang || "en").toLowerCase().startsWith("es");
  const T = ES ? {
    save:"Guardar", saved:"Guardada", mine:"Mis casas", cmp:"Comparar", cmpOn:"En comparación", cmpN:"Comparar",
    tabSaved:"Guardadas", tabCmp:"Comparar", empty:"Toque el ♥ en cualquier casa para guardarla aquí.",
    cmpHint:"Elija al menos 2 casas con «Comparar» para verlas lado a lado.", cmpFull:"Puede comparar hasta 4 casas — quite una primero.",
    saveFull:"Puede guardar hasta 30 casas — quite una primero.", remove:"Quitar", view:"Ver casa", tour:"Visita",
    reqTours:"Pedir visitas", yourTours:"Sus visitas", book:"Agende una visita", name:"Nombre", phone:"Teléfono", email:"Correo", pref:"Mejor día y hora",
    anyDay:"Cualquier día", anyTime:"Cualquier hora", times:["Mañana (9–12)","Tarde (12–4)","Noche (4–7)"],
    send:"Pedir estas visitas", sending:"Enviando…", back:"← Volver", close:"Seguir viendo",
    thanksH:"¡Listo — gracias!", thanksP:"Nos comunicaremos pronto para fijar una hora para estas casas.",
    fail:"Algo salió mal — por favor llámenos o escríbanos.", maxTours:"Puede visitar hasta 5 casas a la vez.",
    optional:"Opcional — puede enviar sin marcar la casilla.", mo:"/mes", pay:"Pago mensual", moveIn:"Para mudarse", price:"Precio",
    beds:"Habitaciones", baths:"Baños", sqft:"Pies²", where:"Ubicación", status:"Estado", feats:"Detalles del anuncio",
    avail:"Disponible", pend:"Pendiente", ask:"Consúltenos", best:"Más bajo", featNote:"Detalles tomados del anuncio que recibimos; no hemos inspeccionado las casas. Recorra la casa y verifique todo usted mismo.",
    tourN:n=>`${n} para visita`, open:"Abrir mis casas",
    consent:`Acepto recibir mensajes de texto de Americas Best Home Solutions LLC sobre casas disponibles, citas para ver casas, ofertas y seguimiento. La frecuencia de mensajes varía. Pueden aplicar tarifas de mensajes y datos. Responda STOP para cancelar la suscripción o HELP para obtener ayuda. Consulte nuestra <a href="/politica-de-privacidad" style="color:var(--pine);font-weight:600">Política de Privacidad</a> y nuestros <a href="/terminos-de-mensajes" style="color:var(--pine);font-weight:600">Términos de Mensajes</a>.`,
    labels:{backyard:"Patio trasero",fenced_yard:"Patio cercado",basement:"Sótano",garage:"Garaje",off_street_parking:"Estacionamiento propio",central_air:"Aire central / HVAC",storage_shed:"Cobertizo",attic:"Ático"},
    locale:"es-US"
  } : {
    save:"Save", saved:"Saved", mine:"My homes", cmp:"Compare", cmpOn:"Comparing", cmpN:"Compare",
    tabSaved:"Saved", tabCmp:"Compare", empty:"Tap the ♥ on any home to keep it here.",
    cmpHint:"Pick at least 2 homes with “Compare” to see them side by side.", cmpFull:"You can compare up to 4 homes — remove one first.",
    saveFull:"You can save up to 30 homes — remove one first.", remove:"Remove", view:"View home", tour:"Tour",
    reqTours:"Request tours", yourTours:"Your tours", book:"Book a Tour", name:"Name", phone:"Phone", email:"Email", pref:"Best day & time",
    anyDay:"Any day", anyTime:"Any time", times:["Morning (9–12)","Afternoon (12–4)","Evening (4–7)"],
    send:"Request these tours", sending:"Sending…", back:"← Back", close:"Keep browsing",
    thanksH:"Got it — thank you!", thanksP:"We'll text or call you shortly to lock in a time for these homes.",
    fail:"Something went wrong — please call or text us instead.", maxTours:"You can tour up to 5 homes at a time.",
    optional:"Optional — you can submit without checking the box.", mo:"/mo", pay:"Monthly payment", moveIn:"To move in", price:"Price",
    beds:"Bedrooms", baths:"Bathrooms", sqft:"Sq ft", where:"Location", status:"Status", feats:"From the listing",
    avail:"Available", pend:"Pending", ask:"Ask us", best:"Lowest", featNote:"Details come from the listing we were given — we haven't inspected these homes. Walk through the home and check everything yourself.",
    tourN:n=>`${n} to tour`, open:"Open my homes",
    consent:`I agree to receive text messages from Americas Best Home Solutions LLC about property listings, showings, offers, and follow-up. Message frequency varies. Message and data rates may apply. Reply STOP to unsubscribe or HELP for help. See our <a href="/privacy-policy" style="color:var(--pine);font-weight:600">Privacy Policy</a> and <a href="/messaging-terms" style="color:var(--pine);font-weight:600">Messaging Terms</a>.`,
    labels:{backyard:"Backyard",fenced_yard:"Fenced yard",basement:"Basement",garage:"Garage",off_street_parking:"Off-street parking",central_air:"Central air / HVAC",storage_shed:"Storage shed",attic:"Attic"},
    locale:"en-US"
  };
  const FEAT_ORDER = ["backyard","fenced_yard","basement","garage","off_street_parking","central_air","storage_shed","attic"];
  const KS = "savedHomes", KC = "compareHomes", MAXS = 30, MAXC = 4, MAXT = 5;

  const offMarket = h => /^(pending|sold)$/i.test(String((h && h.status) || "").trim());
  const ALL = () => (typeof HOMES !== "undefined" ? HOMES : []).filter(h => !offMarket(h));
  const byId = id => ALL().find(h => h.id === id);
  const $ = id => document.getElementById(id);
  const esc = s => String(s==null?"":s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const money = n => "$" + Math.round(Number(n||0)).toLocaleString();
  const load = k => { try { return JSON.parse(localStorage.getItem(k)||"[]").filter(id => typeof id === "string"); } catch(e){ return []; } };
  const store = (k, a) => { try { localStorage.setItem(k, JSON.stringify(a)); } catch(e){} };
  const live = a => a.filter(byId);                 // drop homes that have since sold
  let saved = live(load(KS)), cmp = live(load(KC)), tourSel = null, tab = "saved", view = "list";
  const label = h => [h.address, h.city, h.state].filter(Boolean).join(", ");
  const isPend = h => /pend/i.test(String((h && h.status) || ""));
  const photo = h => h.heroPhoto || `images/${h.id}.jpg`;
  const thumb = h => `<img class="hc-th" src="${esc(photo(h))}" alt="" loading="lazy" onerror="if(!this.dataset.t){this.dataset.t=1;this.src='images/sv/${esc(h.id)}.jpg'}else{this.style.visibility='hidden'}">`;

  /* ---------- styles ---------- */
  function addStyle(){
    if ($("hcStyle")) return;
    const s = document.createElement("style"); s.id = "hcStyle";
    s.textContent = `
    .hc-heart{width:42px;height:42px;border-radius:50%;border:0;background:rgba(255,255,255,.95);color:#8a94a6;font-size:22px;line-height:1;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(15,36,68,.3);transition:transform .15s}
    .hc-heart:hover{transform:scale(1.08)} .hc-heart.on{color:var(--honey,#e23b3b)}
    .card-face .hc-heart{position:absolute;bottom:12px;right:12px;z-index:6}
    .hc-cmpbtn{font:600 13px 'DM Sans',system-ui,sans-serif;display:inline-flex;align-items:center;gap:6px;padding:8px 12px;border-radius:10px;border:1.5px solid var(--line,#e2e8f2);background:#fff;color:var(--pine,#15315e);cursor:pointer;min-height:40px}
    .hc-cmpbtn.on{background:var(--pine,#15315e);border-color:var(--pine,#15315e);color:#fff}
    .card-body .hc-cmpbtn{margin-top:10px}
    .hc-hero{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:12px 0 0}
    .hc-hero .hc-heart{box-shadow:none;border:1.5px solid var(--line,#e2e8f2);background:#fff}
    .hc-tray{position:fixed;right:14px;bottom:14px;z-index:55;display:none;gap:8px;flex-wrap:wrap;justify-content:flex-end;max-width:calc(100vw - 28px)}
    .hc-tray.show{display:flex} body.tl-pad .hc-tray{bottom:84px}
    .hc-tray button{font:700 14px 'DM Sans',system-ui,sans-serif;border:0;border-radius:999px;padding:12px 18px;min-height:46px;cursor:pointer;box-shadow:0 4px 16px rgba(15,36,68,.35);background:var(--pine,#15315e);color:#fff}
    .hc-tray button.alt{background:#fff;color:var(--pine,#15315e);border:1.5px solid var(--pine,#15315e)}
    .hc-tray b{color:var(--honey,#e23b3b);margin-right:2px} .hc-tray .alt b{color:var(--pine,#15315e)}
    .hc-tray button.bump{animation:hcbump .35s}
    @keyframes hcbump{40%{transform:scale(1.12)}}
    .hc-modal{position:fixed;inset:0;z-index:70;background:rgba(10,20,40,.55);display:none;align-items:flex-end;justify-content:center}
    .hc-modal.show{display:flex}
    .hc-box{background:var(--card,#fff);width:100%;max-width:980px;max-height:94vh;overflow:auto;border-radius:18px 18px 0 0;padding:18px 18px 26px;font-family:'DM Sans',system-ui,sans-serif;color:var(--ink,#16213a)}
    @media (min-width:900px){.hc-modal{align-items:center}.hc-box{border-radius:18px}}
    .hc-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px}
    .hc-head h3{font:800 22px 'Bricolage Grotesque','DM Sans',sans-serif;color:var(--pine,#15315e);margin:0}
    .hc-x{background:none;border:0;font-size:26px;line-height:1;cursor:pointer;color:var(--ink-soft,#5b6577);padding:6px 10px}
    .hc-tabs{display:inline-flex;border:1.5px solid var(--pine,#15315e);border-radius:12px;overflow:hidden;margin-bottom:14px}
    .hc-tabs button{font:600 14px 'DM Sans',sans-serif;padding:10px 16px;border:0;background:#fff;color:var(--pine,#15315e);cursor:pointer;min-height:42px}
    .hc-tabs button.on{background:var(--pine,#15315e);color:#fff}
    .hc-item{display:grid;grid-template-columns:84px 1fr;gap:12px;align-items:center;border:1px solid var(--line,#e2e8f2);border-radius:14px;padding:10px;margin:8px 0}
    .hc-th{width:84px;height:70px;border-radius:10px;object-fit:cover;background:linear-gradient(135deg,#15315e,#2f5c96)}
    .hc-item .pr{font-weight:800;font-size:18px;color:var(--pine,#15315e)} .hc-item .pr small{font-weight:500;font-size:13px;color:var(--ink-soft,#5b6577)}
    .hc-item .ad{font-size:14px;color:var(--ink-soft,#5b6577)} .hc-item .sp{font-size:13.5px}
    .hc-acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px;align-items:center}
    .hc-acts a,.hc-acts button{font:600 13px 'DM Sans',sans-serif;background:none;border:0;color:var(--pine,#15315e);cursor:pointer;padding:6px 4px;text-decoration:underline}
    .hc-acts a.hc-book{text-decoration:none;background:var(--go,#e23b3b);color:#fff;border-radius:999px;padding:8px 12px;font-weight:800}
    .hc-acts button.rm{color:var(--honey,#e23b3b)}
    .hc-acts label{font-size:13px;font-weight:600;display:inline-flex;gap:6px;align-items:center;cursor:pointer}
    .hc-cta{width:100%;font:800 16px 'DM Sans',sans-serif;border:0;border-radius:999px;padding:15px;background:var(--go,#e23b3b);color:#fff;cursor:pointer;margin-top:12px}
    .hc-cta[disabled]{opacity:.5} .hc-link{background:none;border:0;color:var(--ink-soft,#5b6577);font-size:14px;cursor:pointer;margin:10px auto 0;display:block}
    .hc-empty{padding:26px 8px;text-align:center;color:var(--ink-soft,#5b6577)}
    .hc-form{display:flex;flex-direction:column;gap:10px;margin-top:8px}
    .hc-form label.f{font:500 11px 'DM Mono',monospace;letter-spacing:1px;text-transform:uppercase;color:var(--ink-soft,#5b6577);margin-bottom:-4px}
    .hc-form input[type=text],.hc-form input[type=tel],.hc-form input[type=email],.hc-form select{font:inherit;font-size:16px;border:1.5px solid var(--line,#e2e8f2);border-radius:12px;padding:12px;width:100%;background:var(--paper,#f4f7fc)}
    .hc-two{display:grid;grid-template-columns:1fr 1fr;gap:8px}
    .hc-tw{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--line,#e2e8f2);border-radius:14px}
    .hc-tbl{border-collapse:separate;border-spacing:0;width:100%;min-width:520px;font-size:14.5px}
    .hc-tbl th,.hc-tbl td{padding:10px 12px;border-bottom:1px solid var(--line,#e2e8f2);text-align:left;vertical-align:top;background:#fff}
    .hc-tbl th.row{position:sticky;left:0;z-index:2;font:500 12px 'DM Mono',monospace;text-transform:uppercase;letter-spacing:.04em;color:var(--ink-soft,#5b6577);width:112px;min-width:112px;background:var(--paper,#f4f7fc)}
    .hc-tbl td.best{background:#eaf6ee;font-weight:800;color:#1c6b3a}
    .hc-tbl td.best:after{content:" ✓";font-weight:700}
    .hc-tbl .ph{display:block;width:100%;height:92px;object-fit:cover;border-radius:10px;background:linear-gradient(135deg,#15315e,#2f5c96);margin-bottom:6px}
    .hc-tbl .nm{font-weight:700;font-size:14px;line-height:1.25} .hc-tbl .y{color:#1c6b3a;font-weight:700} .hc-tbl .n{color:#9aa3b2}
    .hc-note{font-size:12.5px;color:var(--ink-soft,#5b6577);margin:10px 2px 0}
    `;
    document.head.appendChild(s);
  }

  /* ---------- render helpers used by the pages ---------- */
  const heart = (h, withText) => `<button type="button" class="hc-heart" data-save="${esc(h.id)}" aria-pressed="false" aria-label="${T.save}" title="${T.save}"><span class="hc-ic">♡</span>${withText?`<span class="hc-tx" style="font:700 14px 'DM Sans',sans-serif;margin-left:6px">${T.save}</span>`:""}</button>`;
  const compare = h => `<button type="button" class="hc-cmpbtn" data-cmp="${esc(h.id)}" aria-pressed="false"><span class="hc-ic">⇄</span> <span class="hc-tx">${T.cmp}</span></button>`;

  /* ---------- state changes ---------- */
  function toggleSave(id){
    const had = saved.includes(id);
    if (had) saved = saved.filter(x => x !== id);
    else { if (saved.length >= MAXS){ alert(T.saveFull); return; } saved.push(id); }
    store(KS, saved); tourSel = null; sync(true);
    remote(had ? { remove: [id] } : { add: [id] });
  }

  /* ---------- hearts sync: a buyer who opened their personal link keeps their hearts on every device ----------
     The link adds #buyer=<key> to this site; we keep the key in this browser only and talk to the CRM with it.
     Home IDs only ever leave this page. No key = hearts stay in this browser, exactly as before. */
  const CRM = "https://owner.getownerfinancedhomes.com", KB = "buyerKey", KEYRE = /^[A-Za-z0-9_-]{32,64}$/;
  function buyerKey(){ try { const k = localStorage.getItem(KB) || ""; return KEYRE.test(k) ? k : ""; } catch(e){ return ""; } }
  function adoptKey(){
    const m = /(?:^|[#&])buyer=([A-Za-z0-9_-]{32,64})(?:&|$)/.exec(location.hash || "");
    if (!m) return;
    try { localStorage.setItem(KB, m[1]); } catch(e){}
    try { history.replaceState(null, "", location.pathname + location.search); } catch(e){}
  }
  adoptKey();   // at load, before any page script rewrites the address and drops the #
  function remote(body){
    const k = buyerKey(); if (!k) return Promise.resolve(null);
    return fetch(`${CRM}/start/${k}/saved`, { method:"POST", headers:{ "Content-Type":"application/json" }, body:JSON.stringify(body), keepalive:true })
      .then(r => {
        if (r.status === 404 || r.status === 410){ try { localStorage.removeItem(KB); } catch(e){} return null; }  // link expired or replaced
        return r.ok ? r.json() : null;
      })
      .then(j => j && j.data && Array.isArray(j.data.saved) ? j.data.saved : null)
      .catch(() => null);
  }
  function pullSaved(){          // push what this browser already has, take back the buyer's full list
    remote({ add: saved }).then(list => {
      if (!list) return;
      saved = live(list).slice(-MAXS); store(KS, saved); sync();
    });
  }
  function toggleCmp(id){
    if (cmp.includes(id)) cmp = cmp.filter(x => x !== id);
    else { if (cmp.length >= MAXC){ alert(T.cmpFull); return; } cmp.push(id); }
    store(KC, cmp); sync(true);
  }

  /* ---------- tray + button states ---------- */
  function ensureTray(){
    if ($("hcTray")) return;
    const t = document.createElement("div"); t.className = "hc-tray"; t.id = "hcTray";
    t.innerHTML = `<button type="button" id="hcOpenSaved"><b>♥</b> <span id="hcSavedN"></span></button><button type="button" class="alt" id="hcOpenCmp" hidden><b>⇄</b> <span id="hcCmpN"></span></button>`;
    document.body.appendChild(t);
    $("hcOpenSaved").onclick = () => openPanel("saved");
    $("hcOpenCmp").onclick = () => openPanel("cmp");
  }
  function sync(bump){
    saved = live(saved); cmp = live(cmp);
    document.querySelectorAll("[data-save]").forEach(b => {
      const on = saved.includes(b.dataset.save);
      b.classList.toggle("on", on); b.setAttribute("aria-pressed", on); b.setAttribute("aria-label", on ? T.saved : T.save);
      const ic = b.querySelector(".hc-ic"); if (ic) ic.textContent = on ? "♥" : "♡";
      const tx = b.querySelector(".hc-tx"); if (tx) tx.textContent = on ? T.saved : T.save;
    });
    document.querySelectorAll("[data-cmp]").forEach(b => {
      const on = cmp.includes(b.dataset.cmp);
      b.classList.toggle("on", on); b.setAttribute("aria-pressed", on);
      const tx = b.querySelector(".hc-tx"); if (tx) tx.textContent = on ? T.cmpOn : T.cmp;
    });
    ensureTray();
    $("hcSavedN").textContent = `${T.mine} (${saved.length})`;
    $("hcCmpN").textContent = `${T.cmpN} (${cmp.length})`;
    $("hcOpenSaved").hidden = !saved.length; $("hcOpenCmp").hidden = !cmp.length;
    $("hcTray").classList.toggle("show", saved.length > 0 || cmp.length > 0);
    if (bump){ const b = $("hcOpenSaved"); b.classList.remove("bump"); void b.offsetWidth; b.classList.add("bump"); }
    if ($("hcModal") && $("hcModal").classList.contains("show") && view === "list") renderPanel();
  }

  /* ---------- panel ---------- */
  function ensureModal(){
    if ($("hcModal")) return;
    const m = document.createElement("div"); m.className = "hc-modal"; m.id = "hcModal";
    m.innerHTML = `<div class="hc-box" role="dialog" aria-modal="true" aria-label="${T.mine}"><div id="hcBody"></div></div>`;
    document.body.appendChild(m);
    m.addEventListener("click", e => { if (e.target === m) closePanel(); });
    document.addEventListener("keydown", e => { if (e.key === "Escape") closePanel(); });
  }
  function openPanel(t){ ensureModal(); tab = t || tab; view = "list"; $("hcModal").classList.add("show"); document.body.style.overflow = "hidden"; renderPanel(); }
  function closePanel(){ const m = $("hcModal"); if (m){ m.classList.remove("show"); document.body.style.overflow = ""; } }

  function renderPanel(){
    const body = $("hcBody");
    const head = `<div class="hc-head"><h3>${T.mine}</h3><button class="hc-x" type="button" data-hc="close" aria-label="Close">×</button></div>
      <div class="hc-tabs"><button type="button" class="${tab==="saved"?"on":""}" data-hc="tab-saved">♥ ${T.tabSaved} (${saved.length})</button><button type="button" class="${tab==="cmp"?"on":""}" data-hc="tab-cmp">⇄ ${T.tabCmp} (${cmp.length})</button></div>`;
    body.innerHTML = head + (tab === "saved" ? savedHTML() : cmpHTML());
  }

  function savedHTML(){
    if (!saved.length) return `<div class="hc-empty">${T.empty}</div>`;
    const items = saved.map(id => { const h = byId(id);
      const specs = [h.beds?`${h.beds} ${ES?"hab.":"bd"}`:"", h.baths?`${h.baths} ${ES?"baños":"ba"}`:"", h.moveIn?`${money(h.moveIn)} ${T.moveIn.toLowerCase()}`:""].filter(Boolean).join(" · ");
      return `<div class="hc-item">${thumb(h)}<div>
        <div class="pr">${money(h.monthlyPayment)}<small>${T.mo}</small></div>
        <div class="ad">${esc(label(h))}</div><div class="sp">${esc(specs)}</div>
        <div class="hc-acts">
          <a class="hc-book" href="https://owner.getownerfinancedhomes.com/book?home=${encodeURIComponent(id)}&lang=${ES?"es":"en"}">${T.book}</a>
          <button type="button" data-cmp="${esc(id)}"><span class="hc-tx">${cmp.includes(id)?T.cmpOn:T.cmp}</span></button>
          <a href="${encodeURIComponent(id)}.html">${T.view}</a>
          <button type="button" class="rm" data-hc="rm" data-id="${esc(id)}">${T.remove}</button></div></div></div>`; }).join("");
    return items + `<button type="button" class="hc-link" data-hc="close">${T.close}</button>`;
  }

  function best(vals, dir){           // indexes holding the best value (ignores empty/0)
    const nums = vals.map(v => Number(v) || 0); const pos = nums.filter(n => n > 0);
    if (pos.length < 2) return [];
    if (pos.every(n => n === pos[0])) return [];             // a tie highlights nothing
    const t = dir === "min" ? Math.min(...pos) : Math.max(...pos);
    return nums.map((n, i) => n === t ? i : -1).filter(i => i >= 0);
  }
  function cmpHTML(){
    if (cmp.length < 2) return `<div class="hc-empty">${T.cmpHint}${cmp.length?`<div class="hc-acts" style="justify-content:center;margin-top:10px"><button type="button" class="rm" data-hc="rm-cmp" data-id="${esc(cmp[0])}">${T.remove}</button></div>`:""}</div>`;
    const hs = cmp.map(byId);
    const row = (name, cells, bestIdx) => `<tr><th class="row" scope="row">${name}</th>${cells.map((c,i)=>`<td class="${bestIdx && bestIdx.includes(i)?"best":""}">${c}</td>`).join("")}</tr>`;
    const money0 = v => v ? money(v) : T.ask;
    const featKeys = FEAT_ORDER.filter(k => hs.some(h => (h.features||{})[k] === "yes" || (h.features||{})[k] === "no"));
    let rows = "";
    rows += `<tr><th class="row"></th>${hs.map(h => `<td><a href="${encodeURIComponent(h.id)}.html" style="text-decoration:none;color:inherit">${thumb(h).replace('class="hc-th"','class="ph"')}<div class="nm">${esc(h.address||h.city)}</div></a><div class="hc-acts"><button type="button" class="rm" data-hc="rm-cmp" data-id="${esc(h.id)}">${T.remove}</button></div></td>`).join("")}</tr>`;
    rows += row(T.pay, hs.map(h => h.monthlyPayment ? `${money(h.monthlyPayment)}${T.mo}` : T.ask), best(hs.map(h=>h.monthlyPayment),"min"));
    rows += row(T.moveIn, hs.map(h => money0(h.moveIn)), best(hs.map(h=>h.moveIn),"min"));
    rows += row(T.price, hs.map(h => money0(h.lockedPrice)), best(hs.map(h=>h.lockedPrice),"min"));
    rows += row(T.beds, hs.map(h => h.beds || "—"), best(hs.map(h=>h.beds),"max"));
    rows += row(T.baths, hs.map(h => h.baths || "—"), best(hs.map(h=>h.baths),"max"));
    rows += row(T.sqft, hs.map(h => h.sqft ? Number(h.sqft).toLocaleString() : "—"), best(hs.map(h=>h.sqft),"max"));
    rows += row(T.where, hs.map(h => esc([h.city, h.state].filter(Boolean).join(", "))));
    rows += row(T.status, hs.map(() => T.avail));
    featKeys.forEach(k => { rows += row(T.labels[k], hs.map(h => { const v = (h.features||{})[k]; return v === "yes" ? '<span class="y">✓</span>' : v === "no" ? '<span class="n">✕</span>' : '<span class="n">—</span>'; })); });
    return `<div class="hc-tw"><table class="hc-tbl">${rows}</table></div>
      <p class="hc-note">${featKeys.length ? T.featNote : ""}</p>
      <div class="hc-acts" style="margin-top:8px"><button type="button" data-hc="clear-cmp">${T.remove} ✕</button></div>`;
  }

  /* ---------- events ---------- */
  document.addEventListener("click", e => {
    const s = e.target.closest("[data-save]"), c = e.target.closest("[data-cmp]"), a = e.target.closest("[data-hc]");
    if (s){ e.preventDefault(); e.stopPropagation(); toggleSave(s.dataset.save); return; }
    if (c){ e.preventDefault(); e.stopPropagation(); toggleCmp(c.dataset.cmp); return; }
    if (!a) return;
    const k = a.dataset.hc;
    if (k === "close") closePanel();
    else if (k === "tab-saved"){ tab = "saved"; renderPanel(); }
    else if (k === "tab-cmp"){ tab = "cmp"; renderPanel(); }
    else if (k === "rm"){ saved = saved.filter(x => x !== a.dataset.id); store(KS, saved); tourSel = null; sync(); }
    else if (k === "rm-cmp"){ cmp = cmp.filter(x => x !== a.dataset.id); store(KC, cmp); sync(); }
    else if (k === "clear-cmp"){ cmp = []; store(KC, cmp); sync(); }
  }, true);
  // interest rides along on every lead form so the CRM sees what the buyer saved
  document.addEventListener("submit", e => {
    const f = e.target; if (!f || !f.id || !/^(leadForm|tlForm)$/.test(f.id) || !saved.length) return;
    [["saved_homes", saved.map(id => label(byId(id))).join("; ")], ["saved_ids", saved.join(",")], ["compared_ids", cmp.join(",")]].forEach(([n, v]) => {
      let i = f.querySelector(`input[name="${n}"]`);
      if (!i){ i = document.createElement("input"); i.type = "hidden"; i.name = n; f.appendChild(i); }
      i.value = v;
    });
  }, true);
  window.addEventListener("storage", ev => { if (ev.key === KS || ev.key === KC){ saved = live(load(KS)); cmp = live(load(KC)); sync(); } });


  /* ══════════ HOME ALERTS — "text me new homes like this" ══════════
     Posts to the same Formspree + Make endpoints as every lead form, source "Home alert".
     scripts/alerts.py (Filling repo) turns those submissions into subscribers. An alert IS a text,
     so the SMS opt-in box is REQUIRED here (everywhere else it's optional). */
  const TA = ES ? {
    btn:"🔔 Avíseme por texto de casas nuevas", h:"Avíseme cuando salga una casa así", lead:"Le escribimos solo cuando entra una casa nueva que cumple con lo que pide. Sin spam — puede cancelar con STOP en cualquier momento.",
    near:"Cerca de (ciudad o código postal)", within:"Dentro de", state:"o elija un estado", anyState:"Cualquier estado", pay:"Pago mensual máximo", down:"Efectivo máximo para mudarse",
    beds:"Habitaciones (mínimo)", any:"Cualquiera", go:"Activar mis alertas", sending:"Enviando…", needWhere:"Escriba una ciudad o código postal, o elija un estado.",
    noPlace:"Todavía no tenemos casas ahí — pruebe con una ciudad cercana o elija un estado.", needConsent:"Marque la casilla de mensajes de texto — las alertas se envían por texto.",
    doneH:"¡Listo — está en la lista!", doneP:"Le enviaremos un texto de confirmación y luego avisaremos cada vez que entre una casa que cumpla.", mi:"mi",
    required:"Necesaria para recibir alertas por texto."
  } : {
    btn:"🔔 Text me new homes like this", h:"Text me when a home like this comes in", lead:"We only text when a new home fits what you ask for. No spam — reply STOP anytime.",
    near:"Near (city or zip)", within:"Within", state:"or pick a state", anyState:"Any state", pay:"Max monthly payment", down:"Max cash to move in",
    beds:"Bedrooms (minimum)", any:"Any", go:"Turn on my alerts", sending:"Sending…", needWhere:"Enter a city or zip, or pick a state.",
    noPlace:"We don't have homes there yet — try a nearby city or pick a state.", needConsent:"Check the text-message box — alerts are sent by text.",
    doneH:"You're on the list!", doneP:"We'll text a confirmation, then let you know each time a home that fits comes in.", mi:"mi",
    required:"Required to get text alerts."
  };
  function placeKnown(q){
    const t = (q||"").trim().toLowerCase(); if (!t) return false;
    const zip = /^\d{5}$/.test(t);
    return ALL().some(h => typeof h.lat === "number" && (zip ? String(h.zip||"").slice(0,5) === t : (h.city||"").toLowerCase() === t.split(",")[0].trim()));
  }
  function ensureAlertModal(){
    if ($("haModal")) return;
    const m = document.createElement("div"); m.className = "hc-modal"; m.id = "haModal";
    m.innerHTML = `<div class="hc-box" style="max-width:480px" role="dialog" aria-modal="true" aria-label="${esc(TA.h)}"><div id="haBody"></div></div>`;
    document.body.appendChild(m);
    m.addEventListener("click", e => { if (e.target === m) m.classList.remove("show"); });
    document.addEventListener("keydown", e => { if (e.key === "Escape") m.classList.remove("show"); });
  }
  function openAlert(pre){
    pre = pre || {}; ensureAlertModal(); addStyle();
    const states = [...new Set(ALL().map(h => h.state).filter(Boolean))].sort();
    const sel = (opts, cur) => opts.map(([v, l]) => `<option value="${v}" ${String(cur||"")===String(v)?"selected":""}>${l}</option>`).join("");
    $("haBody").innerHTML = `<div class="hc-head"><h3>${esc(TA.h)}</h3><button class="hc-x" type="button" data-ha="close" aria-label="Close">×</button></div>
      <p style="margin:0 0 6px;color:var(--ink-soft,#5b6577);font-size:14.5px">${TA.lead}</p>
      <form class="hc-form" id="haForm">
        <label class="f" for="haNear">${TA.near}</label><input id="haNear" name="alert_near" type="text" value="${esc(pre.near||"")}" autocomplete="off">
        <div class="hc-two"><div><label class="f" for="haMi">${TA.within}</label><select id="haMi" name="alert_miles">${sel([[10,"10 "+TA.mi],[25,"25 "+TA.mi],[50,"50 "+TA.mi],[100,"100 "+TA.mi]], pre.miles||25)}</select></div>
          <div><label class="f" for="haState">${TA.state}</label><select id="haState" name="alert_state"><option value="">${TA.anyState}</option>${sel(states.map(x=>[x,x]), pre.state)}</select></div></div>
        <div class="hc-two"><div><label class="f" for="haPay">${TA.pay}</label><select id="haPay" name="alert_max_pay">${sel([["",TA.any],[700,"$700"],[900,"$900"],[1100,"$1,100"],[1300,"$1,300"]], pre.pay)}</select></div>
          <div><label class="f" for="haDown">${TA.down}</label><select id="haDown" name="alert_max_down">${sel([["",TA.any],[1500,"$1,500"],[2000,"$2,000"],[2500,"$2,500"],[3000,"$3,000"],[4000,"$4,000"]], pre.down)}</select></div></div>
        <label class="f" for="haBeds">${TA.beds}</label><select id="haBeds" name="alert_beds">${sel([["",TA.any],[1,"1+"],[2,"2+"],[3,"3+"],[4,"4+"]], pre.beds)}</select>
        <label class="f" for="haName">${T.name}</label><input id="haName" name="name" type="text" autocomplete="name" required>
        <label class="f" for="haPhone">${T.phone}</label><input id="haPhone" name="phone" type="tel" autocomplete="tel" required>
        <label class="f" for="haEmail">${T.email}</label><input id="haEmail" name="email" type="email" autocomplete="email">
        <label style="display:flex;gap:10px;align-items:flex-start;font-size:13px;line-height:1.5;color:var(--ink-soft,#5b6577);background:var(--paper,#f4f7fc);border:1px solid var(--line,#e2e8f2);border-radius:12px;padding:12px">
          <input name="sms_consent" type="checkbox" value="${ES?"Sí":"Yes"}" required style="margin-top:3px;width:16px;height:16px;flex-shrink:0"><span>${T.consent}</span></label>
        <p style="font:12px 'DM Mono',monospace;color:var(--ink-soft,#5b6577);margin:0">${TA.required}</p>
        <button type="submit" class="hc-cta" id="haSubmit" style="margin-top:2px">${TA.go}</button>
        <p id="haNote" style="font-size:13px;color:var(--honey,#e23b3b);margin:0" role="alert"></p>
      </form>`;
    $("haForm").addEventListener("submit", submitAlert);
    $("haModal").classList.add("show");
  }
  /* New-home alerts are OFF until Joe turns this on. Nothing is emailed or texted.
   When ALERTS_ENABLED is true, the messaging bot sends — this function must still not be the sender. */
  const ALERTS_ENABLED = false;
  async function submitAlert(e){
    e.preventDefault();
    const form = e.target, note = $("haNote"), btn = $("haSubmit");
    if (!ALERTS_ENABLED){
      if (note) note.textContent = ES ? "Las alertas están apagadas. No se envió nada." : "Alerts are off. Nothing was sent.";
      return;
    }
    const near = $("haNear").value.trim(), st = $("haState").value;
    note.textContent = "";
    if (!near && !st){ note.textContent = TA.needWhere; return; }
    if (near && !placeKnown(near)){ note.textContent = TA.noPlace; return; }
    if (!form.querySelector('input[name="sms_consent"]').checked){ note.textContent = TA.needConsent; return; }
    const C = (typeof CONTACT !== "undefined") ? CONTACT : {};
    const hook = (C.makeWebhook||"").trim(), fid = (C.formspreeId||"").trim();
    btn.disabled = true; btn.textContent = TA.sending;
    const data = new FormData(form);
    if (!near) data.delete("alert_miles");
    data.append("source", ES ? "Alerta de casas — casasconfinanciamiento" : "Home alert");
    data.append("language", ES ? "es" : "en");
    const crit = [near ? `near ${near} (${data.get("alert_miles")} mi)` : "", st ? "state " + st : "", data.get("alert_max_pay") ? "max pay $" + data.get("alert_max_pay") : "", data.get("alert_max_down") ? "max down $" + data.get("alert_max_down") : "", data.get("alert_beds") ? data.get("alert_beds") + "+ beds" : ""].filter(Boolean).join(" · ");
    data.append("message", "HOME ALERT signup — " + crit);
    try { if (typeof addConsentRecord === "function") await addConsentRecord(data, form); } catch(_){}
    const targets = [];
    if (fid)  targets.push(fetch(`https://formspree.io/f/${fid}`, { method:"POST", headers:{ "Accept":"application/json" }, body:data }));
    if (hook) targets.push(fetch(hook, { method:"POST", body:data }));
    const res = await Promise.allSettled(targets);
    if (res.some(r => r.status === "fulfilled" && r.value.ok)){
      $("haBody").innerHTML = `<div class="hc-head"><h3>${esc(TA.doneH)}</h3><button class="hc-x" type="button" data-ha="close" aria-label="Close">×</button></div><p>${TA.doneP}</p><p style="color:var(--ink-soft,#5b6577);font-size:14px">${esc(crit)}</p><button type="button" class="hc-cta" data-ha="close">${T.close}</button>`;
    } else { btn.disabled = false; btn.textContent = TA.go; note.textContent = T.fail; }
  }
  document.addEventListener("click", e => { const x = e.target.closest("[data-ha]"); if (x && x.dataset.ha === "close") $("haModal").classList.remove("show"); }, true);

  function init(){ addStyle(); adoptKey(); sync(); if (buyerKey()) pullSaved(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();

  window.HomesCart = { heart, compare, sync, open: openPanel, isSaved: id => saved.includes(id), alert: openAlert, alertLabel: TA.btn };
})();
