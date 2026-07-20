# Lonchando Media Network — Architecture v1

**Status:** DRAFT — awaiting Joe's Phase 3 approval. Nothing in here is built.
**Architect:** Claude (Fable) · **Implementers:** Sonnet/Haiku per §7 handoff spec
**Date:** 2026-07-20

---

## 0. Assumptions and escalations

Answers I never received (interactive Q&A failed twice); the design assumes the following. **If any is wrong, sections marked with its tag must be re-run.**

| Tag | Assumption | If wrong |
|---|---|---|
| A1 | No RMLO currently used for owner-occupant CFD sales | If an RMLO is in place, Phase 0 shortens by ~3 weeks and §6 risk #2 drops two ranks |
| A2 | ~$200–300K deployable for acquisitions post-refi (7–10 houses @ ~$30K) | Under $150K: cut self-funded target to 4, move lender funnel to Phase 1; over $300K: raise Phase 1 acquisition gate |
| A3 | Media opex ≤ $1,000/mo | More budget mainly buys a part-time editor and paid boosts; timeline compresses ~2 months per tier |
| A4 | Joe performs 2–3 hrs/week on camera/mic; audience ≈ 0; no episodes shipped | Under 2 hrs: Ramona becomes primary face and lender-funnel projections in §1 drop ~40% |

**Discovered from the repo (not assumed):** getownerfinancedhomes.com is live with **162 listings** sourced from a third-party master list (community inventory), lead capture via Formspree → Make.com webhook, and a buyer-facing video script already written. The buyer funnel exists today.

**Decisions that must escalate to Joe before build (D-flags, referenced throughout):**
- **D1 — Placement-fee structure.** Placing tenant-buyers into *other operators'* homes for a fee is brokerage activity. Joe is licensed in **NJ only**; collecting per-placement fees on IL/MO/MI property without an in-state license is illegal in those states. Options: take principal positions (option/assignment) on each home before marketing it, refer through an in-state licensed broker for a compliant referral fee, or get licensed in 1–2 core states. **Pick one with counsel. Until then, revenue line M2 is modeled but frozen.**
- **D2 — Make.com vs n8n.** Lead capture currently runs on Make. Either migrate to n8n (one-time cost, one system) or bridge Make→n8n webhook (faster, two systems to break). Spec assumes **migrate**.
- **D3 — Site copy remediation.** "No bank, no credit check" and "$X locked price" claims to owner-occupants must be rewritten per RMLO/counsel guidance. This edits the live site — Joe approves the new copy.
- **D4 — Securities counsel engagement** (§6 risk #1). One flat-fee engagement (~$3–5K) producing: (a) opinion letter on the one-lender/one-note/first-lien structure, (b) an approved-language rulebook for all lending-adjacent content. **No lending content ships before this exists.** "Finding the right words ourselves" is explicitly rejected.

---

## 1. The number, honestly

**$100K/month across all sources is achievable at ~month 48–54, not month 36.** The binding constraint is not content, audience, or AI — it is **lender capital velocity**: every $30K note added produces ~$500/mo of spread, so $70K/mo of note income requires ~140 performing notes ≈ **$4.2M of deployed lender capital** plus real servicing infrastructure. Media accelerates lender acquisition and buyer placement; it cannot compress capital recycling.

**Largest defensible number at month 36: ~$50–58K/month.** The roadmap (§5) gates every phase so you find out cheaply if even that is wrong.

### 1.1 Unit economics (model deal, calibrated to actual homes.js data)

| Item | Value | Source |
|---|---|---|
| Acquisition all-in | $30,000 | Joe's stated range; Jelinek buy-box |
| CFD sale price | $80,000 | homes.js median locked price $69.5–99K |
| Move-in / down | $2,750 | homes.js range $2,250–3,000 |
| Monthly payment (P&I, buyer pays T&I) | $850 | homes.js range $785–1,050 |
| Servicing cost | $25/mo/note | licensed servicer, required at scale |
| Default/turnover haircut | 15% of gross | conservative; defaults re-sell with a new down payment |
| **Net/mo, self-funded** | **≈ $700** | 850×0.85 − 25 |
| Lender coupon ($30K @ 8% interest-only, 1st lien) | $200/mo | Joe's stated structure |
| **Net/mo, lender-funded** | **≈ $500** | 700 − 200 |

### 1.2 The arithmetic to $100K/month (steady state, ~month 48)

| # | Mechanism | Unit econ | Volume | $/month |
|---|---|---|---|---|
| M1 | Note spread (10 self-funded @ $700 + 130 lender-funded @ $500) | above | 140 performing notes | **$72,000** |
| M2 | Tenant-buyer placements into community inventory *(frozen on D1)* | $2,000/placement | 6/mo | **$12,000** |
| M3 | Down payments on own sales (incl. re-sales after default) | $2,750/sale | 3/mo | **$8,250** |
| M4 | NJ commissions from bilingual JC content (KW) | $9,000 net/side | 1/mo | **$9,000** |
| M5 | B2B sponsorship (SDIRA custodians, title, servicers, insurance) | $1–2K/slot | 2 slots | **$3,000** |
| | **Total** | | | **$104,250** |

**What must be true:** ~$4.2M lender capital deployed across ~140 notes · sustained acquisitions of 3/mo from month 6 · 9 total buyer placements/mo (own + community) · annual default rate ≤ 12% with re-placement inside 60 days · D1 resolved in a fee-legal structure. **If lender capital stalls at $1.5M, the honest ceiling is ~$45–50K/mo. Do not pad M2/M5 to cover a capital shortfall — the fix is always more lenders, not more content.**

### 1.3 Monetization stack — full ranking with kill list

Ranked by expected annual contribution at maturity; $/qualified-lead governs, per the brief.

1. **M1 Note spread** — check written by: tenant-buyer monthly payment (lender's coupon comes out first). $/lead: a converted lender lead is worth ~$6K/yr recurring per note funded, for years. AI-scalable except trust-building (human-capped at Joe's face). Fragility: securities recharacterization, servicing blowup, capital drought. Time-to-first-dollar: month 3–4 (first self-funded note payment).
2. **M2 Placement fees** — check: community operator whose house you filled. $/lead: ~$2,000 per converted buyer. Fastest first dollar (**weeks** — funnel and inventory already live). Fragility: D1 licensing, inventory relationship is borrowed not owned, adverse selection on what operators list. Fully AI-scalable except final buyer interview.
3. **M3 Down payments** — check: tenant-buyer at signing. Partially return-of-capital; counted as income because defaults regenerate it. Rides M1's volume; no separate funnel.
4. **M4 NJ commissions** — check: closing settlement. Highest $/lead of anything here (~$9K/lead converted); capped by Joe's NJ hours, so it stays a byproduct lane of the ES show, never a show of its own.
5. **M5 Sponsorship** — check: sponsor AP dept. Needs ~10K engaged niche audience first; month 18+ pilot. Fragility: audience concentration, FTC disclosure hygiene.
6. **Note sales / partials** — not an income line; a **capital velocity tool** (sell a partial to recycle $25–30K into the next house). Modeled in the roadmap, not the P&L.
7. **KILLED — Data products** (deal-pipeline market intel): the paying audience (note investors, operators) is too thin until you have 100+ notes of proprietary data. Revisit month 24. **KILLED — Affiliate/programmatic**: pennies per lead, violates constraint 5. **KILLED — Faceless YouTube**: commodity content with zero deal artifacts = no moat. **KILLED — Licensing the content engine**: it is selling a system to aspiring operators — smells like the prohibited category, and it's premature by years.

---

## 2. Show portfolio — 2 shows + 1 clip engine, nothing else

| Show | Lang / surface / cadence | Anchor | Single business function | Kill criterion (pre-committed) | Review |
|---|---|---|---|---|---|
| **Case Files** | EN · YouTube + audio podcast · weekly, batch-recorded 2 eps/session | Joe | Private-lender credibility → **booked 1:1 lender conversations**. Real deals, real numbers, real documents on screen. **Never a public money ask** (§6 risk #1) | < 8 qualified lender conversations per quarter, measured from month 6 (two full quarters of data) | Month 9 |
| **Casa Propia** | ES · Facebook + TikTok + YT Shorts · weekly | Ramona (Joe monthly guest) | **Tenant-buyer waitlist** feeding the 162-listing site + ABHS's own homes; byproduct lane: JC bilingual buyer/seller leads → M4 | < 25 waitlist signups per quarter from month 6 | Month 9 |
| **Seller Finance Daily** | EN+ES shorts, all surfaces, daily | AI-assembled (Foundry) | Not a show — the **clip engine**: daily cuts from the two shows above. Exists only to feed their funnels | Cut automatically if a parent show dies | with parents |

Cut from the concept list: standalone faceless channels, a third show of any kind before month 12. Jaslene contributes performer energy to Casa Propia shorts (minor — parental consent, no employment-hour commitments assumed). The existing "Your Own Front Door" script becomes Casa Propia episode 1 after D3 copy remediation.

**Why this portfolio survives commoditization:** every episode is built from artifacts competitors cannot fabricate — actual contracts, actual payment ledgers, actual addresses (redacted as needed). That is the moat; guard it by never shipping an episode without a real artifact in it.

---

## 3. Agent architecture

Runtime: n8n + Claude API on the Mac Mini, workspace `lonchando-agents`. Monthly API cost at target volume: **~$120–200**. Every agent writes to the central event log (§4); every agent has a weekly heartbeat — a missed heartbeat pages Joe, because the default failure mode of automation is *silence*.

| Agent | Model | Single responsibility | Inputs → outputs | Trigger | Human in loop | Silent-failure guard | Cost |
|---|---|---|---|---|---|---|---|
| **Victor Reyes** (underwriter, existing CFO persona) | Sonnet — judgment on messy deal data justifies mid-tier | Score every candidate deal against the buy-box; output PASS/FAIL memo with numbers | Deal submissions (community lists, seller leads) → underwriting memo | New deal in intake sheet | **Joe signs every acquisition** — capital commitment is never delegated | Weekly count of memos vs intake rows; mismatch alerts | ~$0.10/run × 60/mo ≈ $6 |
| **Cadence** (follow-up owner) | Sonnet drafts, Haiku classifies | Own ALL follow-up: lender leads, buyer waitlist, seller leads, agent referrals. This is the system that replaces Joe's bottom-five Empathy/Harmony — **no human is the follow-up owner, ever** | New lead / 7-day no-touch → drafted email-SMS queued for one-tap approval | n8n schedule + webhook | Joe approves the daily queue, ~15 min/day. Not optional: unapproved queue >48h old pages him | Daily queue-depth metric; >20 stale items = red on dashboard | ~$40/mo |
| **Foundry** (content factory) | Sonnet scripts, Haiku clips/captions | Transcript → episode notes, 5–7 short scripts, captions EN+ES, titles, publish schedule | Recording transcript → publish-ready package | New file in Drive /recordings | Kelvin edits video; Ismael publishes and closes the loop in the event log | Package must exist ≤ 24h after transcript; else alert | ~$30/mo |
| **Compass** (compliance gate) | Sonnet — false negatives are expensive | Check every outbound script/caption/site edit against the counsel rulebook (D4): no public money asks, no "no credit check"-class claims, required disclosures present | Draft content → PASS / BLOCK + cited rule | Pre-publish hook (blocking) | Attorney writes the rulebook once; **Joe cannot override a BLOCK without a logged reason** — the log exists because low-Deliberative operators override gates on deadline | Publish pipeline hard-fails without a Compass PASS token | ~$15/mo |
| **Concierge-ES** (buyer intake) | Haiku, Sonnet escalation | Qualify waitlist buyers bilingually: income-doc checklist, budget fit, RMLO handoff packet | Form/webhook submissions → qualified-buyer packet or polite decline | Site form (post-D2 migration) | RMLO does ability-to-repay; a human (Ismael) does the final phone screen | Response-time SLA 4h business hours; breaches logged | ~$20/mo |
| **Ledger** (analytics) | Haiku — pure compilation | Compile the weekly 7-number dashboard (§4) from the event log + platform APIs | Event log, YouTube/Meta APIs → Monday 7am email | Cron, Mondays | None — read-only | Missing Monday email is itself the alert | ~$5/mo |

**Seat map:** Joe — record, approve Cadence queue, sign deals, lender 1:1s (total ≈ 5 hrs/wk). Ismael (operator track) — publishes for Foundry, phone-screens for Concierge-ES, owns event-log hygiene, is the human servicer-liaison; this seat is the real operator apprenticeship. Kelvin — feeds Foundry (edits). Ramona — records Casa Propia. Jaslene — occasional shorts, zero critical path. **Nothing on the critical path depends on bench availability except Ismael's publishing seat, which Foundry can degrade to auto-publish (lower quality) if he's out.**

---

## 4. Measurement layer

**Spine:** every public link carries UTM → site/forms POST to n8n webhook → one append-only `events` table. Start in Google Sheets (already the pattern), migrate to Postgres on the Mac Mini at month 6 or 10K rows, whichever first. Entities: `lead` (id, created_at, source_utm, channel, type ∈ {lender, buyer, seller, agent_client}, status, last_touch), `deal` (id, address, state, buy_price, funding ∈ {self, lender}, lender_id, sell_price, down, rate, pmt, status), `note` (deal_id, start, status ∈ {performing, late, default, paid_off}, mtd_collected), `event` (ts, lead_id/deal_id, kind, meta).

**Attribution, honestly:** buyer and seller leads are genuinely attributable (last non-direct UTM + a mandatory "how did you hear about us" field; expect ~80% coverage). **Lender capital is not cleanly attributable** — it converts over months of touches and referrals. We log first-touch and every touch, and report "content-influenced" capital as a range, never a point estimate. Any dashboard claiming per-video ROI on lender money is lying to you.

**The weekly seven** (Ledger's Monday email — these and nothing else):
1. Qualified lender conversations booked (this week / trailing 4)
2. Lender capital committed, cumulative
3. Buyer waitlist adds by channel
4. Placements + own sales closed (M2 + M3)
5. Performing notes and monthly spread (M1)
6. Deals in pipeline passing Victor's buy-box
7. $ per qualified lead, by channel (paid channels only)

**Pre-committed thresholds:** show kill criteria per §2 · **scale trigger:** any channel with $/qualified-lead < $30 for 4 consecutive weeks gets the paid-boost budget · **freeze trigger:** default rate > 12% annualized or >3 notes 60+ days late → acquisitions pause until servicing is fixed (this is the gate a low-Deliberative operator most needs and will most resent).

---

## 5. Roadmap — five phases, hard gates

| Phase | Months | Work | Spend | **Gate to next phase (all must be green)** |
|---|---|---|---|---|
| **0 — Legal + plumbing** | 1–2 | D4 attorney letter + rulebook; RMLO engaged (A1); D1 placement structure chosen; D3 site copy fixed; D2 migration; event spine live; refi closes; buy first 2 houses | ≤ $6K one-time + $500/mo | Attorney letter in hand · RMLO live · D1 resolved · tracking captures a test lead end-to-end · 2 houses owned |
| **1 — First dollars** | 3–6 | Casa Propia + Case Files launch; clip engine on; 5–8 self-funded houses total; 25 lender 1:1s from warm network + content | ≤ $1K/mo | ≥ 6 buyer placements cumulative · ≥ 3 lenders committed ≥ $90K total · ≥ 8 qualified lender convos in Q2 · $/lead known per channel |
| **2 — Lender flywheel** | 7–12 | Lender-funded acquisitions 2/mo; licensed servicer onboarded by note #15; waitlist ≥ 150 | ≤ $1.5K/mo | ≥ 20 performing notes · ≥ $500K lender capital · combined income ≥ $15K/mo · default < 10% |
| **3 — Scale the boring machine** | 13–24 | 3 acquisitions/mo; 6 placements/mo; sponsorship pilot; M4 lane active | ≤ $3K/mo | ≥ 60 notes · ≥ $1.8M capital · **≥ $35K/mo combined** |
| **4 — Grind to the number** | 25–48+ | Sustain 3/mo; partials recycle capital; second servicer redundancy | self-funding | **$100K/mo at ~month 48–54.** If capital plateaus, the honest number is §1.2's ceiling — report it, don't force it |

Phase 1 is deliberately small enough to be wrong for under $10K and six months. **No phase may borrow its gate metric from the next phase's projections.**

---

## 6. Risk register — ranked by expected damage

1. **Securities recharacterization.** Public content + soliciting note investors = general solicitation; *Reves* presumes notes are securities. **Mitigation:** content never asks for money — asks happen 1:1 with documented pre-existing relationship; D4 letter + Compass gate enforce it. *Damage if ignored: rescission, state enforcement, the whole lender funnel dies.*
2. **Dodd-Frank / SAFE Act / state CFD law on owner-occupant sales.** "No bank, no credit check" is live on the site today (exhibit A in someone else's lawsuit). IL additionally regulates installment contracts (recording, disclosure). **Mitigation:** RMLO on every occupant sale, D3 rewrite, state-specific counsel for IL/MO.
3. **Unlicensed brokerage on placement fees (D1).** Second-fastest revenue line is frozen until structured legally.
4. **Servicing/default blowup at scale.** 140 notes is a servicing business. **Mitigation:** licensed servicer at note #15, the §4 freeze trigger, re-placement SLA of 60 days.
5. **Borrowed inventory / adverse selection.** The 162 listings belong to someone else's master list; the relationship can vanish, and operators list their *worst* houses first. **Mitigation:** Victor scores community deals with the same buy-box as strangers' deals; build own inventory share every quarter. Buying colleagues' homes *on terms* also breaks the one-lender/first-lien structure (the colleague holds the lien) — those deals use refi cash only.
6. **Lender concentration + SDIRA custodian friction.** Three lenders ≠ a funnel. Track lender count, not just dollars.
7. **Key-person: Joe's face is the trust asset.** Mitigation is partial at best: Ramona as second face, everything documented, notes keep paying if content stops.
8. **Platform dependency.** FB/TikTok/YouTube can zero any channel overnight; the owned assets are the email/SMS list and the site. Every funnel must end in owned contact info.
9. **AI content commoditization.** Real-artifact moat (§2). If an episode could have been made by someone with no deals, don't ship it.
10. **The failures Joe won't see coming (low Deliberative, high Self-Assurance):** signing acquisition #12 while servicing is failing on #8 · overriding a Compass BLOCK on deadline · launching show #3 in a motivated week · letting the Cadence queue rot because approval is boring · treating the month-36 $50K as failure and swinging for a home run that breaks constraint 4. **The gates in §4–5 exist specifically for these; the log of overrides is the tell.**

---

## 7. Handoff spec (for Sonnet/Haiku — zero architectural judgment required)

**Repo:** `lonchando-agents` (separate from this public site repo — agents, prompts, and business data never live in a public Pages repo).

```
lonchando-agents/
  agents/{victor,cadence,foundry,compass,concierge_es,ledger}/
    prompt.md          # system prompt, versioned
    config.yaml        # model id, max_tokens, temperature, tools
    tests/cases.yaml   # acceptance cases below
  workflows/           # n8n exports, one JSON per trigger
  schemas/{lead,deal,note,event}.schema.json   # per §4 field lists
  rulebook/compliance.md   # D4 output — attorney-owned, PR-only changes
  dashboards/weekly.md.tmpl
  .env.example         # ANTHROPIC_API_KEY, N8N_WEBHOOK_*, YT_API_KEY, META_TOKEN, SHEETS_ID — secrets in macOS Keychain, never committed
```

**Build order and acceptance criteria:**
1. **Event spine** — n8n webhook → Sheets `events`; test: UTM'd form submission appears as `lead` + `event` rows with source intact; a malformed POST is logged to `events_dead_letter`, not dropped.
2. **Cadence** — test: new lender lead generates a draft within 1h; 7-day stale lead generates exactly one follow-up draft (idempotent — re-runs must not double-send); nothing sends without an approval token.
3. **Victor** — test: golden-file deals (3 PASS, 3 FAIL from the buy-box in `agents/victor/prompt.md`) score correctly; missing data yields "INSUFFICIENT DATA," never a guess.
4. **Compass** — test: the current site's "no bank, no credit check" sentence must BLOCK, citing the rule; the D4-approved phrasing must PASS; ambiguity → BLOCK (fail closed).
5. **Foundry** — test: 40-min transcript → ≥5 short scripts + EN/ES captions + notes in ≤24h; every output carries the source-episode id for attribution.
6. **Concierge-ES** — test: Spanish-language inquiry receives a Spanish reply with doc checklist ≤4h; income below payment threshold routes to decline template, never to RMLO.
7. **Ledger** — test: Monday email renders all 7 numbers; any unavailable number renders "MISSING (source)" — never a stale or interpolated value.

**Escalate to Joe, always:** any D1–D4 item · any change to `rulebook/compliance.md` · any public CTA wording · buy-box changes · any new platform, show, or spend > $500 · any agent gaining send-without-approval capability.

---

*End of architecture. Per Phase 3: nothing gets built until Joe approves or revises this document.*
