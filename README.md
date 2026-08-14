# Infinity Ads Compliance Audit

Audit an Android partner app against its own Infinity `ADS SCRIPTS` and working-file CSVs, then compare the implementation with the full `Example-AdLogic-Partner` ads base flow. The audit reads the app; it does not modify it.

## Audit scope

- App identity: package, app name, AdMob app id, Firebase project, and working-file service tokens. The app name is read from the default `res/values/strings.xml`; translated locale files do not override it.
- Ads config: every CSV key/id is checked against the release `ad_config.json`, must match exactly, and must declare `isEnable`. Debug/test IDs in `ad_config_debug.json` are intentionally not compared with the production contract.
- `GlobalApp`: `MobileAds.initialize` -> `DevConfig.init` -> `AdRemoteConfig.initializeFromAssets` -> `ERainAd.init`, DevConfig BuildConfig fields, Adjust/Facebook/TikTok/interval/resume id, AppOpen exclusions, lifecycle observer.
- `SplashActivity`: consent/RemoteConfig, `AdRemoteConfig` from `RemoteConfigUtils`, `inter_splash`, native language preload from `onAdLoaded`, `onNextAction` navigation, `open_resume`.
- `LanguageActivity`: DevSetting on `tvTitle`, 100ms delay, native language/click, onboarding page-1 preload, LiveData render/hide behavior.
- `OnBoardingActivity` and `OnboardingPageFragment`: native page 4/full/inter preload, uninstall widget gate, page LiveData mapping, final `showInterOnboarding` callback to Home.
- `ResumeAdsEntryRule`, `AppLifecycleObserver`, `WelcomeActivity`: open-resume vs Welcome mode, disabled screens, purchase/interstitial/UA gates, native/inter Welcome load/show.
- `AdsManager`: central native/inter/banner load-show, `isEnable`, purchase, network, `config.enableUaCheck`, null fallback, callback navigation.
- `BaseActivityWithBanner`: `BannerConfig`, `AdsManager.loadBanner`, purchase/config/container gates, and `reloadIntervalSeconds`.
- Unmapped placements remain `NEEDS_MAPPING`; user-event/lifecycle cases that static analysis cannot prove remain `NEEDS_RUNTIME_PROOF`.

## Fastest partner workflow: run with npx

From the root of the Android project, run:

```bash
npx -y github:NguyenMinhVu02/Skill_Ads_Audit audit \
  --project . \
  --no-webhook
```

The CLI searches the project for exactly one CSV whose name contains `ADS SCRIPTS` and exactly one CSV whose name contains `working` or `work file`. It never guesses when there are zero or multiple matches.

Requirements:

- Node.js 18 or newer (provides `npx`).
- Python 3.10 or newer.
- The Android project and its two app-specific CSV files.

### Partner CSV formats

The auditor does not require every partner to use the same spreadsheet layout. For the `ADS SCRIPTS` file it automatically handles:

- comma, semicolon, tab, or pipe delimiters;
- English or Vietnamese column labels, with different capitalization and spacing;
- a few title/export rows before the real header row;
- common aliases such as `Ad Unit ID`, `Placement Name`, `Ad Type`, `Tên vị trí`, and `Loại quảng cáo`;
- an unnamed ID column when its values clearly look like ad-unit IDs (for example `ca-app-pub-.../...`).

The working file is flexible too. It recognizes key/value pairs such as `Task Detail / Document`, `Content / Detail`, `Field / Value`, `Key / Data`, and their common Vietnamese equivalents. Column order and unrelated columns such as `Order`, `PIC`, owner, or status do not matter. Row labels such as `Application name`, `Bundle ID`, and `Firebase project` are normalized to the expected checklist fields.

When headers are unfamiliar, the parser can infer columns from recognizable values: checklist labels, package names, Firebase URLs, placement keys, ad formats, and ad-unit IDs. Explicit aliases always win. If two columns are equally plausible or confidence is too low, the audit stops and reports the delimiter, detected headers, and missing semantics instead of silently auditing the wrong data.

If the CLI reports multiple CSV candidates, pass the files explicitly:

```bash
npx -y github:NguyenMinhVu02/Skill_Ads_Audit audit \
  --project . \
  --ads-script "./config/ADS SCRIPTS.csv" \
  --working-file "./config/working-file.csv" \
  --no-webhook
```

Reports are written to `ads-audit-output/ads-audit-summary.md` and `ads-audit-output/ads-audit-evidence.json`. The command reads the Android project; it does not modify source code. Use `--no-webhook` for a local-only report.

## Use with Codex CLI (AI + skill + webhook)

Install for every project on the machine:

```bash
mkdir -p "$HOME/.agents/skills"
git clone \
  https://github.com/NguyenMinhVu02/Skill_Ads_Audit.git \
  "$HOME/.agents/skills/infinity-ads-compliance-audit"
```

Or install only in one repository:

```text
partner-app/.agents/skills/infinity-ads-compliance-audit/
```

Then run Codex from the Android project root:

```bash
cd partner-app
codex
```

Ask Codex to invoke the skill with `$infinity-ads-compliance-audit`:

```text
Use $infinity-ads-compliance-audit to audit the current project.
Find the ADS SCRIPTS CSV and working-file CSV yourself. Do not change code.
Do not check app-ads.txt.
Return a short Vietnamese MKT report with app name, package name, errors to fix, items requiring technical confirmation, and passed checks.
Send the sanitized report to the configured Discord webhook.
```

Codex reads the skill, runs the bundled auditor, reads the generated reports, and sends the webhook unless the prompt asks for a local-only run. The partner does not need to type the Python command.

## Use with Claude Code (AI + skill + webhook)

Install for every project on the machine:

```bash
mkdir -p "$HOME/.claude/skills"
git clone \
  https://github.com/NguyenMinhVu02/Skill_Ads_Audit.git \
  "$HOME/.claude/skills/infinity-ads-compliance-audit"
```

Or install only in one repository:

```text
partner-app/.claude/skills/infinity-ads-compliance-audit/
```

Then run Claude Code from the Android project root:

```bash
cd partner-app
claude
```

Invoke the skill with `/infinity-ads-compliance-audit`:

```text
/infinity-ads-compliance-audit

Audit this Android project. Find the ADS SCRIPTS CSV and working-file CSV,
do not modify source code, read the generated reports, and send the sanitized
report to the configured Discord webhook. Reply in Vietnamese.
```

Claude Code loads skills from `.claude/skills/<skill-name>/SKILL.md` for a project or `$HOME/.claude/skills/<skill-name>/SKILL.md` for the user. If the skill was added while Claude Code was already open, restart it or reload skills.

Both Codex and Claude require Python 3.10 or newer for the bundled auditor. `npx` is only the terminal-only fallback; it does not provide the AI conversation.

## Run the Python auditor directly (optional)

From the partner repository root:

```bash
python3 "/path/to/infinity-ads-compliance-audit/scripts/run_audit.py" \
  --project .
```

The Python CLI now auto-discovers the same two files as the npx command. When there are zero or multiple candidates, pass explicit paths; supplied paths always take precedence:

```bash
python3 "/path/to/infinity-ads-compliance-audit/scripts/run_audit.py" \
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

The bundled skill sends a short MKT report to its embedded Discord webhook after each audit unless `--no-webhook` is passed. It includes app name, package name, counts, short errors, and items requiring technical confirmation. It also attaches `ads-audit-summary.md` so developers can open the full local report from Discord. No webhook URL is needed when using the skill.

Each Discord error is rendered as separate lines:

```text
1. Error group title
Mô tả: short problem description
**Cách sửa:** concrete developer fix
```

Use `--no-webhook` only when Infinity requests a local-only audit.

## Override webhook (Infinity-approved only)

```bash
python3 "/path/to/infinity-ads-compliance-audit/scripts/run_audit.py" \
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

## AI invocation summary

| Host | Install location | Invocation |
| --- | --- | --- |
| Codex CLI | `$HOME/.agents/skills/` or `.agents/skills/` | `$infinity-ads-compliance-audit` |
| Claude Code | `$HOME/.claude/skills/` or `.claude/skills/` | `/infinity-ads-compliance-audit` |

The AI host runs the local auditor and then explains the evidence. The auditor itself is deterministic Python code; `npx` is not an AI runtime.
