/* ══════════════════════════════════════════════════════════════════════════
   LONCHANDO — ALL YOUR HOMES LIVE IN THIS ONE FILE
   ▼▼▼ This is the ONLY file you edit to add, change, or remove a home. ▼▼▼

   TO ADD A HOME: copy one { ... } block in the HOMES list below (from its
   opening { to its closing },), paste it after the last one, and change the
   values. Give it a unique "id" — that becomes its web address, e.g.
   id: "memphis-1"  →  home.html?home=memphis-1

   TO MARK A HOME PENDING: change its  status  to "Pending".
   TO REMOVE A HOME: delete its whole { ... } block.
   ══════════════════════════════════════════════════════════════════════════ */

/* --- who to contact — set ONCE, used by every home's page --- */
const CONTACT = {
  phone: "5513586625",                 // digits only, no spaces or dashes
  contactName: "Lonchando",            // shown in the small note under the buttons
  formspreeId: "xzdlakbq",             // Formspree form code (emails you each lead)
  makeWebhook: "https://hook.us2.make.com/h9jsckkipxxm4ngezfzldtflx4y2efo9",  // Make.com webhook → saves lead to Notion CRM
};

/* --- the homes --- */
const HOMES = [
  {
    id: "st-louis-1",                  // unique, lowercase, no spaces — used in the web address
    city:  "St. Louis",
    state: "MO",
    beds:  3,
    baths: 1,
    sqft:  1100,
    status: "Available",               // "Available"  or  "Pending"

    // the deal (what the buyer sees)
    monthlyPayment: 950,               // per month
    moveIn:         4000,              // move-in / deposit
    lockedPrice:    89900,             // locked purchase price
    termText:       "30-year owner financing (contract for deed)",

    // photos: paste image links OR filenames you upload to this same folder
    heroPhoto: "",                     // e.g. "st-louis-front.jpg"  (leave "" for placeholder)
    photos:    [],                     // e.g. ["kitchen.jpg","living.jpg","bed1.jpg","bath.jpg"]
  },
];
/* ▲▲▲ EDIT ABOVE — nothing below ▲▲▲ */
