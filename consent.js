/* ══════════════════════════════════════════════════════════════════════════
   SMS CONSENT RECORD — A2P 10DLC evidence capture
   ══════════════════════════════════════════════════════════════════════════
   Carriers can ask us, months later, to produce proof that a specific phone
   number opted in. That proof has to include WHAT the person saw, not just
   that a box was ticked. So every lead form on this site sends these fields
   alongside the normal name/phone/email:

     sms_consent          "Yes" / "No"   (never blank — "No" is a real record)
     consent_timestamp    ISO-8601 UTC
     consent_timestamp_local  human-readable, with timezone
     consent_ip           submitter's public IP (see note below)
     consent_page_url     the exact page the form was on
     consent_text_version CONSENT_TEXT_VERSION below
     consent_text         the verbatim wording displayed at submit time

   Bump CONSENT_TEXT_VERSION *and* CONSENT_TEXT together whenever the wording
   on the checkbox changes. Old records keep their old version string, which
   is the whole point — we can always show what a given person agreed to.

   IP note: a browser can't read its own public IP, so we ask ipify for it.
   If that call fails or is blocked we send "unavailable" rather than silently
   dropping the field — Formspree also records the submitting IP server-side,
   so that stays a backstop. ipify is disclosed in the Privacy Policy.
   ══════════════════════════════════════════════════════════════════════════ */

const CONSENT_TEXT_VERSION = "2026-08-07.v1";

const CONSENT_TEXT =
  "I agree to receive text messages from Americas Best Home Solutions LLC " +
  "about property listings, showings, offers, and follow-up. Message frequency " +
  "varies. Message and data rates may apply. Reply STOP to unsubscribe or HELP " +
  "for help. See our Privacy Policy and Messaging Terms.";

/* Fetch the public IP once per page load, with a short timeout so a slow or
   blocked lookup can never hold up a lead. Resolves to a string, never throws. */
const CONSENT_IP = (function () {
  if (!window.fetch || !window.AbortController) return Promise.resolve("unavailable");
  const stop = new AbortController();
  const timer = setTimeout(() => stop.abort(), 2500);
  return fetch("https://api.ipify.org?format=json", { signal: stop.signal })
    .then((r) => (r.ok ? r.json() : null))
    .then((j) => (j && j.ip ? j.ip : "unavailable"))
    .catch(() => "unavailable")
    .finally(() => clearTimeout(timer));
})();

/* Append the consent evidence fields to a FormData about to be submitted.
   `form` is the <form> element; the checkbox must be named "sms_consent". */
async function addConsentRecord(data, form) {
  const box = form.querySelector('input[name="sms_consent"]');
  const now = new Date();

  // An unchecked box is meaningful evidence too: it proves we were told NOT to
  // text this person. FormData omits unchecked boxes, so set it explicitly.
  data.set("sms_consent", box && box.checked ? "Yes" : "No");
  data.set("consent_timestamp", now.toISOString());
  data.set("consent_timestamp_local", now.toString());
  data.set("consent_page_url", window.location.href);
  data.set("consent_text_version", CONSENT_TEXT_VERSION);
  data.set("consent_text", CONSENT_TEXT);
  data.set("consent_ip", await CONSENT_IP);
  return data;
}
