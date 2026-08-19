# Infinity Ads Compliance Audit

An agent skill for **Claude Code** and **Codex** that audits an Android app's
Infinity ads integration against the base project and the app's own contract
documents. The audit reads the project; it never modifies source.

Install it once, then ask the AI to check any Android project.

## Install

```bash
git clone https://github.com/NguyenMinhVu02/Skill_Ads_Audit.git
cd Skill_Ads_Audit
./install.sh          # macOS / Linux
.\install.ps1         # Windows PowerShell
```

The installer detects which agents are on the machine and copies the skill into
each one it finds:

| Host | Location | Invoke with |
| --- | --- | --- |
| Claude Code | `~/.claude/skills/` | `/infinity-ads-compliance-audit` |
| Codex CLI | `$CODEX_HOME/skills/` (default `~/.codex/skills/`) | `$infinity-ads-compliance-audit` |
| Antigravity / Gemini | `~/.gemini/antigravity/skills/` | ask in plain language |

Codex reads skills from `$CODEX_HOME/skills`, **not** `~/.agents/skills`. The
installer writes to both, so an older Codex keeps working.

To install into one repository instead of the whole machine, clone into
`<project>/.claude/skills/infinity-ads-compliance-audit/` (or `.agents/skills/`).
Restart the agent afterwards so it picks up the new skill.

Requires Python 3.9+ and `curl`. No Python packages to install — standard
library only.

## Use

From the Android project root.

**Claude Code** — start `claude`, then:

```text
/infinity-ads-compliance-audit

Audit this project. Documents:
  ADS SCRIPTS:  https://docs.google.com/spreadsheets/d/.../edit#gid=0
  Checklist:    https://docs.google.com/document/d/.../edit
Do not modify source. Reply in Vietnamese.
```

**Codex CLI** — start `codex`, then use the `$` sigil:

```text
$infinity-ads-compliance-audit

Audit this project. Documents:
  ADS SCRIPTS:  https://docs.google.com/spreadsheets/d/.../edit#gid=0
  Checklist:    https://docs.google.com/document/d/.../edit
Do not modify source. Reply in Vietnamese.
```

Both hosts also select the skill on their own when you simply describe the task
("kiểm tra tuân thủ ads cho project này"). The explicit sigil just guarantees it.

If the two CSV files already sit in the project, drop the Documents block —
they are discovered automatically.

The agent runs the bundled auditor, reads the generated reports, checks each
finding against the code, and sends the sanitized report to Discord unless you
ask for a local-only run.

### The two documents

| Document | Carries |
| --- | --- |
| **ADS SCRIPTS** | placement key, ad type, ad-unit ID, AdMob APP ID |
| **working checklist** | app name, package, Firebase project, Adjust/Facebook/TikTok tokens |

Each may be a local CSV or a **Google Sheets / Google Docs link**. Sheets are
exported as CSV; Docs are read as `label: value` lines. Share the link as
anyone-with-the-link viewer, otherwise the download returns a sign-in page and
the audit stops with a sharing error.

If both documents are already CSV files inside the project, they are discovered
automatically — one filename containing `ADS SCRIPTS`, one containing `working`
or `work file`. Discovery never guesses when it finds zero or several matches.

Partner spreadsheets do not need a fixed layout. The parser handles comma,
semicolon, tab and pipe delimiters, English and Vietnamese column labels, title
rows before the real header, and common aliases. When headers are unfamiliar it
infers columns from recognisable values — package names, Firebase URLs, ad
formats, ad-unit IDs. Explicit aliases always win, and if two columns are
equally plausible the audit **stops and reports** rather than auditing the wrong
data.

## What gets checked

Calibrated against the Infinity base project so that a correct app passes
cleanly.

- **Identity** — package, app name (from default `res/values/strings.xml`, not a
  translation), AdMob app id from the **release** `manifestPlaceholders`,
  Firebase project, service tokens.
- **Config** — every contract key/ID exists in release `ad_config.json`, matches
  exactly, and declares `isEnable`. `ad_config_debug.json` is deliberately
  exempt.
- **Init order** — `MobileAds.initialize` → `DevConfig.init` →
  `AdRemoteConfig.initializeFromAssets` → `ERainAd.init`, plus the DevConfig
  version fields, `ERainAdConfig` fields, `intervalInterstitialAd`, AppOpen
  exclusions, lifecycle observer and activity callbacks.
- **Screen structure** — Splash, Language, Onboarding, Home and Welcome must be
  separate Activities. A single-Activity + Fragment implementation of those
  screens is an error. Fragments used as *pages inside* them are correct.
- **Preload / load / show** — where each ad is preloaded, the four load gates
  (`isEnable`, purchase, network, `getShouldDisplay*(config.enableUaCheck)`),
  null-fallback hiding, and interstitials navigating only from their callback.
- **Resume vs Welcome** — mode selection, disabled-screen lists, and the gates
  that stop an App Open ad stacking with a Welcome interstitial.
- **Banner** — config/purchase/container gates and `reloadIntervalSeconds`.

Unmapped placements stay `NEEDS_MAPPING`. Claims static analysis cannot settle
stay `NEEDS_RUNTIME_PROOF` with a test case attached. Neither is a pass.

## Output

Written to `ads-audit-output/` inside the audited project:

- `ads-audit-summary.md` — full finding list for developers.
- `ads-audit-evidence.json` — sanitized Vietnamese MKT payload.

The command exits `0` with no static failures, `2` when fixes are required, and
`1` for invalid input.

Reports redact Adjust, Facebook client, and TikTok values. They never include
`app-ads.txt` checks.

## Custom placements

If a placement returns `NEEDS_MAPPING`, copy `templates/ads-audit-overrides.yaml`
into the app and add the approved class and call mapping, keeping the contract
key and ID exactly. Some placements — `native_home`, `native_permission`,
`native_onboarding_fullscreen_*_4`, `banner_splash`, `reward_example` — exist in
`AdsManager` but are not wired to a screen in the base, so they land here by
design.

## Discord webhook

The skill posts a short MKT report plus the summary file after each audit.
Disable per-run with `--no-webhook`. Override the endpoint with `--webhook-url`
or the `ADS_AUDIT_WEBHOOK_URL` / `DISCORD_WEBHOOK_URL` environment variables.

## Running the auditor directly

Useful for CI or debugging; the AI path above is the intended one.

```bash
python3 scripts/run_audit.py --project /path/to/app --no-webhook
python3 scripts/run_audit.py --project . \
  --ads-script "https://docs.google.com/spreadsheets/d/<id>/edit#gid=0" \
  --working-file "./working file.csv"
```

## Package for a partner repo

```bash
python3 scripts/package_skill.py --skill-root . --output infinity-ads-audit.zip
```

## Reference

- `references/base-code-reference.md` — the base implementation in code:
  Gradle, `GlobalApp`, `AdsManager`, every screen, gates, config schema.
- `references/base-integration-rules.md` — the same rules as a checklist.
- `references/placement-rule-map.yaml` — approved evidence per placement.
