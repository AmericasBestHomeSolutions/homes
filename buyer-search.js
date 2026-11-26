/* Buyer search: city or ZIP, max down, max monthly.
   Results stay on this page. A ZIP centroid file is fetched only after a
   5-digit ZIP is typed. Same file on the English and Spanish sites. */
(function (root) {
  "use strict";
  var NEAR_MILES = 50;
  var ZIP_MILES = 15;

  function num(value) {
    var n = Number(String(value == null ? "" : value).replace(/[$,]/g, ""));
    return isFinite(n) ? n : NaN;
  }

  function cityKey(name) {
    return String(name || "").toLowerCase().replace(/\./g, "").replace(/\bsaint\b/g, "st").replace(/[^a-z0-9]/g, "");
  }

  function cleanZip(value) {
    var text = String(value || "").trim();
    if (/\.0$/.test(text)) text = text.slice(0, -2);
    var match = text.match(/^(\d{5})/);
    return match ? match[1] : "";
  }

  function coords(home) {
    var lat = Number(home.lat), lng = Number(home.lng);
    if (!isFinite(lat) || !isFinite(lng)) return null;
    if (lat === 0 && lng === 0) return null;
    return { lat: lat, lng: lng };
  }

  function haversine(a, b) {
    var radius = 3958.7613;
    var dLat = (b.lat - a.lat) * Math.PI / 180;
    var dLng = (b.lng - a.lng) * Math.PI / 180;
    var lat1 = a.lat * Math.PI / 180, lat2 = b.lat * Math.PI / 180;
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return 2 * radius * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  function isPending(home) {
    return /^pending$/i.test(String((home && home.status) || "").trim());
  }

  function isAvailable(home) {
    return !isPending(home) && !/^sold$/i.test(String((home && home.status) || "").trim());
  }

  function hasPhoto(home) {
    return !!(home && (home.hasPhoto === true || home.hasPhoto === "true" || home.hasPhoto === 1));
  }

  function positive(value) {
    var n = num(value);
    return isFinite(n) && n > 0 ? n : 0;
  }

  function limitsOf(opts) {
    opts = opts || {};
    return {
      downMin: positive(opts.downMin),
      downMax: positive(opts.downMax),
      payMin: positive(opts.payMin),
      payMax: positive(opts.payMax),
      bedsMin: positive(opts.bedsMin)
    };
  }

  function knownBeds(home) {
    var beds = num(home && home.beds);
    return isFinite(beds) && beds > 0 ? beds : 0;
  }

  function inBudget(home, limits) {
    limits = limits || {};
    var down = num(home.moveIn), pay = num(home.monthlyPayment);
    if (limits.downMax && (!isFinite(down) || down > limits.downMax)) return false;
    if (limits.downMin && (!isFinite(down) || down < limits.downMin)) return false;
    if (limits.payMax && (!isFinite(pay) || pay > limits.payMax)) return false;
    if (limits.payMin && (!isFinite(pay) || pay < limits.payMin)) return false;
    if (limits.bedsMin && knownBeds(home) < limits.bedsMin) return false;
    return true;
  }

  function centroid(list) {
    var points = [];
    list.forEach(function (home) {
      var point = coords(home);
      if (point) points.push(point);
    });
    if (!points.length) return null;
    var lat = 0, lng = 0;
    points.forEach(function (point) { lat += point.lat; lng += point.lng; });
    return { lat: lat / points.length, lng: lng / points.length };
  }

  function resolvePlace(query, listings) {
    var raw = String(query || "").trim();
    if (/^\d{5}$/.test(raw)) return { kind: "zip", zip: raw };
    var labeled = raw.match(/^(.+?)\s*,\s*([a-z]{2})$/i);
    var name = raw, state = "";
    if (labeled) { name = labeled[1]; state = labeled[2].toUpperCase(); }
    var key = cityKey(name);
    var words = raw.toLowerCase().replace(/[.,#]/g, " ").split(/\s+/).filter(Boolean);
    if (!key || key.length < 3) return words.length ? { kind: "text", words: words } : { kind: "none" };
    var cities = [], seen = {};
    (listings || []).forEach(function (home) {
      if (!home.city || !home.state) return;
      var id = cityKey(home.city) + "|" + String(home.state).toUpperCase();
      if (seen[id]) return;
      seen[id] = 1;
      cities.push({ city: home.city, state: String(home.state).toUpperCase(), key: cityKey(home.city) });
    });
    var exact = cities.filter(function (city) { return city.key === key && (!state || city.state === state); });
    if (exact.length === 1) return { kind: "city", city: exact[0].city, state: exact[0].state };
    if (exact.length > 1) return { kind: "city", city: exact[0].city, state: state };
    var prefix = cities.filter(function (city) { return city.key.indexOf(key) === 0 && (!state || city.state === state); });
    if (prefix.length === 1) return { kind: "city", city: prefix[0].city, state: prefix[0].state };
    return words.length ? { kind: "text", words: words } : { kind: "none" };
  }

  function sameCity(home, place) {
    if (cityKey(home.city) !== cityKey(place.city)) return false;
    if (place.state && String(home.state || "").toUpperCase() !== place.state) return false;
    return true;
  }

  function byAvailThenDistance(center) {
    return function (a, b) {
      var pendingDelta = (isPending(a) ? 1 : 0) - (isPending(b) ? 1 : 0);
      if (pendingDelta) return pendingDelta;
      if (center && coords(a) && coords(b)) {
        var delta = haversine(center, coords(a)) - haversine(center, coords(b));
        if (Math.abs(delta) > 0.01) return delta;
      }
      return String(a.address || "").localeCompare(String(b.address || ""));
    };
  }

  function withMiles(list, center) {
    list.forEach(function (home) {
      var point = coords(home);
      home._miles = point && center ? Math.round(haversine(center, point)) : null;
    });
    list.sort(function (a, b) {
      return (a._miles == null ? 9999 : a._miles) - (b._miles == null ? 9999 : b._miles) || String(a.address || "").localeCompare(String(b.address || ""));
    });
    return list;
  }

  function groups(listings, opts) {
    opts = opts || {};
    var place = opts.place || resolvePlace(opts.q, listings);
    var limits = limitsOf(opts);
    var primary = [], nearby = [], over = [], center = null;
    if (place.kind === "city") {
      var inCity = (listings || []).filter(function (home) { return sameCity(home, place); });
      center = centroid(inCity);
      primary = inCity.filter(function (home) { return inBudget(home, limits); });
      primary.sort(byAvailThenDistance(center));
      var availableHere = primary.filter(isAvailable);
      if (!availableHere.some(hasPhoto)) {
        over = inCity.filter(function (home) {
          return isAvailable(home) && hasPhoto(home) && !inBudget(home, limits);
        });
        over.sort(byAvailThenDistance(center));
      }
      if (availableHere.length < 3 && center) {
        nearby = (listings || []).filter(function (home) {
          if (!isAvailable(home) || sameCity(home, place) || !inBudget(home, limits)) return false;
          var point = coords(home);
          return !!(point && haversine(center, point) <= NEAR_MILES);
        });
        withMiles(nearby, center);
      }
    } else if (place.kind === "zip") {
      var zipIndex = opts.zipIndex || {};
      var hit = zipIndex[place.zip];
      center = hit ? { lat: Number(hit[0]), lng: Number(hit[1]) } : null;
      primary = (listings || []).filter(function (home) {
        if (!inBudget(home, limits)) return false;
        if (cleanZip(home.zip) === place.zip) return true;
        if (!center || cleanZip(home.zip)) return false;
        var point = coords(home);
        return !!(point && haversine(center, point) <= ZIP_MILES);
      });
      primary.sort(byAvailThenDistance(center));
      if (primary.filter(isAvailable).length < 3 && center) {
        var seen = {};
        primary.forEach(function (home) { seen[home.id] = 1; });
        nearby = (listings || []).filter(function (home) {
          if (!isAvailable(home) || seen[home.id] || !inBudget(home, limits)) return false;
          var point = coords(home);
          return !!(point && haversine(center, point) <= NEAR_MILES);
        });
        withMiles(nearby, center);
      }
    } else {
      return null;
    }
    return { place: place, primary: primary, nearby: nearby, over: over };
  }

  var zipPromise = null;
  function loadZips() {
    if (zipPromise) return zipPromise;
    if (typeof fetch !== "function") {
      zipPromise = Promise.resolve({});
      return zipPromise;
    }
    zipPromise = fetch("/data/zip-centroids.json", { credentials: "same-origin" })
      .then(function (response) { return response.ok ? response.json() : {}; })
      .then(function (doc) { return (doc && doc.z) || {}; })
      .catch(function () { return {}; });
    return zipPromise;
  }

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"]/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch];
    });
  }

  function moneyText(value) {
    var n = num(value);
    if (!isFinite(n) || n <= 0) return "";
    return "$" + Math.round(n).toLocaleString();
  }

  function readLimits(form) {
    function val(id) {
      var el = form.querySelector("#" + id);
      return el ? el.value : "";
    }
    return limitsOf({
      downMin: val("chipDownMin") || val("downMin"),
      downMax: val("chipDownMax") || val("fDown"),
      payMin: val("chipPayMin") || val("payMin"),
      payMax: val("chipPayMax") || val("fPayMax"),
      bedsMin: val("bedsMin")
    });
  }

  function bindChips(form) {
    if (!form || form.dataset.chips === "1") return;
    form.dataset.chips = "1";
    form.querySelectorAll(".range-chips").forEach(function (group) {
      group.addEventListener("click", function (event) {
        var btn = event.target.closest("button");
        if (!btn || !group.contains(btn)) return;
        group.querySelectorAll("button").forEach(function (other) {
          other.setAttribute("aria-pressed", other === btn ? "true" : "false");
        });
        var minId = group.getAttribute("data-min");
        var maxId = group.getAttribute("data-max");
        if (minId) {
          var minEl = form.querySelector("#" + minId);
          if (minEl) minEl.value = btn.getAttribute("data-min") || "";
        }
        if (maxId) {
          var maxEl = form.querySelector("#" + maxId);
          if (maxEl) maxEl.value = btn.getAttribute("data-max") || "";
        }
        form.dispatchEvent(new Event("change", { bubbles: true }));
      });
    });
  }

  function miniCard(home, es) {
    var beds = knownBeds(home);
    var pending = isPending(home);
    var bedLabel = beds
      ? (es ? (beds + (beds === 1 ? " recámara" : " recámaras")) : (beds + (beds === 1 ? " bed" : " beds")))
      : (es ? "recámaras no indicadas" : "beds not listed");
    var photo = home.hasPhoto
      ? '<img src="/images/cards/' + esc(home.id) + '-480.webp" alt="" width="480" height="360" loading="lazy" decoding="async">'
      : "";
    var miles = home._miles == null ? "" : (es ? "a unas " + home._miles + " millas" : "about " + home._miles + " miles away");
    var bits = [moneyText(home.lockedPrice), moneyText(home.moveIn) ? moneyText(home.moveIn) + (es ? " enganche" : " down") : "", moneyText(home.monthlyPayment) ? moneyText(home.monthlyPayment) + (es ? "/mes" : "/mo") : ""].filter(Boolean);
    var avail = pending ? (es ? "Pendiente: visitas cerradas" : "Pending: tours closed") : (es ? "Disponible ahora" : "Available now");
    return '<article class="swipe-card" data-down="' + esc(home.moveIn || "") + '" data-pay="' + esc(home.monthlyPayment || "") + '" data-beds="' + esc(beds || "") + '" data-status="' + esc(home.status || "") + '" data-photo="' + (home.hasPhoto ? "1" : "0") + '"><a href="/' + esc(home.id) + '.html">' + photo + '<p class="where">' + esc(home.address || home.id) + '</p><p class="meta">' + esc(bits.join(" · ")) + '</p><p class="meta">' + esc(bedLabel + (miles ? " · " + miles : "")) + '</p><p class="avail">' + esc(avail) + '</p></a></article>';
  }

  function mountCity() {
    var form = document.getElementById("buyerSearch");
    var list = document.getElementById("cityHomes");
    if (!form || !list || form.dataset.bound === "1") return;
    form.dataset.bound = "1";
    bindChips(form);
    var es = (document.documentElement.lang || "en") === "es";
    var extra = document.getElementById("buyerExtra");
    var empty = document.getElementById("cityEmpty");
    var pageSize = 24;
    var shown = pageSize;
    var moreBtn = document.getElementById("showMoreHomes");
    if (!moreBtn) {
      moreBtn = document.createElement("button");
      moreBtn.type = "button";
      moreBtn.id = "showMoreHomes";
      moreBtn.className = "chip-clear";
      moreBtn.hidden = true;
      list.insertAdjacentElement("afterend", moreBtn);
      moreBtn.addEventListener("click", function () {
        shown += pageSize;
        applyLocal();
      });
    }
    function applyLocal() {
      var limits = readLimits(form);
      var availableShown = 0, photoShown = false, matched = 0;
      Array.prototype.forEach.call(list.children, function (li) {
        if (!li.classList || !li.classList.contains("swipe-card")) return;
        var ok = inBudget({
          moveIn: li.getAttribute("data-down"),
          monthlyPayment: li.getAttribute("data-pay"),
          beds: li.getAttribute("data-beds")
        }, limits);
        if (!ok) { li.hidden = true; li.dataset.paged = ""; return; }
        matched += 1;
        li.hidden = matched > shown;
        li.dataset.paged = matched > shown ? "1" : "";
        var pending = /pending/i.test(li.getAttribute("data-status") || "");
        if (!pending && matched <= shown) {
          availableShown += 1;
          if (li.getAttribute("data-photo") === "1") photoShown = true;
        }
      });
      if (moreBtn) {
        var left = matched - shown;
        moreBtn.hidden = left <= 0;
        moreBtn.textContent = es
          ? ("Mostrar " + Math.min(pageSize, Math.max(left, 0)) + " más")
          : ("Show " + Math.min(pageSize, Math.max(left, 0)) + " more");
      }
      if (empty) empty.hidden = availableShown > 0 || list.querySelector(":scope > :not([hidden])");
      if (!extra) return;
      var over = "";
      if (!photoShown) {
        Array.prototype.forEach.call(list.children, function (li) {
          if (li.hidden && li.dataset.paged !== "1" && !/pending/i.test(li.getAttribute("data-status") || "") && li.getAttribute("data-photo") === "1") {
            over += li.outerHTML.replace(' hidden=""', "").replace(" hidden", "");
          }
        });
      }
      var heading = es ? "Apenas sobre su presupuesto" : "Just over your budget";
      extra.innerHTML = over ? '<section class="buyer-group"><h2>' + heading + '</h2><div class="row-scroller">' + over + '</div></section>' : "";
      if (availableShown < 3) loadNearby(limits);
      else {
        var near = extra.querySelector("#nearby");
        if (near) near.remove();
      }
    }
    var catalog = null;
    function loadNearby(limits) {
      var query = (form.querySelector("#fQ").value || "").trim();
      var place = resolvePlace(query, catalog || [{ city: form.dataset.city, state: form.dataset.state }]);
      if (place.kind !== "city") {
        window.location.href = "/?" + new URLSearchParams(new FormData(form)).toString();
        return;
      }
      var run = function (homes) {
        var result = groups(homes, {
          place: place,
          downMin: limits.downMin, downMax: limits.downMax,
          payMin: limits.payMin, payMax: limits.payMax,
          bedsMin: limits.bedsMin
        });
        if (!result || !extra) return;
        var items = result.nearby.map(function (home) { return miniCard(home, es); }).join("");
        var title = es ? "Casas cercanas en su presupuesto" : "Nearby homes in your budget";
        var note = es ? "Nada en ese rango en esta ciudad. Estas casas cercanas sí caben." : "Nothing in that range here. These nearby homes fit.";
        var block = items ? '<section class="buyer-group" id="nearby"><h2>' + title + '</h2><p class="row-hint">' + note + '</p><div class="row-scroller">' + items + '</div></section>' : "";
        if (extra.querySelector("#nearby")) extra.querySelector("#nearby").outerHTML = block;
        else extra.insertAdjacentHTML("beforeend", block);
      };
      if (catalog) { run(catalog); return; }
      fetch("/data/buyer-index.json", { credentials: "same-origin" })
        .then(function (response) { return response.ok ? response.json() : { homes: [] }; })
        .then(function (doc) { catalog = doc.homes || []; run(catalog); })
        .catch(function () {});
    }
    function resetPage() { shown = pageSize; applyLocal(); }
    form.addEventListener("submit", function (event) { event.preventDefault(); resetPage(); });
    form.addEventListener("change", resetPage);
    form.addEventListener("input", function (event) {
      if (event.target && event.target.id === "fQ") resetPage();
    });
    var clearBtn = form.querySelector("#clearBuyer");
    if (clearBtn && !clearBtn.dataset.wired) {
      clearBtn.dataset.wired = "1";
      clearBtn.addEventListener("click", function () {
        ["chipDownMin", "chipDownMax", "chipPayMin", "chipPayMax", "bedsMin", "downMin", "fDown", "payMin", "fPayMax"].forEach(function (id) {
          var el = form.querySelector("#" + id);
          if (el && el.type === "hidden") el.value = "";
        });
        form.querySelectorAll(".range-chips").forEach(function (group) {
          group.querySelectorAll("button").forEach(function (b, i) {
            b.setAttribute("aria-pressed", i === 0 ? "true" : "false");
          });
        });
        resetPage();
      });
    }
    resetPage();
  }

  root.BuyerSearch = {
    groups: groups,
    resolvePlace: resolvePlace,
    haversine: haversine,
    cleanZip: cleanZip,
    loadZips: loadZips,
    hasPhoto: hasPhoto,
    isPending: isPending,
    knownBeds: knownBeds,
    limitsOf: limitsOf,
    bindChips: bindChips,
    readLimits: readLimits,
    mountCity: mountCity,
    NEAR_MILES: NEAR_MILES,
    ZIP_MILES: ZIP_MILES
  };

  if (typeof document !== "undefined" && document.documentElement && document.documentElement.hasAttribute("data-city-landing")) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mountCity);
    else mountCity();
  }
})(typeof window !== "undefined" ? window : globalThis);
