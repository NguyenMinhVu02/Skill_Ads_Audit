# Infinity Ads Compliance Audit Implementation Plan

> For agentic workers: implement task-by-task with test-first changes.

**Goal:** Expand the portable `infinity-ads-compliance-audit` skill so partner repos can be checked against the full Infinity ads base flow, not only CSV/config identity.

**Architecture:** Keep the package self-contained under `infinity-ads-compliance-audit`. Store the base contract in reference files and enforce stable, token-based static rules in `scripts/ads_audit_lib.py`; keep runtime-only claims as `NEEDS_RUNTIME_PROOF`.

**Tech Stack:** Python 3.10+, stdlib only, Android/Kotlin static text inspection, `unittest`.

## Global Constraints

- Only modify and package files inside `infinity-ads-compliance-audit`.
- Do not require partner teams to run terminal commands manually when Codex is using the skill.
- Never leak raw Adjust, Facebook client, TikTok, webhook, or other secret values.
- Keep webhook optional via `--no-webhook`; local reports must always be generated.

## Tasks

### Task 1: Lock Full Base Flow Behavior With Tests

**Files:**
- Modify: `infinity-ads-compliance-audit/tests/test_run_audit.py`

**Steps:**
- Add a compliant fake Android project fixture with `GlobalApp`, `AdsManager`, `SplashActivity`, `LanguageActivity`, `OnBoardingActivity`, `OnboardingPageFragment`, `WelcomeActivity`, `AppLifecycleObserver`, `ResumeAdsEntryRule`, and `BaseActivityWithBanner`.
- Assert PASS for init order, DevConfig fields, screen flow, AdsManager gates, welcome/resume, and banner reload.
- Add a negative fixture that breaks init order and hard-codes a UA gate; assert FAIL.

### Task 2: Implement Base Flow Static Rules

**Files:**
- Modify: `infinity-ads-compliance-audit/scripts/ads_audit_lib.py`
- Modify: `infinity-ads-compliance-audit/references/base-integration-rules.md`
- Modify: `infinity-ads-compliance-audit/references/placement-rule-map.yaml`

**Steps:**
- Add helper checks for class token presence and ordered token presence.
- Add architecture rules from README and base code.
- Add screen flow rules for Splash, Language, Onboarding, Welcome, Resume, and Banner.
- Add AdsManager placement gate rules for native/inter/banner methods.

### Task 3: Document and Package the Skill

**Files:**
- Modify: `infinity-ads-compliance-audit/SKILL.md`
- Modify: `infinity-ads-compliance-audit/README.md`
- Modify: `infinity-ads-compliance-audit/README.vi.md`
- Create: `infinity-ads-compliance-audit/scripts/package_skill.py`

**Steps:**
- Document full audit scope and local-only packaging behavior.
- Add a zip packager that excludes `__pycache__`, `.pyc`, and generated reports.
- Verify with unit tests and package as `infinity-ads-compliance-audit.zip`.
