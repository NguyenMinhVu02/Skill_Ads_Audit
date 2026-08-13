# Base Integration Rules

Source: clean `Example-AdLogic-Partner` README and implementation at the time this skill was created.

## Mandatory architecture

1. `GlobalApp.onCreate()` initializes in this order: `MobileAds.initialize`, `DevConfig.init`, `AdRemoteConfig.initializeFromAssets`, then `ERainAd.getInstance().init`.
2. `DevConfig.init` must receive `BuildConfig.ERAIN_STUDIO_VERSION`, `BuildConfig.PLAY_SERVICES_ADS_VERSION`, and `BuildConfig.GDPR_MODULE_VERSION`; `app/build.gradle` must declare those three fields for debug and release.
3. `GlobalApp.initAds()` must set environment, `AdjustConfig`, `facebookClientToken`, `adjustTokenTiktok`, `intervalInterstitialAd = 35`, `idAdResume`, `Admob.setDisableAdResumeWhenClickAds(true)`, `Admob.setOpenActivityAfterShowInterAds(true)`, AppOpen disabled screens, lifecycle observer, and activity callbacks.
4. Debug reads `ad_config_debug.json`; release reads `ad_config.json` and may apply Firebase Remote Config key `ad_remote_config`.
5. Put placement loading/showing in `AdsManager`; do not make unapproved direct SDK calls from activities/fragments.
6. Native rendering observes a `LiveData`, populates the native view when non-null, and hides the container when null/offline.
7. A load must protect `isEnable`, purchase state, network, and the placement's required `getShouldDisplay*(config.enableUaCheck)` gate.
8. Interstitial show must continue navigation only through the close/fail/next callback; production show logic must not require debug-only `ignoreLimit`.

## Base journey

| Stage | Required behavior |
| --- | --- |
| Application | Initialize ads/config early; initialize DevConfig; register lifecycle rules and activity callbacks. |
| Splash | Consent + RemoteConfig; apply `AdRemoteConfig.initialize(this, RemoteConfigUtils.getAdRemoteConfig())`; load splash interstitial; preload Language native only after splash ad loads; configure `open_resume`. |
| Language | DevSetting on `tvTitle`; after 100ms load language-click native and preload onboarding page 1; observe language/native-click LiveData; hide ad container on null/offline. |
| Onboarding | After 100ms preload native page 4, native full, and onboarding interstitial; add fullscreen page only when network + Full1 gate allow it; only move to Home in the inter close/fail callback. |
| Onboarding page | Map page flags to `nativeOnboarding1AdLive`, `nativeOnboarding4AdLive`, and `nativeAdOnBoardingFullLive`; render non-null ad, hide ad region on null. |
| Home/banner | Use `BaseActivityWithBanner` / `AdsManager.loadBanner`; gate by config + purchase + `fr_banner`; follow `reloadIntervalSeconds`. |
| Resume/welcome | Choose App Open or Welcome using `ResumeAdsEntryRule`; disabled screens must not trigger resume ads; do not stack AppOpen with Welcome. |
| Welcome | Load native + inter Welcome in `initViews`; observe/render native Welcome; show inter Welcome on CTA and finish/continue only from callback. |
| Uninstall widget | Apply the widget display gate and preserve the configured confirm/survey navigation. |

## Gate mapping

| Placement family | Required SDK gate |
| --- | --- |
| `native_onboarding_fullscreen_*` | `getShouldDisplayNativeOnboardingFull1/2(config.enableUaCheck)` |
| `native_onboarding_*_4` | `getShouldDisplayNativeOnboardingNormal2(config.enableUaCheck)` |
| `native_home` | `getShouldDisplayNativeHome(config.enableUaCheck)` |
| `native_permission` | `getShouldDisplayNativePermission(config.enableUaCheck)` |
| `inter_onboarding` | `getShouldDisplayInterOnboarding(config.enableUaCheck)` |
| welcome native/inter | `getShouldDisplayNativeWelcomeBack` / `getShouldDisplayInterWelcomeBack` |
| uninstall widget/survey | `getShouldDisplayWidgetUninstall(config.enableUaCheck)` |

## Pipeline rule ids

The auditor emits these base-flow rule ids in addition to app identity/config checks:

- `ARCH_GLOBAL_INIT_ORDER`
- `ARCH_DEV_CONFIG_INIT`
- `ARCH_DEV_CONFIG_BUILD_FIELDS`
- `ARCH_ADS_CONFIG_FIELDS`
- `ARCH_APP_OPEN_EXCLUSIONS`
- `ARCH_ADS_MANAGER_NATIVE_GATES`
- `ARCH_ADS_MANAGER_UA_GATES`
- `ARCH_ADS_MANAGER_INTER_GATES`
- `ARCH_ADS_MANAGER_BANNER`
- `ARCH_BANNER_BASE_RELOAD`
- `FLOW_SPLASH_REMOTE_CONFIG`
- `FLOW_SPLASH_INTER_PRELOAD_LANGUAGE`
- `FLOW_SPLASH_OPEN_RESUME`
- `FLOW_LANGUAGE_DEV_SETTING`
- `FLOW_LANGUAGE_PRELOAD_AND_RENDER`
- `FLOW_ONBOARDING_PRELOAD_AND_SHOW`
- `FLOW_ONBOARDING_PAGE_RENDERING`
- `FLOW_RESUME_RULE`
- `FLOW_WELCOME_NATIVE_AND_INTER`
- `FLOW_INTER_WELCOME_BACK_*`

## Static-analysis limit

Static checks cannot prove a real ad loaded, all buttons have been tapped, Firebase production values are active, or UI timing is correct. Require runtime proof rather than passing these claims.
