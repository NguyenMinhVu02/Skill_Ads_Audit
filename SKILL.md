---
name: infinity-ads-compliance-audit
description: Use when auditing an Android partner app's Infinity ads integration against project-specific ADS SCRIPTS and working-file CSVs, including AdMob IDs, package/tokens, Remote Config, Application-to-onboarding flow, placement logic, or webhook-ready compliance reports.
---

# Infinity Ads Compliance Audit

Treat the supplied CSVs as the app-specific contract. Treat the bundled base rules as the required integration architecture. Do not claim a placement passes without evidence.

## Run the audit

1. Confirm the partner project contains its `ADS SCRIPTS` CSV and working-file CSV. Never substitute base IDs.
2. Run the bundled auditor yourself from the partner project root. Resolve `scripts/run_audit.py` relative to the directory containing this `SKILL.md`; do not assume the skill lives under `.agents/skills`, because Codex and Claude Code use different skill locations. The Python runner auto-discovers one CSV of each kind, so the partner only needs to ask the AI host to check.

```bash
python3 "/absolute/path/to/this-skill/scripts/run_audit.py" \
  --project .
```

If discovery reports zero or multiple candidates, rerun with explicit `--ads-script` and `--working-file` paths. Explicit paths always override discovery.

CSV layouts may vary by partner. Prefer recognized aliases, including working-file pairs such as `Task Detail / Document`, `Content / Detail`, and `Field / Value`; otherwise use the bundled parser's guarded content inference. If the parser reports an ambiguous layout, stop and request a clearer header or explicit mapping. Never guess between tied columns.

If the skill directory cannot be resolved, use the published fallback from the project root instead:

```bash
npx -y github:NguyenMinhVu02/Skill_Ads_Audit audit --project .
```

3. Read `ads-audit-summary.md` and `ads-audit-evidence.json` in `ads-audit-output/`.
4. Read [base integration rules](references/base-integration-rules.md) and [placement mapping](references/placement-rule-map.yaml). Inspect every `FAIL`, `NEEDS_MAPPING`, and `NEEDS_RUNTIME_PROOF` against the code before reporting.

## Required review scope

Follow this route in order: `Application` → Splash → Language → Onboarding → Home/Banner → Resume/Welcome → configured post-onboarding screens. Check:

- `Application` initializes `MobileAds`, `DevConfig`, local `AdRemoteConfig`, and `ERainAd` in the prescribed order.
- `Application` declares DevConfig version `BuildConfig` fields, ERain environment, Adjust/Facebook/TikTok config, interstitial interval, AppOpen exclusions, lifecycle observer, and activity callbacks.
- Primary ads-journey screens use separate `Activity` classes. If Splash, Language, Onboarding, Home, or Welcome is implemented as a single-`Activity` navigation flow using screen `Fragment`s, return `ARCH_PRIMARY_SCREENS_ACTIVITY` as `FAIL` and require migration to the base Activity structure. Do not flag small UI-only fragments.
- Every CSV key/ID exists in release `ad_config.json` and matches exactly; debug/test IDs in `ad_config_debug.json` are not compared with the production contract.
- `SplashActivity` keeps consent/RemoteConfig loading, applies `AdRemoteConfig.initialize(this, RemoteConfigUtils.getAdRemoteConfig())`, loads `inter_splash`, preloads native language only from splash `onAdLoaded`, navigates only from `onNextAction`/fallback, and configures `open_resume`.
- `LanguageActivity` keeps DevSetting entry on `tvTitle`, 100ms preload, native language/click observers, onboarding page-1 preload, render/hide behavior, and correct next navigation.
- `OnBoardingActivity` keeps page setup, native page 4/full preload, `inter_onboarding` preload/show, widget gate, final callback navigation, and onboarding page LiveData rendering.
- `ResumeAdsEntryRule` and `AppLifecycleObserver` keep the open-resume vs Welcome decision, disabled-screen list, interstitial/purchase/UA gates, and Welcome routing.
- `WelcomeActivity` loads native/inter Welcome, observes native Welcome, renders/hides native ad, and shows inter Welcome from CTA with callback finish.
- `BaseActivityWithBanner` keeps `BannerConfig`, `AdsManager.loadBanner`, isEnable/purchase/container gates, and `reloadIntervalSeconds` reload behavior.
- Each mapped placement loads/shows through the central manager with enable, purchase, network, and required UA gates.
- Interstitial callbacks continue navigation only after close/fail and preserve the configured interval.
- For CSV key `inter_welcome_back`, require this complete chain: the registered resume observer checks `ResumeAdsEntryRule.shouldShowWelcomeOnResume()` and `getShouldDisplayInterWelcomeBack(config.enableUaCheck)`, routes to Welcome, then Welcome loads/shows through `AdsManager`. Require runtime proof that it does not duplicate an App Open ad.
- Every CSV placement that lacks an approved class/event mapping stays `NEEDS_MAPPING`; do not call it a failure or a pass.
- Every user-event requirement that static analysis cannot prove stays `NEEDS_RUNTIME_PROOF` and includes an executable test case.

## Pipeline checks

The auditor statically checks:

- identity/config: package, app name from default `res/values/strings.xml`, AdMob app id, Firebase project, required service tokens, and release `ad_config.json` (debug/test config is not used for contract ID equality);
- base architecture: `ARCH_GLOBAL_INIT_ORDER`, `ARCH_DEV_CONFIG_INIT`, `ARCH_DEV_CONFIG_BUILD_FIELDS`, `ARCH_ADS_CONFIG_FIELDS`, `ARCH_APP_OPEN_EXCLUSIONS`, `ARCH_ADS_MANAGER_*`, `ARCH_BANNER_BASE_RELOAD`;
- screen flow: `FLOW_SPLASH_*`, `FLOW_LANGUAGE_*`, `FLOW_ONBOARDING_*`, `FLOW_RESUME_RULE`, `FLOW_WELCOME_NATIVE_AND_INTER`, `FLOW_INTER_WELCOME_BACK_*`;
- placement mapping: configured CSV placements mapped to approved class/method evidence;
- runtime proof: user-event and lifecycle cases static source cannot prove.

## Exceptions and new placements

For a class name, user event, or placement not inferable from CSV text, copy `templates/ads-audit-overrides.yaml` into the partner project and add an Infinity-approved mapping. Preserve the CSV key and ID exactly. A new key may differ from the base project; its architecture must still follow the base pattern.

## Webhook

After local report generation, the bundled Discord webhook receives the MKT payload and `ads-audit-summary.md` attachment automatically. Use `--no-webhook` only when the partner explicitly asks for a local-only audit. `--webhook-url` overrides the embedded endpoint when Infinity authorizes another destination. Do not paste tokens into reports or chat. The payload follows [report schema](references/report-schema.json), includes `ten_app` and `package_name`, and gives MKT a short Vietnamese error list without secrets or `app-ads.txt` checks. In Discord, each error must render compactly: title immediately followed by bold `**Mô tả:**` with no blank line, plain-language details about the exact broken flow, then bold `**Cách sửa:**` on its own line with concrete developer actions. If the report is too long for one Discord message, split it into multiple messages named `Ads Audit chi tiết (2/N)`, `Ads Audit chi tiết (3/N)`, etc.; attach `ads-audit-summary.md` only to the first message.

## Partner-facing result format

Return this short format, in the partner's requested language:

```text
Result: BLOCKED | REVIEW_REQUIRED

BLOCKER / ERROR
- [rule] file:line — observed problem. Fix: concrete change.

NEEDS MAPPING / RUNTIME PROOF
- [rule] why static evidence is insufficient. Next proof: exact action and expected result.

Passed: N static checks.
```

Never output raw Adjust, Facebook client, TikTok, webhook, or other secret values.
