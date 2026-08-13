# Infinity Ads Compliance Audit

Audit an Android partner app against its own Infinity `ADS SCRIPTS` and working-file CSVs, then compare the implementation with the full `Example-AdLogic-Partner` ads base flow. The audit reads the app; it does not modify it.

## Audit scope

- App identity: package, app name, AdMob app id, Firebase project, and working-file service tokens.
- Ads config: every CSV key/id must exist in `ad_config.json` and `ad_config_debug.json`, match exactly, and declare `isEnable`.
- `GlobalApp`: `MobileAds.initialize` -> `DevConfig.init` -> `AdRemoteConfig.initializeFromAssets` -> `ERainAd.init`, DevConfig BuildConfig fields, Adjust/Facebook/TikTok/interval/resume id, AppOpen exclusions, lifecycle observer.
- `SplashActivity`: consent/RemoteConfig, `AdRemoteConfig` from `RemoteConfigUtils`, `inter_splash`, native language preload from `onAdLoaded`, `onNextAction` navigation, `open_resume`.
- `LanguageActivity`: DevSetting on `tvTitle`, 100ms delay, native language/click, onboarding page-1 preload, LiveData render/hide behavior.
- `OnBoardingActivity` and `OnboardingPageFragment`: native page 4/full/inter preload, uninstall widget gate, page LiveData mapping, final `showInterOnboarding` callback to Home.
- `ResumeAdsEntryRule`, `AppLifecycleObserver`, `WelcomeActivity`: open-resume vs Welcome mode, disabled screens, purchase/interstitial/UA gates, native/inter Welcome load/show.
- `AdsManager`: central native/inter/banner load-show, `isEnable`, purchase, network, `config.enableUaCheck`, null fallback, callback navigation.
- `BaseActivityWithBanner`: `BannerConfig`, `AdsManager.loadBanner`, purchase/config/container gates, and `reloadIntervalSeconds`.
- Unmapped placements remain `NEEDS_MAPPING`; user-event/lifecycle cases that static analysis cannot prove remain `NEEDS_RUNTIME_PROOF`.

## Install

Copy the `infinity-ads-compliance-audit` folder into the partner repository:

```text
partner-app/.agents/skills/infinity-ads-compliance-audit/
```

Use Python 3.10 or newer. No package installation is required.

## Easiest use: ask Codex

After copying the folder into the partner repository, open that repository in Codex and send:

```text
Use `infinity-ads-compliance-audit` to audit the current project.
Find the ADS SCRIPTS CSV and working-file CSV yourself. Do not change code.
Do not check app-ads.txt.
Return a short Vietnamese MKT report with app name, package name, errors to fix, items requiring technical confirmation, and passed checks.
```

Codex runs the bundled auditor; the partner does not need to use a terminal.

## Run by command (optional)

From the partner repository root:

```bash
python3 .agents/skills/infinity-ads-compliance-audit/scripts/run_audit.py \
  --project . \
  --ads-script "/path/to/ADS SCRIPTS.csv" \
  --working-file "/path/to/working file.csv"
```

Read the generated files in `ads-audit-output/`:

- `ads-audit-summary.md`: short fix list for the partner.
- `ads-audit-evidence.json`: short webhook payload for Infinity review or Discord delivery.

The command returns `0` without static failures, `2` when fixes are required, and `1` for invalid inputs.

## Package for partner repos

```bash
python3 infinity-ads-compliance-audit/scripts/package_skill.py \
  --skill-root infinity-ads-compliance-audit \
  --output infinity-ads-compliance-audit.zip
```

The zip excludes `__pycache__`, `.pyc`, and `ads-audit-output/` so the partner receives a clean skill package.

## Automatic Discord webhook

The bundled skill sends a short MKT report only when `--webhook-url` is passed, unless `--no-webhook` is passed. It includes app name, package name, counts, short errors, and items requiring technical confirmation. It also attaches `ads-audit-summary.md` so developers can open the full local report from Discord.

Each Discord error is rendered as separate lines:

```text
1. Error group title
Mô tả: short problem description
**Cách sửa:** concrete developer fix
```

Use `--no-webhook` only when Infinity requests a local-only audit.

## Override webhook (Infinity-approved only)

```bash
python3 .agents/skills/infinity-ads-compliance-audit/scripts/run_audit.py \
  --project . --ads-script "/path/to/ADS SCRIPTS.csv" \
  --working-file "/path/to/working file.csv" \
  --webhook-url "https://your-endpoint.example/audits"
```

Add `--webhook-token "$TOKEN"` only if the endpoint requires bearer authorization. The report redacts Adjust, Facebook client, and TikTok secret values.

The webhook payload contains `ten_app`, `package_name`, a short MKT-friendly error list, and items requiring technical confirmation. It does not check or send `app-ads.txt` information.

## When an app has a custom placement

The CSV is authoritative, so custom keys are allowed. If the tool returns `NEEDS_MAPPING`, copy `templates/ads-audit-overrides.yaml` into the app and add the approved class/call/event mapping. `NEEDS_RUNTIME_PROOF` means a tester must run the listed user journey; it is not a pass.

## Required screen architecture

Splash, Language, Onboarding, Home, and Welcome are primary ads-journey screens and must be separate `Activity` classes following the Infinity base. A single-`Activity` implementation that uses `Fragment`s for those screens is reported as an error. Small UI-only fragments within a compliant Activity screen are allowed.

## Codex use

Ask: `Use $infinity-ads-compliance-audit to audit this Android project with the supplied ADS SCRIPTS and working-file CSVs.`
