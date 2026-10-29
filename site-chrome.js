/* Header pieces shared by the English and Spanish sites: domain, EN/ES, account link.
   Safe to load on any page that has the existing top bar. */
(function () {
  const es = (document.documentElement.lang || "en").toLowerCase().startsWith("es");
  const EN = "https://getownerfinancedhomes.com";
  const ES = "https://casasconfinanciamiento.com";
  const small = document.querySelector(".brand .bn small, .brand .name small");
  if (small) small.textContent = es ? "casasconfinanciamiento.com" : "getownerfinancedhomes.com";

  const nav = document.querySelector(".topnav, .util");
  if (!nav || nav.querySelector(".lang")) return;
  const id = window.__HOME_ID__ || new URLSearchParams(location.search).get("home");
  const file = (location.pathname.split("/").pop() || "index.html").toLowerCase();
  const mapToEN = {
    "como-funciona.html": "/how-it-works.html",
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
  const lang = document.createElement("div");
  lang.className = "lang";
  lang.setAttribute("role", "group");
  lang.setAttribute("aria-label", es ? "Idioma" : "Language");
  const aHere = document.createElement("a");
  aHere.href = here + (id ? "/" + id + ".html" : (file === "index.html" || file === "" ? "/" : path));
  aHere.textContent = es ? "ES" : "EN";
  aHere.hreflang = es ? "es" : "en";
  aHere.setAttribute("aria-current", "page");
  const aThere = document.createElement("a");
  aThere.href = there + path;
  aThere.textContent = es ? "EN" : "ES";
  aThere.hreflang = es ? "en" : "es";
  lang.append(aHere, aThere);

  const acct = document.createElement("a");
  acct.href = "account.html";
  acct.textContent = es ? "Cuenta" : "Account";
  if (file === "account.html") acct.setAttribute("aria-current", "page");

  let savedCount = 0;
  try { savedCount = JSON.parse(localStorage.getItem("savedHomes") || "[]").length; } catch (e) {}
  const saved = document.createElement("a");
  saved.className = "saved";
  saved.href = "account.html#saved";
  saved.innerHTML = (es ? "Guardados" : "Saved") + (savedCount ? `<span class="count">${savedCount}</span>` : "");

  const call = nav.querySelector(".call");
  nav.insertBefore(lang, call || nav.firstChild);
  nav.insertBefore(saved, call || null);
  nav.insertBefore(acct, call || null);
})();
