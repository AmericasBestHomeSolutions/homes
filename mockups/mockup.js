/* Tiny behavior for the layout mockup. Nothing here talks to the live site. */
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

  document.querySelectorAll("form[data-mock]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const note = form.querySelector(".form-note");
      if (note) note.textContent = "Mockup only — nothing was sent.";
    });
  });
})();
