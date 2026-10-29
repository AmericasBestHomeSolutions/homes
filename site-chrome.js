/* Header pieces shared by the English and Spanish sites: domain, EN/ES, account link,
   and the Menu button. Safe to load on any page that has the existing top bar. */
(function () {
  const es = (document.documentElement.lang || "en").toLowerCase().startsWith("es");
  const EN = "https://getownerfinancedhomes.com";
  const ES = "https://casasconfinanciamiento.com";
  const small = document.querySelector(".brand .bn small, .brand .name small");
  if (small) small.textContent = es ? "casasconfinanciamiento.com" : "getownerfinancedhomes.com";

  const nav = document.querySelector(".topnav, .util");
  if (!nav) return;
  nav.querySelectorAll("a.call, #navCall").forEach(function (a) { a.remove(); });

  const id = window.__HOME_ID__ || new URLSearchParams(location.search).get("home");
  const file = (location.pathname.split("/").pop() || "index.html").toLowerCase();
  const mapToEN = {
    "como-funciona.html": "/how-it-works",
    "nosotros.html": "/about",
    "contacto.html": "/contact",
    "politica-de-privacidad.html": "/privacy-policy",
    "terminos-de-mensajes.html": "/messaging-terms",
    "account.html": "/"
  };
  const mapToES = {
    "how-it-works.html": "/como-funciona.html",
    "about.html": "/nosotros",
    "contact.html": "/contacto",
    "privacy-policy.html": "/politica-de-privacidad",
    "messaging-terms.html": "/terminos-de-mensajes",
    "account.html": "/"
  };
  let path = "/";
  if (id && file !== "index.html" && file !== "home.html" && file !== "account.html") path = "/" + id + ".html";
  else if (file === "home.html" && id) path = "/" + id + ".html";
  else if (es && mapToEN[file]) path = mapToEN[file];
  else if (!es && mapToES[file]) path = mapToES[file];
  else if (file && file !== "index.html" && file.endsWith(".html") && !id) path = "/" + file;

  const here = es ? ES : EN;
  const there = es ? EN : ES;

  let menu = nav.querySelector(".site-menu");
  if (!menu) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "nav-toggle";
    btn.setAttribute("aria-expanded", "false");
    btn.setAttribute("aria-controls", "siteMenu");
    btn.innerHTML = '<span class="nav-bars" aria-hidden="true"></span><span class="nav-word">' + (es ? "Menú" : "Menu") + "</span>";
    menu = document.createElement("div");
    menu.className = "site-menu";
    menu.id = "siteMenu";
    const links = es ? [
      ["/#listings", "Casas"],
      ["/como-funciona.html", "Cómo funciona"],
      ["/#por-que", "Comprar o rentar"],
      ["/nosotros", "Nosotros"],
      ["/#faq", "Preguntas"]
    ] : [
      ["/#listings", "Homes"],
      ["/how-it-works", "How it works"],
      ["/#why-buy", "Why buy vs rent"],
      ["/about", "About us"],
      ["/#faq", "FAQ"]
    ];
    menu.innerHTML = links.map(function (pair) {
      return '<a href="' + pair[0] + '">' + pair[1] + "</a>";
    }).join("") + '<a class="nav-es" href="#"></a>';
    nav.append(btn, menu);
  }

  const toggle = nav.querySelector(".nav-toggle");
  if (toggle && !toggle.dataset.wired) {
    toggle.dataset.wired = "1";
    toggle.addEventListener("click", function () {
      const open = nav.classList.toggle("menu-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    document.addEventListener("click", function (e) {
      if (!nav.contains(e.target)) {
        nav.classList.remove("menu-open");
        toggle.setAttribute("aria-expanded", "false");
      }
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        nav.classList.remove("menu-open");
        toggle.setAttribute("aria-expanded", "false");
      }
    });
  }

  const esLink = nav.querySelector(".nav-es");
  if (esLink) {
    const tail = id ? "/" + id + ".html" : ((file === "index.html" || file === "") ? "/" : path);
    esLink.href = there + tail;
    esLink.textContent = es ? "English" : "Español";
    esLink.hreflang = es ? "en" : "es";
  }

  if (!nav.querySelector(".lang")) {
    const lang = document.createElement("div");
    lang.className = "lang";
    lang.setAttribute("role", "group");
    lang.setAttribute("aria-label", es ? "Idioma" : "Language");
    const aHere = document.createElement("a");
    aHere.href = here + (id ? "/" + id + ".html" : ((file === "index.html" || file === "") ? "/" : path));
    aHere.textContent = es ? "ES" : "EN";
    aHere.hreflang = es ? "es" : "en";
    aHere.setAttribute("aria-current", "page");
    const aThere = document.createElement("a");
    aThere.href = there + (id ? "/" + id + ".html" : ((file === "index.html" || file === "") ? "/" : path));
    aThere.textContent = es ? "EN" : "ES";
    aThere.hreflang = es ? "en" : "es";
    lang.append(aHere, aThere);
    menu.append(lang);
  }

  if (!nav.querySelector("a.saved")) {
    let savedCount = 0;
    try { savedCount = JSON.parse(localStorage.getItem("savedHomes") || "[]").length; } catch (e) {}
    const saved = document.createElement("a");
    saved.className = "saved";
    saved.href = "account.html#saved";
    saved.innerHTML = (es ? "Guardados" : "Saved") + (savedCount ? '<span class="count">' + savedCount + "</span>" : "");
    menu.append(saved);
  }
  if (!nav.querySelector('a[href="account.html"], a[href="/account.html"]')) {
    const acct = document.createElement("a");
    acct.href = "account.html";
    acct.textContent = es ? "Cuenta" : "Account";
    if (file === "account.html") acct.setAttribute("aria-current", "page");
    menu.append(acct);
  }
})();
