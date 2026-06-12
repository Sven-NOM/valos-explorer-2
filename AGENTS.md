# AGENTS.md — ValOS Explorer

Context file for coding agents working on this repository. Read this fully before changing anything; the architecture is unusual (a build-time data pipeline feeding a single-file vanilla-JS SPA) and several constraints are deliberate.

## What this is

ValOS Explorer is an interactive companion to **ValOS — the Validator Operations Standard** (Lido Labs Foundation, Apache 2), a specification of risks, mitigations, and testable controls for blockchain node operators. The spec itself (`spec/valos-spec.html`) is a respec document and is **normative**; this explorer is a navigation and contribution aid built on top of it. It never modifies the spec.

The explorer serves four audiences in one artifact:

1. **Curious operators** — an Overview with a clickable "risk surface" grid and a Risks register showing, per risk, which mitigations and controls defend against it.
2. **Practitioners doing a deep dive** — Mitigations with full practice text, field tooling lists, and cross-links.
3. **Auditors / self-assessors** — Controls & Audit: every requirement as a checklist row with MUST/SHOULD level, SOC 2 / ISO 27001 / OWASP crosswalk chips, per-requirement status + evidence notes, progress bar, CSV export.
4. **Teams rolling the standard out** — Planner: controls as work items (owner, priority, target, status) with a per-category risk-coverage meter.

Plus a fifth, newer layer: **Community** — a local-only prototype of crowdsourced FMECA-style knowledge gathering (see below). The long-term vision is a GitHub-backed pipeline where community claims feed spec revisions; the current implementation is deliberately backend-free so the elicitation UX can be validated first.

## Repository layout

```
spec/valos-spec.html    INPUT — the ValOS spec (respec; markdown/HTML hybrid). Treat as read-only.
parse.py                Stage 1: spec HTML → data.json (structured model)
data.json               GENERATED intermediate. Never hand-edit; regenerate via parse.py.
template.html           The entire SPA: CSS + HTML shell + all JS. The data is injected
                        at the placeholder string "__DATA__".
build.py                Stage 2: post-processes data.json (cross-links, redirects, stats)
                        and injects it into template.html → dist/valos-explorer.html
dist/valos-explorer.html  OUTPUT — single self-contained file, ~280 KB. The only deliverable.
tests/test_views.py     Playwright smoke test: every route, search, assess, plan, exports, mobile.
tests/test_community.py Playwright test of the community layer end-to-end.
```

Build: `python3 parse.py && python3 build.py`. Test: `python3 tests/test_views.py && python3 tests/test_community.py` (needs `playwright` + chromium; tests print `errors: none` on success and drop screenshots into `tests/` for visual review — actually look at them when changing UI).

## Stage 1 — parse.py

The spec is markdown headings (`## Title {#sec-id}`) interleaved with raw HTML tables and divs, processed client-side by respec. The parser works line-wise on the raw file, splitting at the three top-level sections (Risks / Risk Mitigation Strategies / Controls Catalog) and walking `###`/`####` heading blocks **while tracking `<div class="info">` / `<details>` nesting depth** — headings inside info divs are labels, not new sections (this matters: several `####` lines in the spec live inside info divs and would otherwise split controls).

Extracted model (see data.json):

- `categories[]` — 8 risk categories (`FIN SLS DOW KEC HCK GIR SPS RER`), each `{id, code, name, intro}`.
- `risks[]` — 96 rows from the HTML tables, `{id, code, cat, status, group, vector, desc, replaces[], replacedBy[]}`. `status` is `active` (74), `replaced`, or `removed`. HCK risks consolidate older IDs ("HCK1 (replaces SLS8, KEC2, …)") — the parser splits code from the `replaces` list.
- `mitGroups[]` / `mitigations[]` (10 / 46) — `{id (sec-mit-*), name, group, body[], tools[], risks[], all}`. `body` is a list of typed blocks `{t:'p'|'h'|'b', x}` rendered by `prose()` in the template. `all:true` means the spec says it mitigates "all risks" (foundational practices).
- `ctlGroups[]` / `controls[]` (10 / 53, 64 requirements) — `{id (first req id), name, group, reqs[{id, text, level}], body[], externals[{fw, ref}], risks[], all}`. Requirements come from `<b id="req-*">` elements; one control can hold several. Info-only `####` blocks without a req id are merged into the preceding control.

Known parser quirks already handled — don't "fix" them away: one spec table row (`risk-hck-6`) is missing `</tr>`, so the row scanner also stops at `</tbody>`/`</table>`; external refs like `[[?SOC2]] CC 5.2` are parsed by regex; `[[?SSRF]]` / `[[?CRYPTOFAIL]]` / `[[?OWASP_ACCESS_CONTROL]]` are OWASP Top-10 item refs, mapped to the OWASP family **at runtime** by `fwFamily()` in the template, not in the parser.

If the spec gets updated: rerun `parse.py` and check its sanity output (`unknown refs: []` is the invariant; `retired refs used` is expected and resolved in stage 2).

## Stage 2 — build.py

Post-processing before injection:

- **Retired-risk redirects.** Mitigations/controls in the spec still reference retired codes (SLS9, DOW16, …). `resolve()` maps every retired code to its active replacement(s) via `replacedBy`, dedupes, and drops `removed` codes. After this, all `risks[]` lists contain only active codes.
- **Reverse links.** Each risk gets `mits[]`, `ctls[]`, `groupMits[]` (mitigation groups whose group-level info div lists the risk).
- **Related-by-overlap.** `mitigation.relatedCtls` / `control.relatedMits` = top 6 by risk-set intersection. This is a heuristic ("controls testing the same risks"), not a spec-defined link — keep it labeled as such in the UI.
- **stats** + foundational lists (`all:true` items).
- Injection: JSON is minified, `</` escaped to `<\/`, and substituted for the literal `"__DATA__"` in template.html.

## The SPA (template.html)

Zero frameworks, zero runtime dependencies except Google Fonts (with system fallbacks — the file must work fully offline). One `<script>` at the bottom of the body. Hash router: `#/overview`, `#/risks[/CODE]`, `#/mitigations[/sec-mit-*]`, `#/controls[/req-*]`, `#/planner`, `#/community[/sub]`. Each view is a `vXxx()` function that sets `app.innerHTML` from template literals and binds events afterwards. **Every interpolated string from data or user input goes through `esc()`** — maintain this religiously; user-typed community claims are rendered back into HTML.

Design system: CSS custom properties at `:root`. Each risk category has a hue pair `--c-XXX` (ink) / `--t-XXX` (tint), used consistently in chips, the risk fabric, list accents, heat map links. Type: Space Grotesk (display), IBM Plex Sans (body), IBM Plex Mono (all codes/IDs). The "coverage ticks" and category spectrum are the visual signature — reuse them rather than inventing new affordances. Quality floor that must survive any change: responsive to ~390 px, `:focus-visible` outlines, `prefers-reduced-motion` respected.

### Workspace state and persistence

Single mutable object: `ws = { assess, plan, community }`.

- `assess[reqId] = {status: ''|pass|partial|fail|na, note}`
- `plan[ctlId] = {status, owner, due, prio}` (priority auto-suggested from risk count on first access via `getPlan`)
- `community = { profile, claims[], hideSeed, showDrafts }`

Persistence is a **guarded localStorage adapter** (`loadWS`/`saveWS`, key `valos-explorer-ws-v2`): try/catch everywhere, falling back to in-memory with a visible "no persistent storage here — use Export" pill. This is deliberate — the file is also viewed in sandboxed iframes (e.g. claude.ai artifact preview) where storage APIs throw. **Never assume localStorage works; never remove the fallback or the Export/Import JSON path**, which round-trips the whole `ws` object and is the supported way to move data between machines. Mutations call `markDirty()`; a 1.5 s interval plus `beforeunload` flushes. If you add new mutable state, put it under `ws`, call `markDirty()`, and it ships in export/import for free.

## The Community layer (local crowdsourcing prototype)

Concept: knowledge is gathered as **small structured claims**, not documents. Claim objects live in `ws.community.claims[]` (user) and `SEED_CLAIMS` (demo crowd), discriminated by `type`:

| type       | shape (beyond `by`, `ts`, `seed?`/`mine?`)                                  |
|------------|------------------------------------------------------------------------------|
| `estimate` | `{risk, dim, value 0–4}` — anchored scale rating                              |
| `pairwise` | `{a, b, winner:'a'|'b'}` — likelihood comparison                              |
| `incident` | `{risk, year, setup, outcome, text}`                                          |
| `mitidea`  | `{risk, kind:'practice'|'counterexample', text}`                              |
| `tool`     | `{risk, name, url, verdict:'works'|'footgun', note}`                          |
| `newrisk`  | `{id:'CR-n', cat, group, vector, desc, status:'draft'}`                       |
| `crvote`   | `{target:'CR-n', v:'confirm'|'dup', dupOf?}`                                  |

Key mechanics, all in template.html (search for "COMMUNITY KNOWLEDGE LAYER"):

- **Dimensions** (`DIMS`): likelihood + four impact axes (financial, reputational, regulatory, network health) + detectability, FMECA-style. Every scale point has a concrete anchor string — never replace anchors with bare low/medium/high. `aggRisk(code)` returns per-dim medians, severity (max of the four impacts), and `rpn = (O+1)(S+1)(D+1)` ∈ 1–125.
- **Anti-anchoring**: crowd medians are revealed only *after* the user commits (`sessionShown` gate). Preserve this ordering in any redesign of the rate flow.
- **Profile gating**: estimates, incidents, ideas, submissions and queue votes require `profileComplete()`; pairwise voting deliberately does not (low-floor entry). The profile simulates GitHub login; a real backend would replace it with OAuth.
- **Pairwise → Elo**: `eloRanking()` replays all pairwise claims chronologically, K=32 from 1500. Recomputed on demand, cheap at this scale.
- **Duplicate detection** on new-risk submission: `similar()` does stopword-filtered token overlap (cosine-ish) against all active risks, threshold 0.13, top 3 shown live. A backend version would use embeddings; keep the function signature.
- **Draft lifecycle**: drafts get sequential `CR-n` IDs (`nextCrId()` scans both seed and user claims). 3 confirmations ⇒ "candidate for editors" styling. Drafts optionally overlay into the main Risks register (`ws.community.showDrafts`, dashed `draftrow` styling) — visually distinct from normative risks at all times.
- **Seeded demo crowd**: `buildSeed()` generates ~8 personas with category- and profile-biased estimates, ~170 pairwise votes, incidents, tool reports, and drafts CR-1..3. It is **deterministic** (FNV hash + mulberry32 PRNG, fixed `SEED_BASE_TS`) so reloads are stable — keep it deterministic if you touch it. Seeded claims carry `seed:true` and render a `demo` badge; user claims render `you`. The "Include demo community data" toggle filters seeds out of `allClaims()`, which is the single accessor every aggregate goes through — route any new aggregation through `allClaims()` and the toggle keeps working.

## Conventions and invariants

- The deliverable is **one self-contained HTML file**. No bundler, no npm, no fetches at runtime beyond fonts. If a change needs a library, it almost certainly shouldn't.
- Edit `template.html`, then rebuild. Never edit `dist/` or `data.json` by hand. (`community.css`/`community.js` from an earlier iteration were merged into template.html and no longer exist as files.)
- Risk/requirement IDs from the spec (`SLS1`, `req-segment-networks`, `sec-mit-*`) are stable public identifiers — never rename or reformat them.
- Spec text shown in the UI is parsed, not rewritten. Don't paraphrase spec content in the data pipeline; editorial framing belongs in the explorer's own copy.
- Keep the seed-data tone realistic but clearly fictional handles; never present demo data without its badge.
- After any UI change: rebuild, run both tests, and view the screenshots they produce (desktop + mobile) before considering the change done.

## Roadmap candidates (discussed with the owner, not yet built)

- Per-profile breakdowns of estimates ("solo stakers vs professionals rate this risk differently") — the conditional-risk view that is the real prize of profile tagging.
- GitHub backend: OAuth identity, claims as issue comments / a claims repo, candidate drafts opening issues on the spec repo, contributor acknowledgments on promotion.
- Time-boxed contribution campaigns (deliberately deferred to keep the core concept clean).
- Printable audit report view; gold-standard pairwise items and estimator track-record weighting for quality control.
