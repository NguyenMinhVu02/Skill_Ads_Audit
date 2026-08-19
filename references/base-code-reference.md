# Base Code Reference

Extracted from the Infinity base project `TestSill` (`com.itg.template`). This is
the implementation ground truth: what correct integration actually looks like.
`base-integration-rules.md` states *what must be true*; this file shows *the code*.

Every snippet below is real base code, not an idealized rewrite. When an app
differs from these snippets in a way that changes ad behavior, that is a finding.

## 1. Gradle setup

`versions.gradle` (ads-related pins):

```groovy
erain_studio_version       = '2.0'
module_update_gdpr_version = '2.0.2'
play_services_ads_version  = '24.7.0'
billing_version            = '7.0.0'
```

`app/build.gradle` dependencies:

```groovy
implementation "com.github.trongluan99:ERain-Studio:$erain_studio_version"
implementation 'com.github.Infinity-Technologies-Global:DevConfig:1.0.7-partner'
implementation "com.github.Infinity-Technologies-Global:Module-Update-GDPR:$module_update_gdpr_version"
implementation "com.google.android.gms:play-services-ads:$play_services_ads_version"
implementation "com.android.billingclient:billing:$billing_version"
implementation "com.facebook.shimmer:shimmer:$shimmer_version"
```

Both build types must declare the three version fields, and the AdMob app id
belongs in `manifestPlaceholders`. Debug carries Google's test app id; release
carries the real one from the ADS SCRIPTS contract:

```groovy
debug {
    manifestPlaceholders = [app_id: "ca-app-pub-3940256099942544~3347511713"]
    buildConfigField "String", "ERAIN_STUDIO_VERSION",     "\"$erain_studio_version\""
    buildConfigField "String", "PLAY_SERVICES_ADS_VERSION", "\"$play_services_ads_version\""
    buildConfigField "String", "GDPR_MODULE_VERSION",      "\"$module_update_gdpr_version\""
}
release {
    manifestPlaceholders = [app_id: "ca-app-pub-7208941695689653~1614717305"]
    // same three buildConfigField lines
}
```

Only the **release** `manifestPlaceholders` app id is compared against the
contract. Reading the debug placeholder produces a false failure, because the
debug value is deliberately Google's public test id.

## 2. Application: `GlobalApp`

Extends `AdsMultiDexApplication`. Order in `onCreate` is load-bearing.

```kotlin
@HiltAndroidApp
class GlobalApp : AdsMultiDexApplication() {

    override fun onCreate() {
        super.onCreate()
        MobileAds.initialize(this) {}
        DevConfig.init(
            context = this,
            nkhStudioVersion = BuildConfig.ERAIN_STUDIO_VERSION,
            playServicesAdsVersion = BuildConfig.PLAY_SERVICES_ADS_VERSION,
            gdprModuleVersion = BuildConfig.GDPR_MODULE_VERSION
        )
        instance = this
        if (BuildConfig.DEBUG) Timber.plant(Timber.DebugTree())
        initAdRemoteConfig()
        initAds()
        ProcessLifecycleOwner.get().lifecycle.addObserver(AppLifecycleObserver())
        registerActivityLifecycleCallbacks(AppActivityLifecycleCallbacks())
    }

    private fun initAdRemoteConfig() {
        AdRemoteConfig.initializeFromAssets(this)
    }

    private fun initAds() {
        val environment = if (BuildConfig.DEBUG) ERainAdConfig.ENVIRONMENT_DEVELOP
                          else ERainAdConfig.ENVIRONMENT_PRODUCTION
        mERainAdConfig = ERainAdConfig(this, environment)

        mERainAdConfig.adjustConfig = AdjustConfig(true, resources.getString(R.string.adjust_token))
        mERainAdConfig.facebookClientToken = resources.getString(R.string.facebook_client_token)
        mERainAdConfig.adjustTokenTiktok = resources.getString(R.string.event_token)
        mERainAdConfig.intervalInterstitialAd = 35
        mERainAdConfig.idAdResume = ""

        ERainAd.getInstance().init(this, mERainAdConfig)

        Admob.getInstance().setDisableAdResumeWhenClickAds(true)
        Admob.getInstance().setOpenActivityAfterShowInterAds(true)
        AppOpenManager.getInstance().disableAppResumeWithActivity(SplashActivity::class.java)
        AppOpenManager.getInstance().disableAppResumeWithActivity(LanguageActivity::class.java)
        AppOpenManager.getInstance().disableAppResumeWithActivity(OnBoardingActivity::class.java)
        AppOpenManager.getInstance().disableAppResumeWithActivity(ConfirmUninstallActivity::class.java)
    }
}
```

Notes that matter when auditing:

- The `DevConfig.init` parameter is named `nkhStudioVersion`, but it receives
  `BuildConfig.ERAIN_STUDIO_VERSION`. Do not expect a matching name.
- Secret values come from string resources (`adjust_token`,
  `facebook_client_token`, `event_token`), never inline literals.
- `idAdResume` is set to `""` here; the real resume id is applied later in
  `SplashActivity` through `AppOpenManager.setAppResumeAdId`.
- The observer and callbacks are registered unconditionally.

## 3. Config model

`AdUnitConfig` — one entry per placement:

```kotlin
@Keep
data class AdUnitConfig(
    val id: String,
    val isEnable: Boolean,
    val enableUaCheck: Boolean = false,
    val reloadIntervalSeconds: Int? = null,
    val colorCTA: String = "default",
    val heightCTA: Int = 40,
    val positionCTA: String = "BOTTOM",
    val components: List<String> = listOf("icon_headline", "body", "media", "cta")
)
```

`ad_config.json` entry shape. Note the JSON key is `enable_ua_check` (snake
case) while the Kotlin property is `enableUaCheck`:

```json
"native_language_1": {
  "id": "ca-app-pub-7208941695689653/1611434606",
  "isEnable": true,
  "colorCTA": "default",
  "heightCTA": 45,
  "positionCTA": "BOTTOM",
  "components": ["icon_headline", "body", "media", "cta"],
  "enable_ua_check": false
},
"banner_home": {
  "id": "...", "isEnable": true, "reloadIntervalSeconds": 30, "enable_ua_check": false
}
```

The 24 base placement keys:

```
inter_splash  banner_splash  open_resume
native_language_1  native_language_1_click  native_language_2  native_language_2_click
native_onboarding_1_1  native_onboarding_2_1  native_onboarding_1_4  native_onboarding_2_4
native_onboarding_fullscreen_1_3  native_onboarding_fullscreen_2_3
native_onboarding_fullscreen_1_4  native_onboarding_fullscreen_2_4
native_permission  native_home  inter_onboarding  banner_home
native_survey  native_confirm_uninstall  native_welcome  inter_welcome  reward_example
```

`AdRemoteConfig` selects the file by build type, and release may be overridden
by the Firebase Remote Config key `ad_remote_config`:

```kotlin
private const val RELEASE_FILE_NAME = "ad_config.json"
private const val DEBUG_FILE_NAME   = "ad_config_debug.json"

fun initialize(context: Context, json: String? = null) {
    instance = if (BuildConfig.DEBUG) fromAssets(context, DEBUG_FILE_NAME)
               else fromJsonOrAssets(context, json, RELEASE_FILE_NAME)
}
fun initializeFromAssets(context: Context) {
    instance = fromAssets(context, if (BuildConfig.DEBUG) DEBUG_FILE_NAME else RELEASE_FILE_NAME)
}
```

Because debug reads a separate file, debug ad-unit ids legitimately differ from
the contract and must never be compared against ADS SCRIPTS.

Each placement is reached through a generated extension property, so app code
reads `AdRemoteConfig.native_language_1`, not a map lookup:

```kotlin
val AdRemoteConfig.Companion.native_language_1: AdUnitConfig
    get() = getInstance().native_language_1
```

## 4. `AdsManager` — the single load/show funnel

All native loads pass through one private function that applies every gate:

```kotlin
private fun loadNativeInternal(
    activity: Activity,
    config: AdUnitConfig,
    layoutRes: Int,
    liveData: MutableLiveData<ApNativeAd?>,
    shouldDisplay: Boolean = true,
) {
    if (!config.isEnable
        || AppPurchase.getInstance().isPurchased(activity)
        || !activity.isNetworkAvailable()
        || !shouldDisplay
    ) {
        liveData.postValue(null)
        return
    }
    ERainAd.getInstance()
        .loadNativeAdResultCallback(activity, config.id, layoutRes, object : AdCallback() {
            override fun onNativeAdLoaded(nativeAd: ApNativeAd) {
                super.onNativeAdLoaded(nativeAd)
                adConfigMap[nativeAd] = config
                liveData.postValue(nativeAd)
            }
            override fun onAdFailedToLoad(adError: LoadAdError?) {
                super.onAdFailedToLoad(adError)
                liveData.postValue(null)
            }
        })
}
```

Four gates, always in this order: `isEnable` → purchase → network →
placement-specific `shouldDisplay`. On any refusal or failure the LiveData is
set to `null` so the screen hides its ad container instead of leaving a shimmer.

Per-placement wrappers pick the config by "first session" flag and pass the SDK
UA gate as `shouldDisplay`:

```kotlin
fun loadNativeLanguage(activity: Activity, isFirst: Boolean, layoutRes: Int) {
    val config = if (isFirst) AdRemoteConfig.native_language_1 else AdRemoteConfig.native_language_2
    loadNativeInternal(activity, config, layoutRes, nativeLanguageAdLive)
}

fun loadNativeOnboarding4(activity: Activity, isFirst: Boolean, layoutRes: Int) {
    val config = if (isFirst) AdRemoteConfig.native_onboarding_1_4 else AdRemoteConfig.native_onboarding_2_4
    loadNativeInternal(activity, config, layoutRes, nativeOnboarding4AdLive,
        ERainAd.getInstance().getShouldDisplayNativeOnboardingNormal2(config.enableUaCheck))
}

fun loadNativeOnboardingFull(activity: Activity, isFirst: Boolean, layoutRes: Int) {
    val config = if (isFirst) AdRemoteConfig.native_onboarding_fullscreen_1_3
                 else AdRemoteConfig.native_onboarding_fullscreen_2_3
    loadNativeInternal(activity, config, layoutRes, nativeAdOnBoardingFullLive,
        ERainAd.getInstance().getShouldDisplayNativeOnboardingFull1(config.enableUaCheck))
}
```

`native_language_*` and `native_onboarding_*_1` intentionally pass **no**
`shouldDisplay` gate — they default to `true`. Only the placements listed in the
gate table below carry one.

One LiveData per placement family:

```kotlin
val nativeLanguageAdLive        = MutableLiveData<ApNativeAd?>()
val nativeLanguageClickAdLive   = MutableLiveData<ApNativeAd?>()
val nativeOnboarding1AdLive     = MutableLiveData<ApNativeAd?>()
val nativeOnboarding4AdLive     = MutableLiveData<ApNativeAd?>()
val nativeAdOnBoardingFullLive  = MutableLiveData<ApNativeAd?>()
val nativeAdOnBoardingFull2Live = MutableLiveData<ApNativeAd?>()
val nativeWelcomeAdLive         = MutableLiveData<ApNativeAd?>()
val nativeHomeAdLive            = MutableLiveData<ApNativeAd?>()
val nativePermissionAdLive      = MutableLiveData<ApNativeAd?>()
val nativeSurveyAdLive          = MutableLiveData<ApNativeAd?>()
val nativeConfirmUninstallAdLive = MutableLiveData<ApNativeAd?>()
```

Interstitial load and show are separate calls; navigation happens in the
callback, never inline:

```kotlin
fun loadInterOnboarding(context: Context, ignoreLimit: Boolean = false) {
    val config = AdRemoteConfig.inter_onboarding
    if (!config.isEnable
        || AppPurchase.getInstance().isPurchased(context)
        || (!ignoreLimit && !ERainAd.getInstance().getShouldDisplayInterOnboarding(config.enableUaCheck))
    ) {
        interOnboarding = null
        return
    }
    interOnboarding = ERainAd.getInstance().getInterstitialAds(context, config.id, object : AdCallback() {})
}

fun showInterOnboarding(context: Context, ignoreLimit: Boolean = false, onAction: () -> Unit) {
    val interstitial = interOnboarding
    if (interstitial != null && interstitial.isReady
        && !AppPurchase.getInstance().isPurchased(context) && (ignoreLimit)
    ) {
        ERainAd.getInstance().forceShowInterstitial(context, interstitial, object : AdCallback() {
            override fun onNextAction() { super.onNextAction(); onAction() }
        }, true)
    } else {
        onAction()
    }
}
```

The `onAction()` in the `else` branch is mandatory: when the ad is unavailable
the user must still advance. A show path that can leave the user stuck is a
defect regardless of the ad gates.

Banner load, with shimmer reset and hide-on-failure:

```kotlin
fun loadBanner(activity: AppCompatActivity, adUnitConfig: AdUnitConfig,
               frAds: FrameLayout, isCollapse: Boolean) {
    if (adUnitConfig.isEnable) {
        removeBannerView(activity, frAds)
        if (isCollapse) ERainAd.getInstance().loadCollapsibleBanner(
            activity, adUnitConfig.id, AppConstant.CollapsibleGravity.BOTTOM,
            object : AdCallback() {
                override fun onAdFailedToLoad(i: LoadAdError?) { super.onAdFailedToLoad(i); frAds.goneView() }
            })
        else ERainAd.getInstance().loadBanner(activity, adUnitConfig.id, object : AdCallback() {
            override fun onAdFailedToLoad(i: LoadAdError?) { super.onAdFailedToLoad(i); frAds.goneView() }
        })
    } else {
        frAds.removeAllViews()
        frAds.goneView()
    }
}
```

Network check is local to `AdsManager`:

```kotlin
private fun Context.isNetworkAvailable(): Boolean {
    val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager ?: return false
    val network = cm.activeNetwork ?: return false
    val caps = cm.getNetworkCapabilities(network) ?: return false
    return caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) ||
           caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) ||
           caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)
}
```

## 5. SDK gate table

`shouldDisplay` values come from `ERainAd.getInstance()`. Only these nine exist
in the base:

| Placement | Gate call |
| --- | --- |
| `native_onboarding_*_4` | `getShouldDisplayNativeOnboardingNormal2(config.enableUaCheck)` |
| `native_onboarding_fullscreen_*_3` | `getShouldDisplayNativeOnboardingFull1(config.enableUaCheck)` |
| `native_onboarding_fullscreen_*_4` | `getShouldDisplayNativeOnboardingFull2(config.enableUaCheck)` |
| `native_home` | `getShouldDisplayNativeHome(config.enableUaCheck)` |
| `native_permission` | `getShouldDisplayNativePermission(config.enableUaCheck)` |
| `native_welcome` | `getShouldDisplayNativeWelcomeBack(config.enableUaCheck)` |
| `inter_onboarding` | `getShouldDisplayInterOnboarding(config.enableUaCheck)` |
| `inter_welcome` | `getShouldDisplayInterWelcomeBack(config.enableUaCheck)` |
| `native_survey`, `native_confirm_uninstall`, uninstall widget | `getShouldDisplayWidgetUninstall(config.enableUaCheck)` |

`getShouldDisplayInterWelcomeBack` is called from **`AppLifecycleObserver`**, not
from `AdsManager`. Do not require it inside the manager.

## 6. Screen flow

### SplashActivity

```kotlin
override fun initViews() {
    super.initViews()
    RemoteConfigUtils.init(this, this)
    consentHandler = ConsentHandler(
        activity = this, appSharedPref = appSharedPref, trackingSuffix = 1,
        onConsentFlowCompleted = { loadingRemoteConfig() }
    )
    if (appSharedPref.isConfirmConsent.not() && appSharedPref.isUserGlobal.not() && isNetwork()) {
        consentHandler.requestConsent()
    } else {
        loadingRemoteConfig()
    }
    initVideoSplash()
}

private fun loadingRemoteConfig() {
    object : CountDownTimer(AppConstants.DEFAULT_TIME_SPLASH, 100) {   // 6500ms
        override fun onTick(millisUntilFinished: Long) {
            if (getConfigSuccess && millisUntilFinished < AppConstants.DEFAULT_LIMIT_TIME_SPLASH) {  // 5000ms
                checkRemoteConfigResult(); cancel()
            }
        }
        override fun onFinish() { if (!getConfigSuccess) checkRemoteConfigResult() }
    }.start()
}

private fun checkRemoteConfigResult() {
    AdRemoteConfig.initialize(this, RemoteConfigUtils.getAdRemoteConfig())

    if (AdRemoteConfig.inter_splash.isEnable && isNetwork(this@SplashActivity)) {
        ERainAd.getInstance().loadSplashInterstitialAds(
            this, AdRemoteConfig.inter_splash.id, 30000, 5000,
            object : AdCallback() {
                override fun onNextAction() { super.onNextAction(); moveActivity() }
                override fun onAdLoaded() {
                    super.onAdLoaded()
                    lifecycleScope.launch(Dispatchers.Main) {
                        loadNativeLanguage(this@SplashActivity, appSharedPref.firstLanguage,
                                           R.layout.layout_native_language)
                    }
                }
            })
    } else {
        moveActivity()
    }

    if (ResumeAdsEntryRule.shouldEnableOpenResume()) {
        AppOpenManager.getInstance().setAppResumeAdId(AdRemoteConfig.open_resume.id)
        AppOpenManager.getInstance().enableAppResume()
    } else {
        AppOpenManager.getInstance().disableAppResume()
    }
}
```

Timing constants: `DEFAULT_TIME_SPLASH = 6500`, `DEFAULT_LIMIT_TIME_SPLASH = 5000`,
splash interstitial timeout `30000` / min show `5000`.

Preloading the Language native from `onAdLoaded` — not from `initViews`, not
from `onNextAction` — is what gives Language an ad ready on arrival while the
splash interstitial is still on screen. Moving that call breaks the fill rate.

`onResume` recovers a failed splash ad:

```kotlin
override fun onResume() {
    super.onResume()
    ERainAd.getInstance().onCheckShowSplashWhenFail(this, object : AdCallback() {
        override fun onNextAction() { super.onNextAction(); moveActivity() }
    }, 1000)
}
```

### LanguageActivity

```kotlin
override fun initViews() {
    isFromSetting = intent.getBooleanExtra(EXTRA_FROM_SETTING, false)
    mBinding.tvTitle.setOnAdminAdToggleListener {
        Routes.startSplashActivity(this@LanguageActivity); finish()
    }
    initAdapter(); initLayout()

    mBinding.root.postDelayed({
        loadNativeLanguageClick(this, appSharedPref.firstLanguage, R.layout.layout_native_language_click)
        initAds()
    }, 100L)
}

private fun initAds() {
    if (fromSetting) mBinding.flAds.goneView()
    else AdsManager.loadNativeOnboarding1(this, appSharedPref.firstOnBoarding,
                                          R.layout.layout_native_onboarding)
}
```

The 100 ms `postDelayed` lets the list render first. The two observers are
mutually exclusive — selecting a language swaps which one is active:

```kotlin
private fun listenLanguageAd() {
    AdsManager.nativeLanguageClickAdLive.removeObservers(this)
    AdsManager.nativeLanguageAdLive.observe(this) { ad ->
        if (ad != null) showNativeLanguage(ad) else mBinding.flAds.goneView()
    }
}

private fun listenLanguageClickAd() {
    AdsManager.nativeLanguageAdLive.removeObservers(this)
    AdsManager.nativeLanguageClickAdLive.observe(this) { ad ->
        if (ad != null) showNativeLanguage(ad) else mBinding.flAds.goneView()
    }
}
```

Forgetting `removeObservers` leaves both live and makes the container flicker
between two ads. `LanguageActivity` also preloads onboarding page 1.

### OnBoardingActivity

```kotlin
override fun initViews() {
    initPage(); initOnboardingItems(); applyUninstallWidgetShortcutsFromRemoteConfig()

    mBinding.root.postDelayed({
        AdsManager.loadNativeOnboarding4(this, appSharedPref.firstOnBoarding, R.layout.layout_native_onboarding)
        AdsManager.loadNativeOnboardingFull(this, appSharedPref.firstOnBoarding, R.layout.layout_native_onboarding_full)
        AdsManager.loadInterOnboarding(this)
    }, 100L)
}
```

The fullscreen ad page is inserted into the pager only when network and the
Full1 gate both allow it:

```kotlin
if (isNetwork(this) && ERainAd.getInstance().getShouldDisplayNativeOnboardingFull1(
        AdRemoteConfig.native_onboarding_fullscreen_1_3.enableUaCheck))
    onboardingItems.add(OnboardingItem(isHasNativeFull = true))
```

Navigation to Home goes through the interstitial callback:

```kotlin
private fun startNextActivity() {
    appSharedPref.firstOnBoarding = false
    AdsManager.showInterOnboarding(this) {
        Routes.startMainActivity(this); finish()
    }
}
```

### OnboardingPageFragment

This fragment is a legitimate ViewPager2 page inside `OnBoardingActivity`. It is
**not** a violation of the Activity rule — the screen container is still an
Activity. It picks its LiveData from the page flags:

```kotlin
private fun observeAdChannel() {
    val liveData: MutableLiveData<ApNativeAd?> = when {
        onboardingItem.isHasNativeOnPage1 -> AdsManager.nativeOnboarding1AdLive
        onboardingItem.isHasNativeOnPage4 -> AdsManager.nativeOnboarding4AdLive
        onboardingItem.isHasNativeFull    -> AdsManager.nativeAdOnBoardingFullLive
        else -> { renderNoAd(); return }
    }
    liveData.observe(viewLifecycleOwner) { ad -> renderAd(ad) }
}
```

Note `viewLifecycleOwner`, not `this` — observing with the fragment lifecycle in
a pager leaks observers across page recycling.

Full-page ads hide the content layout and show a close button; normal pages keep
content visible and only toggle the ad block.

### WelcomeActivity

```kotlin
override fun initViews() {
    super.initViews()
    AdsManager.loadNativeWelcome(this, R.layout.layout_native_welcome)
    AdsManager.loadInterWelcome(this)
}

override fun observerData() {
    AdsManager.nativeWelcomeAdLive.observe(this) { ad -> renderWelcomeAd(ad) }
}

override fun onClickViews() {
    mBinding.btnStart.click {
        AdsManager.showInterWelcome(this) { finish() }
    }
}
```

Both Welcome ads load in `initViews`; the interstitial shows only from the CTA
and the activity finishes from the callback.

## 7. Resume vs Welcome

`ResumeAdsEntryRule` decides the mode from config alone:

```kotlin
enum class ResumeAdsEntryMode { OPEN_RESUME, WELCOME, NONE }

object ResumeAdsEntryRule {
    fun currentMode(): ResumeAdsEntryMode {
        if (!AdRemoteConfig.isInitialized()) return ResumeAdsEntryMode.NONE
        if (AdRemoteConfig.open_resume.isEnable) return ResumeAdsEntryMode.OPEN_RESUME
        val canUseWelcome = AdRemoteConfig.native_welcome.isEnable && AdRemoteConfig.inter_welcome.isEnable
        return if (canUseWelcome) ResumeAdsEntryMode.WELCOME else ResumeAdsEntryMode.NONE
    }
    fun shouldEnableOpenResume() = currentMode() == ResumeAdsEntryMode.OPEN_RESUME
    fun shouldShowWelcomeOnResume() =
        currentMode() == ResumeAdsEntryMode.WELCOME && !AdRemoteConfig.open_resume.isEnable
}
```

`open_resume` wins when enabled. The two are mutually exclusive by construction,
which is how the base guarantees an App Open ad and a Welcome interstitial never
stack on the same resume.

`AppLifecycleObserver` applies the remaining gates on foreground:

```kotlin
class AppLifecycleObserver : DefaultLifecycleObserver {
    private val listActivityDisableResume = arrayListOf(
        SplashActivity::class.java, LanguageActivity::class.java,
        OnBoardingActivity::class.java, WelcomeActivity::class.java, SurveyActivity::class.java,
    )

    override fun onStart(owner: LifecycleOwner) {
        val currentActivity = GlobalApp.currentActivity ?: return
        val isDisable = listActivityDisableResume.any { it.isInstance(currentActivity) }
        if (!isDisable && ResumeAdsEntryRule.shouldShowWelcomeOnResume()
            && !AppOpenManager.getInstance().isInterstitialShowing
            && !AppPurchase.getInstance().isPurchased(currentActivity.applicationContext)
            && ERainAd.getInstance().getShouldDisplayInterWelcomeBack(AdRemoteConfig.inter_welcome.enableUaCheck)
        ) {
            Routes.startWelcomeActivity(currentActivity)
        }
    }
}
```

Five gates in order: disabled-screen list → mode → interstitial-not-showing →
not purchased → SDK UA gate.

`GlobalApp.currentActivity` is kept fresh by `AppActivityLifecycleCallbacks`:

```kotlin
override fun onActivityResumed(activity: Activity) { GlobalApp.currentActivity = activity }
override fun onActivityDestroyed(activity: Activity) {
    if (GlobalApp.currentActivity == activity) GlobalApp.currentActivity = null
}
```

Two exclusion lists exist and they are **not** the same:

- `GlobalApp.initAds()` — AppOpen: Splash, Language, OnBoarding, ConfirmUninstall.
- `AppLifecycleObserver` — Welcome routing: Splash, Language, OnBoarding, Welcome, Survey.

## 8. Banner: `BaseActivityWithBanner`

```kotlin
data class BannerConfig(
    val adUnitConfig: AdUnitConfig = AdUnitConfig(id = "", isEnable = false, reloadIntervalSeconds = 0),
    val isCollapse: Boolean = false
)

abstract class BaseActivityWithBanner<VB : ViewDataBinding> : BaseActivity<VB>() {
    private const val DISTANCE_TIME_NEED_CHECK_RELOAD_BANNER = 2000L
    abstract val bannerConfig: BannerConfig

    override fun onCreate(savedInstanceState: Bundle?) { super.onCreate(savedInstanceState); loadBanner() }
    override fun onResume()  { super.onResume(); reloadBannerIfNeeded() }
    override fun onPause()   { cleanupHandler(); super.onPause() }
    override fun onDestroy() { cleanupHandler(); super.onDestroy() }

    private fun shouldShowBanner(): Boolean {
        val isAdEnabled = bannerConfig.adUnitConfig.isEnable && !AppPurchase.getInstance().isPurchased(this)
        return isAdEnabled && findViewById<FrameLayout>(R.id.fr_banner) != null
    }
}
```

A screen opts in by overriding one property:

```kotlin
class MainActivity : BaseActivityWithBanner<ActivityMainBinding>() {
    override val bannerConfig = BannerConfig(AdRemoteConfig.banner_home, true)
}
```

The reload loop polls every 2 s and reloads once `reloadIntervalSeconds` has
elapsed; the handler is torn down in `onPause`/`onDestroy`. A banner that
reloads without that cleanup keeps requesting ads off-screen.

## 9. Native rendering

`populateNativeAdView` resolves CTA height and colour from the loaded ad's own
config, then reorders components per `components`:

```kotlin
fun populateNativeAdView(activity: Activity, apNativeAd: ApNativeAd,
                         adPlaceHolder: FrameLayout, containerShimmerLoading: ShimmerFrameLayout) {
    if (apNativeAd.admobNativeAd == null && apNativeAd.nativeView == null) {
        containerShimmerLoading.visibility = View.GONE
        return
    }
    val config = AdsManager.getAdConfig(apNativeAd)
    val adView = LayoutInflater.from(activity).inflate(apNativeAd.layoutCustomNative, null) as NativeAdView

    containerShimmerLoading.stopShimmer()
    containerShimmerLoading.visibility = View.GONE
    adPlaceHolder.visibility = View.VISIBLE

    adView.findViewById<View>(R.id.ad_call_to_action)?.let { cta ->
        cta.updateLayoutParams { height = (config?.heightCTA ?: 40).coerceIn(36, 52).dpToPx(activity).toInt() }
        applyCtaColor(cta, config?.colorCTA ?: "default")
    }
    // ... component reorder into R.id.ad_container ...
    Admob.getInstance().populateUnifiedNativeAdView(apNativeAd.admobNativeAd, adView)
    adPlaceHolder.removeAllViews()
    adPlaceHolder.addView(adView)
}
```

CTA height is clamped to 36–52 dp regardless of config. Required view ids in a
native layout: `ad_container`, `block_icon_headline`, `ad_body`, `ad_media`,
`ad_call_to_action`, and for flat layouts `ad_app_icon` / `ad_icon` /
`ad_headline` / `ad_advertiser`.

Standard render/hide pattern on every screen:

```kotlin
AdsManager.nativeWelcomeAdLive.observe(this) { ad ->
    if (ad == null || !isNetwork()) { mBinding.frAds.goneView(); return@observe }
    mBinding.frAds.visibleView()
    populateNativeAdView(this, ad, mBinding.frAds, mBinding.shimmerAds.shimmerNativeLarge)
}
```

## 10. Firebase Remote Config keys

```
ad_remote_config                        // full ad_config.json override (release only)
on_show_navigation_button
on_show_dialog_consent
delay_button_done_language
time_delay_show_language_done_button
on_enable_uninstall_widget
force_update_config
```

Defaults are seeded from the bundled `ad_config.json`, so a missing Remote
Config value falls back to the shipped asset rather than disabling ads.
