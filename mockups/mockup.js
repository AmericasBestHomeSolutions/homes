/* Tiny behavior for the layout mockup. Nothing here talks to the live site.
   ALERTS_ENABLED is OFF. This page does not email or text anyone.
   When Joe turns alerts on, the messaging bot sends — not this file. */
const ALERTS_ENABLED = false;
(function () {
  document.querySelectorAll(".heart").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const on = btn.classList.toggle("on");
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      btn.setAttribute("aria-label", on ? "Saved" : "Save this home");
    });
  });

  document.querySelectorAll(".btn.save").forEach((btn) => {
    btn.addEventListener("click", () => {
      const on = btn.classList.toggle("on");
      const label = btn.querySelector(".save-label");
      if (label) label.textContent = on ? "Saved" : "Save";
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
  });

  document.querySelectorAll(".cmp").forEach((btn) => {
    btn.addEventListener("click", (e) => e.stopPropagation());
  });

  const toggle = document.querySelector(".view-toggle");
  if (toggle) {
    const listIcon = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M4 6h16v2H4zm0 5h16v2H4zm0 5h10v2H4z"/></svg> List';
    const mapIcon = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7zm0 9.5A2.5 2.5 0 1 1 12 6a2.5 2.5 0 0 1 0 5.5z"/></svg> Map';
    const paint = () => {
      const mapOn = document.body.classList.contains("show-map");
      toggle.innerHTML = mapOn ? listIcon : mapIcon;
      toggle.setAttribute("aria-pressed", mapOn ? "true" : "false");
    };
    const params = new URLSearchParams(location.search);
    if (params.has("map")) document.body.classList.add("show-map");
    if (params.has("full")) document.body.classList.add("shot-full");
    toggle.addEventListener("click", () => {
      document.body.classList.toggle("show-map");
      paint();
    });
    paint();
  }

  document.querySelectorAll("form.search").forEach((form) => {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const q = (form.querySelector("input") || {}).value || "";
      const h1 = document.querySelector(".list-head h1");
      if (h1 && /^\d{5}$/.test(q.trim())) h1.textContent = "ZIP " + q.trim();
    });
  });

  const nearBtn = document.getElementById("nearBtn");
  if (nearBtn) {
    nearBtn.addEventListener("click", () => {
      const msg = document.getElementById("nearMsg");
      if (!navigator.geolocation) {
        if (msg) msg.textContent = "Location isn't available. Search a ZIP.";
        return;
      }
      nearBtn.textContent = "Finding you…";
      navigator.geolocation.getCurrentPosition((pos) => {
        const { latitude, longitude } = pos.coords;
        const miles = (lat, lng) => {
          const r = Math.PI / 180, R = 3958.8;
          const x = Math.sin((lat - latitude) * r / 2) ** 2 + Math.cos(latitude * r) * Math.cos(lat * r) * Math.sin((lng - longitude) * r / 2) ** 2;
          return 2 * R * Math.asin(Math.sqrt(x));
        };
        const list = document.querySelector(".list");
        const cards = [...document.querySelectorAll(".list .card")];
        cards.sort((a, b) => miles(+a.dataset.lat, +a.dataset.lng) - miles(+b.dataset.lat, +b.dataset.lng));
        cards.forEach((card) => list.appendChild(card));
        const sort = document.querySelector(".sort");
        if (sort) sort.textContent = "Nearest";
        nearBtn.textContent = "Near you";
        nearBtn.classList.add("on");
        if (msg) msg.textContent = "";
      }, () => {
        nearBtn.textContent = "Near me";
        if (msg) msg.textContent = "We couldn't use your location. Search a ZIP.";
      });
    });
  }

  const alertOn = document.getElementById("alertOn");
  if (alertOn) {
    alertOn.checked = false;
    alertOn.addEventListener("change", () => {
      if (ALERTS_ENABLED) return;
      alertOn.checked = false;
      const hold = document.getElementById("alertHold");
      if (hold) hold.hidden = false;
    });
  }
})();
