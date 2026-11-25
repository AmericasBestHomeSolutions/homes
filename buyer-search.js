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

  function inBudget(home, downMax, payMax) {
    var down = num(home.moveIn), pay = num(home.monthlyPayment);
    if (downMax && (!isFinite(down) || down > downMax)) return false;
    if (payMax && (!isFinite(pay) || pay > payMax)) return false;
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
    var downMax = num(opts.downMax), payMax = num(opts.payMax);
    if (!isFinite(downMax) || downMax <= 0) downMax = 0;
    if (!isFinite(payMax) || payMax <= 0) payMax = 0;
    var primary = [], nearby = [], over = [], center = null;
    if (place.kind === "city") {
      var inCity = (listings || []).filter(function (home) { return sameCity(home, place); });
      center = centroid(inCity);
      primary = inCity.filter(function (home) { return inBudget(home, downMax, payMax); });
      primary.sort(byAvailThenDistance(center));
      var availableHere = primary.filter(isAvailable);
      if (!availableHere.some(hasPhoto)) {
        over = inCity.filter(function (home) {
          return isAvailable(home) && hasPhoto(home) && !inBudget(home, downMax, payMax);
        });
        over.sort(byAvailThenDistance(center));
      }
      if (availableHere.length < 3 && center) {
        nearby = (listings || []).filter(function (home) {
          if (!isAvailable(home) || sameCity(home, place) || !inBudget(home, downMax, payMax)) return false;
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
        if (!inBudget(home, downMax, payMax)) return false;
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
          if (!isAvailable(home) || seen[home.id] || !inBudget(home, downMax, payMax)) return false;
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

  function mountCity() {
    var form = document.getElementById("buyerSearch");
    var list = document.getElementById("cityHomes");
    if (!form || !list || form.dataset.bound === "1") return;
    form.dataset.bound = "1";
    var es = (document.documentElement.lang || "en") === "es";
    var extra = document.getElementById("buyerExtra");
    function budget() {
      return { downMax: form.querySelector("#fDown").value, payMax: form.querySelector("#fPayMax").value };
    }
    function applyLocal() {
      var limits = budget();
      var downMax = num(limits.downMax), payMax = num(limits.payMax);
      if (!isFinite(downMax) || downMax <= 0) downMax = 0;
      if (!isFinite(payMax) || payMax <= 0) payMax = 0;
      var availableShown = 0, photoShown = false;
      Array.prototype.forEach.call(list.children, function (li) {
        var down = num(li.getAttribute("data-down")), pay = num(li.getAttribute("data-pay"));
        var ok = (!downMax || (isFinite(down) && down <= downMax)) && (!payMax || (isFinite(pay) && pay <= payMax));
        li.hidden = !ok;
        var pending = /pending/i.test(li.getAttribute("data-status") || "");
        if (ok && !pending) {
          availableShown += 1;
          if (li.getAttribute("data-photo") === "1") photoShown = true;
        }
      });
      if (!extra) return;
      var over = "";
      if (!photoShown) {
        Array.prototype.forEach.call(list.children, function (li) {
          if (li.hidden && !/pending/i.test(li.getAttribute("data-status") || "") && li.getAttribute("data-photo") === "1") {
            over += '<li>' + li.innerHTML + '</li>';
          }
        });
      }
      var heading = es ? "Apenas sobre su presupuesto" : "Just over your budget";
      extra.innerHTML = over ? '<section class="buyer-group"><h2>' + heading + '</h2><ul class="city-list">' + over + '</ul></section>' : "";
      if (availableShown < 3) loadNearby(downMax, payMax);
    }
    var catalog = null;
    function loadNearby(downMax, payMax) {
      var query = (form.querySelector("#fQ").value || "").trim();
      var place = resolvePlace(query, catalog || [{ city: form.dataset.city, state: form.dataset.state }]);
      if (place.kind !== "city") {
        window.location.href = "/?" + new URLSearchParams(new FormData(form)).toString();
        return;
      }
      var run = function (homes) {
        var result = groups(homes, { place: place, downMax: downMax, payMax: payMax });
        if (!result || !extra) return;
        var items = result.nearby.map(function (home) {
          var miles = home._miles == null ? "" : (es ? "a unas " + home._miles + " millas" : "about " + home._miles + " miles away");
          return '<li><a href="/' + home.id + '.html">' + (home.address || home.id) + '</a><span class="meta">' + miles + '</span></li>';
        }).join("");
        var title = es ? "Casas cercanas en su presupuesto" : "Nearby homes in your budget";
        var block = items ? '<section class="buyer-group" id="nearby"><h2>' + title + '</h2><ul class="city-list">' + items + '</ul></section>' : "";
        if (extra.querySelector("#nearby")) extra.querySelector("#nearby").outerHTML = block;
        else extra.insertAdjacentHTML("beforeend", block);
      };
      if (catalog) { run(catalog); return; }
      fetch("/data/buyer-index.json", { credentials: "same-origin" })
        .then(function (response) { return response.ok ? response.json() : { homes: [] }; })
        .then(function (doc) { catalog = doc.homes || []; run(catalog); })
        .catch(function () {});
    }
    form.addEventListener("submit", function (event) { event.preventDefault(); applyLocal(); });
    form.addEventListener("change", applyLocal);
    form.addEventListener("input", function (event) {
      if (event.target && event.target.id === "fQ") applyLocal();
    });
  }

  root.BuyerSearch = {
    groups: groups,
    resolvePlace: resolvePlace,
    haversine: haversine,
    cleanZip: cleanZip,
    loadZips: loadZips,
    hasPhoto: hasPhoto,
    isPending: isPending,
    mountCity: mountCity,
    NEAR_MILES: NEAR_MILES,
    ZIP_MILES: ZIP_MILES
  };

  if (typeof document !== "undefined" && document.documentElement && document.documentElement.hasAttribute("data-city-landing")) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mountCity);
    else mountCity();
  }
})(typeof window !== "undefined" ? window : globalThis);
