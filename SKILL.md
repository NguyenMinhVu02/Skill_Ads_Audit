---
name: infinity-ads-compliance-audit
description: Use when auditing an Android partner app's Infinity ads integration against the base project and the app's own ADS SCRIPTS and working checklist, including AdMob IDs, package/tokens, Remote Config, Application init order, preload/load/show flow, Activity-vs-Fragment screen structure, or webhook-ready compliance reports. Accepts local CSVs or Google Sheets/Docs links.
---

# Infinity Ads Compliance Audit

Audit an Android app against the Infinity ads base. The two supplied documents
are the app-specific contract; the bundled references are the required
architecture. Never claim a placement passes without evidence in the code.

The audit reads the project. It never modifies app source.

## Inputs

Two documents, each either a local file or a Google Sheets/Docs share link:

| Document | Carries |
| --- | --- |
| **ADS SCRIPTS** | placement key, ad type, ad-unit ID, AdMob APP ID |
| **working checklist** | app name, package, Firebase project, Adjust/Facebook/TikTok tokens |

If either is missing, ask the partner for it. Never substitute base IDs.

## Run the audit

Resolve `scripts/run_audit.py` relative to the directory holding this
`SKILL.md`. Skill locations differ per host — Claude Code
(`~/.claude/skills`), Codex (`~/.agents/skills`), Antigravity
(`~/.gemini/antigravity/skills`) — so never assume a fixed path.

Run it yourself from the app root. Do not ask the partner to type commands.

```bash
python3 "/absolute/path/to/this-skill/scripts/run_audit.py" --project .
```

Both documents are auto-discovered from CSV files in the project. Pass them
explicitly when discovery finds zero or several candidates, or when the partner
gives you links:

```bash
python3 "/absolute/path/to/this-skill/scripts/run_audit.py" --project . \
  --ads-script   "https://docs.google.com/spreadsheets/d/<id>/edit#gid=0" \
  --working-file "https://docs.google.com/document/d/<id>/edit"
```

Links must be shared as anyone-with-the-link viewer. A sign-in page comes back
as a sharing error, not as data. Explicit values always override discovery.

CSV layouts vary by partner. The parser prefers known aliases (`Task Detail /
Document`, `Content / Detail`, `Field / Value`, and Vietnamese equivalents),
then falls back to guarded content inference. If it reports an ambiguous
layout, stop and ask for a clearer header — never guess between tied columns.

Then read `ads-audit-output/ads-audit-summary.md` and
`ads-audit-evidence.json`, and check every `FAIL`, `NEEDS_MAPPING`, and
`NEEDS_RUNTIME_PROOF` against the actual code before reporting.

## Reference material

- [base code reference](references/base-code-reference.md) — the real base
  implementation: Gradle setup, `GlobalApp`, `AdsManager`, every screen, gates,
  `ad_config.json` schema. Read this before judging whether code is correct.
- [base integration rules](references/base-integration-rules.md) — the rules in
  checklist form.
- [placement mapping](references/placement-rule-map.yaml) — approved class and
  call evidence per placement.

## Required review scope

Follow the journey in order: `Application` → Splash → Language → Onboarding →
Home/Banner → Resume/Welcome.

**Initialization.** `GlobalApp.onCreate` runs `MobileAds.initialize` →
`DevConfig.init` → `AdRemoteConfig.initializeFromAssets` → `ERainAd.init`, in
that order. `DevConfig.init` receives the three `BuildConfig` version fields
(the parameter is named `nkhStudioVersion` but takes `ERAIN_STUDIO_VERSION`).
`initAds` sets environment, `AdjustConfig`, `facebookClientToken`,
`adjustTokenTiktok`, `intervalInterstitialAd = 35`, `idAdResume`, the AppOpen
exclusions, the lifecycle observer, and the activity callbacks. Secrets come
from string resources, never inline literals.

**Screen structure.** Splash, Language, Onboarding, Home, and Welcome must be
separate `Activity` classes. If any of them is a `Fragment` inside a
single-Activity navigation graph, report `ARCH_PRIMARY_SCREENS_ACTIVITY` as
`FAIL` and require migration. A `Fragment` used as a *page inside* one of those
Activities — `OnboardingPageFragment` in a `ViewPager2` — is correct base
structure, not a violation.

**Config.** Every CSV key/ID exists in release `ad_config.json` and matches
exactly. `ad_config_debug.json` is deliberately different and is never compared
with the production contract. The AdMob app id comes from the **release**
`manifestPlaceholders`; the debug block legitimately holds Google's test id.

**Preload.** Splash preloads the Language native only from the splash
interstitial's `onAdLoaded`. Language preloads onboarding page 1 after its 100 ms
`postDelayed`. Onboarding preloads native page 4, native full, and
`inter_onboarding` after its own 100 ms delay. Moving a preload earlier or later
changes fill rate and is a finding.

**Load.** Every native load goes through the central `AdsManager` helper with
all four gates: `isEnable`, purchase, network, and the placement's
`getShouldDisplay*(config.enableUaCheck)`. On any refusal or failure the
LiveData is set to `null` so the container hides. `getShouldDisplayInterWelcomeBack`
lives in `AppLifecycleObserver`, not in `AdsManager`.

**Show.** Interstitials continue navigation only through the close/fail
callback, and the show path always has an `else { onAction() }` so the user
still advances when no ad is ready. The configured interval stays at 35 s.

**Render.** Natives observe a `LiveData`, call `populateNativeAdView` when
non-null, and hide the container when null or offline. Fragments observe with
`viewLifecycleOwner`. Language swaps between its two observers with
`removeObservers` so both are never active at once.

**Resume/Welcome.** `ResumeAdsEntryRule` picks App Open or Welcome and they are
mutually exclusive — `open_resume` wins when enabled — so an App Open ad and a
Welcome interstitial never stack. `AppLifecycleObserver` applies the disabled-screen
list, interstitial, purchase, and UA gates before routing to Welcome. Note the
two exclusion lists differ: AppOpen excludes Splash/Language/OnBoarding/ConfirmUninstall;
Welcome routing excludes Splash/Language/OnBoarding/Welcome/Survey.

**Banner.** `BaseActivityWithBanner` gates on `isEnable`, purchase, and the
`fr_banner` container, honours `reloadIntervalSeconds`, and tears down its
handler in `onPause`/`onDestroy`.

**Unresolved items.** A CSV placement with no approved class/event mapping stays
`NEEDS_MAPPING` — neither pass nor failure. A user-event or lifecycle claim
static analysis cannot settle stays `NEEDS_RUNTIME_PROOF` and must carry an
executable test case.

## Exceptions and new placements

For a class, event, or placement not inferable from the CSV, copy
`templates/ads-audit-overrides.yaml` into the app and add an Infinity-approved
mapping. Preserve the CSV key and ID exactly. A new key may differ from the base
project, but its architecture must still follow the base pattern.

## Webhook

After the local report is written, the bundled Discord webhook receives the MKT
payload and `ads-audit-summary.md`. Use `--no-webhook` only when the partner
asks for a local-only audit. `--webhook-url`, or `ADS_AUDIT_WEBHOOK_URL` /
`DISCORD_WEBHOOK_URL`, override the embedded endpoint when Infinity authorises
another destination.

The payload follows [report schema](references/report-schema.json), carries
`ten_app` and `package_name`, and gives MKT a short Vietnamese error list with
no secrets and no `app-ads.txt` checks. Each Discord error renders compactly:
title, then bold `**Mô tả:**` with no blank line, plain-language detail about the
broken flow, then bold `**Cách sửa:**` on its own line with concrete developer
actions. If the report exceeds one message, split into `Ads Audit chi tiết
(2/N)`, `(3/N)`, and attach the summary to the first message only.

## Partner-facing result format

Reply in the partner's language, in this shape:

```text
Result: BLOCKED | REVIEW_REQUIRED

BLOCKER / ERROR
- [rule] file:line — observed problem. Fix: concrete change.

NEEDS MAPPING / RUNTIME PROOF
- [rule] why static evidence is insufficient. Next proof: exact action and expected result.

Passed: N static checks.
```

Never output raw Adjust, Facebook client, TikTok, webhook, or other secret values.
