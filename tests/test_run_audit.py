import json
import io
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from ads_audit_lib import (  # noqa: E402
    Finding,
    build_webhook_payload,
    inspect_project,
    parse_ads_script,
    parse_working_file,
    redact_value,
)
import run_audit  # noqa: E402
import package_skill  # noqa: E402


class AdsAuditTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.ads_csv = self.root / "ads.csv"
        self.working_csv = self.root / "working.csv"
        self.ads_csv.write_text(
            " ,Ads type,Name,ID,Mô tả\n"
            "1,interstitial,inter_splash,ca-app-pub-123/111,Show on splash\n"
            "2,native,native_home,ca-app-pub-123/222,Show in home\n"
            ",,APP ID,ca-app-pub-123~999,\n",
            encoding="utf-8",
        )
        self.working_csv.write_text(
            "Phase,Task,Task Detail,Document\n"
            ",,App name,Demo Player\n"
            ",,Package name,com.example.player\n"
            ",,Adjust token,adjust-secret\n"
            ",,Facebook App ID,facebook-app-id\n"
            ",,Facebook Client token,facebook-client-secret\n"
            ",,Tiktok token,tiktok-secret\n"
            ",,Firebase,https://console.firebase.google.com/project/demo-player/overview\n"
            ",,app-ads.txt,https://example.com/\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_project(self, include_home_config=True):
        (self.root / "app/src/main/java/com/example").mkdir(parents=True)
        (self.root / "app/src/main/assets").mkdir(parents=True)
        (self.root / "app/src/main/res/values").mkdir(parents=True)
        (self.root / "app/build.gradle").write_text(
            'android { namespace "com.example.player"\n defaultConfig { applicationId "com.example.player" }\n'
            ' buildTypes { debug { manifestPlaceholders = [app_id: "ca-app-pub-123~999"] } } }',
            encoding="utf-8",
        )
        (self.root / "app/src/main/AndroidManifest.xml").write_text(
            '<manifest><application android:label="@string/app_name">'
            '<meta-data android:name="com.google.android.gms.ads.APPLICATION_ID" android:value="${app_id}"/>'
            '</application></manifest>',
            encoding="utf-8",
        )
        (self.root / "app/src/main/res/values/strings.xml").write_text(
            '<resources><string name="app_name">Demo Player</string><string name="adjust_token">adjust-secret</string>'
            '<string name="facebook_app_id">facebook-app-id</string><string name="facebook_client_token">facebook-client-secret</string>'
            '<string name="event_token">tiktok-secret</string><string name="policy">https://example.com/</string></resources>',
            encoding="utf-8",
        )
        config = {"inter_splash": {"id": "ca-app-pub-123/111", "isEnable": True}}
        if include_home_config:
            config["native_home"] = {"id": "ca-app-pub-123/222", "isEnable": True}
        for name in ("ad_config.json", "ad_config_debug.json"):
            (self.root / "app/src/main/assets" / name).write_text(json.dumps(config), encoding="utf-8")
        (self.root / "app/src/main/java/com/example/GlobalApp.kt").write_text(
            "MobileAds.initialize(this)\nAdRemoteConfig.initializeFromAssets(this)\nERainAd.getInstance().init(this, config)\n",
            encoding="utf-8",
        )
        (self.root / "app/src/main/java/com/example/AdsManager.kt").write_text(
            "object AdsManager { fun loadNativeHome() { ERainAd.getInstance().loadNativeAdResultCallback() } }\n",
            encoding="utf-8",
        )
        (self.root / "app/src/main/java/com/example/SplashActivity.kt").write_text(
            "AdsManager.loadSplash()\nERainAd.getInstance().loadSplashInterstitialAds()\n",
            encoding="utf-8",
        )
        (self.root / "google-services.json").write_text(
            '{"project_info":{"project_id":"demo-player"}}', encoding="utf-8"
        )

    def write_full_base_flow_project(self):
        self.write_project()
        java_dir = self.root / "app/src/main/java/com/example"
        (self.root / "app/src/main/res/navigation").mkdir(parents=True, exist_ok=True)
        (self.root / "app/build.gradle").write_text(
            'android { namespace "com.example.player"\n defaultConfig { applicationId "com.example.player" }\n'
            ' buildTypes { debug { manifestPlaceholders = [app_id: "ca-app-pub-123~999"]\n'
            ' buildConfigField "String", "ERAIN_STUDIO_VERSION", "\\"1.0\\""\n'
            ' buildConfigField "String", "PLAY_SERVICES_ADS_VERSION", "\\"23.0\\""\n'
            ' buildConfigField "String", "GDPR_MODULE_VERSION", "\\"2.0\\"" }\n'
            ' release { manifestPlaceholders = [app_id: "ca-app-pub-123~999"]\n'
            ' buildConfigField "String", "ERAIN_STUDIO_VERSION", "\\"1.0\\""\n'
            ' buildConfigField "String", "PLAY_SERVICES_ADS_VERSION", "\\"23.0\\""\n'
            ' buildConfigField "String", "GDPR_MODULE_VERSION", "\\"2.0\\"" } } }',
            encoding="utf-8",
        )
        (self.root / "app/src/main/AndroidManifest.xml").write_text(
            '<manifest><application android:label="@string/app_name">'
            '<activity android:name=".SplashActivity"/><activity android:name=".LanguageActivity"/>'
            '<activity android:name=".OnBoardingActivity"/><activity android:name=".MainActivity"/>'
            '<activity android:name=".WelcomeActivity"/>'
            '<meta-data android:name="com.google.android.gms.ads.APPLICATION_ID" android:value="${app_id}"/>'
            '</application></manifest>',
            encoding="utf-8",
        )
        (java_dir / "GlobalApp.kt").write_text(
            "class GlobalApp { fun onCreate() { "
            "MobileAds.initialize(this){}; "
            "DevConfig.init(context = this, nkhStudioVersion = BuildConfig.ERAIN_STUDIO_VERSION, "
            "playServicesAdsVersion = BuildConfig.PLAY_SERVICES_ADS_VERSION, gdprModuleVersion = BuildConfig.GDPR_MODULE_VERSION); "
            "initAdRemoteConfig(); initAds(); "
            "ProcessLifecycleOwner.get().lifecycle.addObserver(AppLifecycleObserver()); "
            "registerActivityLifecycleCallbacks(AppActivityLifecycleCallbacks()) } "
            "fun initAdRemoteConfig(){ AdRemoteConfig.initializeFromAssets(this) } "
            "fun initAds(){ val environment = if (BuildConfig.DEBUG) ERainAdConfig.ENVIRONMENT_DEVELOP else ERainAdConfig.ENVIRONMENT_PRODUCTION; "
            "mERainAdConfig = ERainAdConfig(this, environment); "
            "mERainAdConfig.adjustConfig = AdjustConfig(true, resources.getString(R.string.adjust_token)); "
            "mERainAdConfig.facebookClientToken = resources.getString(R.string.facebook_client_token); "
            "mERainAdConfig.adjustTokenTiktok = resources.getString(R.string.event_token); "
            "mERainAdConfig.intervalInterstitialAd = 35; mERainAdConfig.idAdResume = \"\"; "
            "ERainAd.getInstance().init(this, mERainAdConfig); "
            "Admob.getInstance().setDisableAdResumeWhenClickAds(true); "
            "Admob.getInstance().setOpenActivityAfterShowInterAds(true); "
            "AppOpenManager.getInstance().disableAppResumeWithActivity(SplashActivity::class.java); "
            "AppOpenManager.getInstance().disableAppResumeWithActivity(LanguageActivity::class.java); "
            "AppOpenManager.getInstance().disableAppResumeWithActivity(OnBoardingActivity::class.java); "
            "AppOpenManager.getInstance().disableAppResumeWithActivity(WelcomeActivity::class.java) } }",
            encoding="utf-8",
        )
        (java_dir / "AdsManager.kt").write_text(
            "object AdsManager { "
            "val nativeLanguageAdLive = MutableLiveData<ApNativeAd?>(); val nativeLanguageClickAdLive = MutableLiveData<ApNativeAd?>(); "
            "val nativeOnboarding1AdLive = MutableLiveData<ApNativeAd?>(); val nativeOnboarding4AdLive = MutableLiveData<ApNativeAd?>(); "
            "val nativeAdOnBoardingFullLive = MutableLiveData<ApNativeAd?>(); val nativeWelcomeAdLive = MutableLiveData<ApNativeAd?>(); "
            "val nativeHomeAdLive = MutableLiveData<ApNativeAd?>(); private var interOnboarding: ApInterstitialAd? = null; private var interWelcomeAd: ApInterstitialAd? = null; "
            "fun loadNativeInternal(activity: Activity, config: AdUnitConfig, layoutRes: Int, liveData: MutableLiveData<ApNativeAd?>, shouldDisplay: Boolean = true) { "
            "if (!config.isEnable || AppPurchase.getInstance().isPurchased(activity) || !activity.isNetworkAvailable() || !shouldDisplay) { liveData.postValue(null); return }; "
            "ERainAd.getInstance().loadNativeAdResultCallback(activity, config.id, layoutRes, object: AdCallback(){ override fun onNativeAdLoaded(nativeAd: ApNativeAd){ liveData.postValue(nativeAd) }; override fun onAdFailedToLoad(e: LoadAdError?){ liveData.postValue(null) } }) } "
            "fun loadNativeLanguage(a: Activity, first: Boolean, r: Int){ val config = if(first) AdRemoteConfig.native_language_1 else AdRemoteConfig.native_language_2; loadNativeInternal(a, config, r, nativeLanguageAdLive) } "
            "fun loadNativeLanguageClick(a: Activity, first: Boolean, r: Int){ val config = if(first) AdRemoteConfig.native_language_1_click else AdRemoteConfig.native_language_2_click; loadNativeInternal(a, config, r, nativeLanguageClickAdLive) } "
            "fun loadNativeOnboarding1(a: Activity, first: Boolean, r: Int){ val config = if(first) AdRemoteConfig.native_onboarding_1_1 else AdRemoteConfig.native_onboarding_2_1; loadNativeInternal(a, config, r, nativeOnboarding1AdLive) } "
            "fun loadNativeOnboarding4(a: Activity, first: Boolean, r: Int){ val config = if(first) AdRemoteConfig.native_onboarding_1_4 else AdRemoteConfig.native_onboarding_2_4; loadNativeInternal(a, config, r, nativeOnboarding4AdLive, ERainAd.getInstance().getShouldDisplayNativeOnboardingNormal2(config.enableUaCheck)) } "
            "fun loadNativeOnboardingFull(a: Activity, first: Boolean, r: Int){ val config = if(first) AdRemoteConfig.native_onboarding_fullscreen_1_3 else AdRemoteConfig.native_onboarding_fullscreen_2_3; loadNativeInternal(a, config, r, nativeAdOnBoardingFullLive, ERainAd.getInstance().getShouldDisplayNativeOnboardingFull1(config.enableUaCheck)) } "
            "fun loadNativeHome(a: Activity, r: Int){ val config = AdRemoteConfig.native_home; loadNativeInternal(a, config, r, nativeHomeAdLive, ERainAd.getInstance().getShouldDisplayNativeHome(config.enableUaCheck)) } "
            "fun loadNativeWelcome(a: Activity, r: Int){ loadNativeInternal(a, AdRemoteConfig.native_welcome, r, nativeWelcomeAdLive, ERainAd.getInstance().getShouldDisplayNativeWelcomeBack(AdRemoteConfig.native_welcome.enableUaCheck)) } "
            "fun loadInterOnboarding(context: Context, ignoreLimit: Boolean = false){ val config = AdRemoteConfig.inter_onboarding; if (!config.isEnable || AppPurchase.getInstance().isPurchased(context) || (!ignoreLimit && !ERainAd.getInstance().getShouldDisplayInterOnboarding(config.enableUaCheck))) { interOnboarding = null; return }; interOnboarding = ERainAd.getInstance().getInterstitialAds(context, config.id, object: AdCallback(){}) } "
            "fun showInterOnboarding(context: Context, ignoreLimit: Boolean = false, onAction: () -> Unit){ val interstitial = interOnboarding; if (interstitial != null && interstitial.isReady && !AppPurchase.getInstance().isPurchased(context) && (ignoreLimit || ERainAd.getInstance().getShouldDisplayInterOnboarding(AdRemoteConfig.inter_onboarding.enableUaCheck))) { ERainAd.getInstance().forceShowInterstitial(context, interstitial, object: AdCallback(){ override fun onNextAction(){ onAction() } }, true) } else onAction() } "
            "fun loadInterWelcome(context: Context, ignoreLimit: Boolean = false){ val config = AdRemoteConfig.inter_welcome; if (!config.isEnable || AppPurchase.getInstance().isPurchased(context) || (!ignoreLimit && !ERainAd.getInstance().getShouldDisplayInterWelcomeBack(config.enableUaCheck))) { interWelcomeAd = null; return }; interWelcomeAd = ERainAd.getInstance().getInterstitialAds(context, config.id, object: AdCallback(){}) } "
            "fun showInterWelcome(context: Context, ignoreLimit: Boolean = false, onAction: () -> Unit){ val interstitial = interWelcomeAd; if (interstitial != null && interstitial.isReady && !AppPurchase.getInstance().isPurchased(context) && (ignoreLimit || ERainAd.getInstance().getShouldDisplayInterWelcomeBack(AdRemoteConfig.inter_welcome.enableUaCheck))) { ERainAd.getInstance().forceShowInterstitial(context, interstitial, object: AdCallback(){ override fun onNextAction(){ onAction() } }, false) } else onAction() } "
            "fun loadBanner(activity: AppCompatActivity, adUnitConfig: AdUnitConfig, frAds: FrameLayout, isCollapse: Boolean){ if(adUnitConfig.isEnable){ if(isCollapse) ERainAd.getInstance().loadCollapsibleBanner(activity, adUnitConfig.id, AppConstant.CollapsibleGravity.BOTTOM, object: AdCallback(){}) else ERainAd.getInstance().loadBanner(activity, adUnitConfig.id, object: AdCallback(){}) } else { frAds.removeAllViews(); frAds.goneView() } } }",
            encoding="utf-8",
        )
        (java_dir / "SplashActivity.kt").write_text(
            "class SplashActivity { fun initViews(){ RemoteConfigUtils.init(this,this); consentHandler = ConsentHandler(onConsentFlowCompleted = { loadingRemoteConfig() }); loadingRemoteConfig() } "
            "fun checkRemoteConfigResult(){ AdRemoteConfig.initialize(this, RemoteConfigUtils.getAdRemoteConfig()); if (AdRemoteConfig.inter_splash.isEnable && isNetwork(this)) { ERainAd.getInstance().loadSplashInterstitialAds(this, AdRemoteConfig.inter_splash.id, 30000, 5000, object: AdCallback(){ override fun onNextAction(){ moveActivity() }; override fun onAdLoaded(){ loadNativeLanguage(this@SplashActivity, appSharedPref.firstLanguage, R.layout.layout_native_language) } }) } else moveActivity(); "
            "if (ResumeAdsEntryRule.shouldEnableOpenResume()) { AppOpenManager.getInstance().setAppResumeAdId(AdRemoteConfig.open_resume.id); AppOpenManager.getInstance().enableAppResume() } else AppOpenManager.getInstance().disableAppResume() } "
            "fun onResume(){ ERainAd.getInstance().onCheckShowSplashWhenFail(this, object: AdCallback(){ override fun onNextAction(){ moveActivity() } }, 1000) } fun moveActivity(){ Routes.startLanguageActivity(this, null); Routes.startMainActivity(this) } }",
            encoding="utf-8",
        )
        (java_dir / "LanguageActivity.kt").write_text(
            "class LanguageActivity { fun initViews(){ mBinding.tvTitle.setOnAdminAdToggleListener(){ Routes.startSplashActivity(this) }; mBinding.root.postDelayed({ loadNativeLanguageClick(this, appSharedPref.firstLanguage, R.layout.layout_native_language_click); initAds() }, 100L) } "
            "fun initAds(){ if (fromSetting) mBinding.flAds.goneView() else AdsManager.loadNativeOnboarding1(this, appSharedPref.firstOnBoarding, R.layout.layout_native_onboarding) } "
            "fun listenLanguageAd(){ AdsManager.nativeLanguageClickAdLive.removeObservers(this); AdsManager.nativeLanguageAdLive.observe(this){ ad -> if(ad != null) showNativeLanguage(ad) else mBinding.flAds.goneView() } } "
            "fun listenLanguageClickAd(){ AdsManager.nativeLanguageAdLive.removeObservers(this); AdsManager.nativeLanguageClickAdLive.observe(this){ ad -> if(ad != null) showNativeLanguage(ad) else mBinding.flAds.goneView() } } "
            "fun showNativeLanguage(ad: ApNativeAd){ if(!isNetwork()){ mBinding.flAds.goneView(); return }; populateNativeAdView(this, ad, mBinding.flAds, mBinding.shimmerAds.shimmerNativeSmall) } "
            "fun startNextActivity(){ appSharedPref.firstLanguage = false; Routes.startOnBoardingActivity(this); Routes.startMainActivity(this) } }",
            encoding="utf-8",
        )
        (java_dir / "OnBoardingActivity.kt").write_text(
            "class OnBoardingActivity { fun initViews(){ initPage(); initOnboardingItems(); applyUninstallWidgetShortcutsFromRemoteConfig(); mBinding.root.postDelayed({ AdsManager.loadNativeOnboarding4(this, appSharedPref.firstOnBoarding, R.layout.layout_native_onboarding); AdsManager.loadNativeOnboardingFull(this, appSharedPref.firstOnBoarding, R.layout.layout_native_onboarding_full); AdsManager.loadInterOnboarding(this) }, 100L) } "
            "fun applyUninstallWidgetShortcutsFromRemoteConfig(){ ERainAd.getInstance().getShouldDisplayWidgetUninstall(RemoteConfigUtils.getOnEnableUninstallWidget()); ShortcutManager.initShortCut(this) } "
            "fun initOnboardingItems(){ onboardingItems.add(OnboardingItem(isHasNativeOnPage1 = true)); if (isNetwork(this) && ERainAd.getInstance().getShouldDisplayNativeOnboardingFull1(AdRemoteConfig.native_onboarding_fullscreen_1_3.enableUaCheck)) onboardingItems.add(OnboardingItem(isHasNativeFull = true)); onboardingItems.add(OnboardingItem(isHasNativeOnPage4 = true)); onboardingAdapter.submitData(onboardingItems) } "
            "fun startNextActivity(){ appSharedPref.firstOnBoarding = false; AdsManager.showInterOnboarding(this){ Routes.startMainActivity(this); finish() } } }",
            encoding="utf-8",
        )
        (java_dir / "OnboardingPageFragment.kt").write_text(
            "class OnboardingPageFragment { fun observeAdChannel(){ val liveData = when { onboardingItem.isHasNativeOnPage1 -> AdsManager.nativeOnboarding1AdLive; onboardingItem.isHasNativeOnPage4 -> AdsManager.nativeOnboarding4AdLive; onboardingItem.isHasNativeFull -> AdsManager.nativeAdOnBoardingFullLive; else -> return }; liveData.observe(viewLifecycleOwner){ ad -> renderAd(ad) } } "
            "fun renderAd(ad: ApNativeAd?){ if(ad != null){ populateNativeAdView(requireActivity(), ad, mBinding.layoutAds, mBinding.shimmerAds.shimmerNativeMedium) } else { mBinding.layoutAds.invisibleView(); mBinding.layoutAdsFull.invisibleView() } } }",
            encoding="utf-8",
        )
        (java_dir / "WelcomeActivity.kt").write_text(
            "class WelcomeActivity { fun initViews(){ AdsManager.loadNativeWelcome(this, R.layout.layout_native_welcome); AdsManager.loadInterWelcome(this) } "
            "fun observerData(){ AdsManager.nativeWelcomeAdLive.observe(this){ ad -> renderWelcomeAd(ad) } } "
            "fun onClickViews(){ mBinding.btnStart.click { AdsManager.showInterWelcome(this){ finish() } } } "
            "fun renderWelcomeAd(ad: ApNativeAd?){ if(ad == null || !isNetwork()){ mBinding.frAds.goneView(); return }; populateNativeAdView(this, ad, mBinding.frAds, mBinding.shimmerAds.shimmerNativeLarge) } }",
            encoding="utf-8",
        )
        (java_dir / "AppLifecycleObserver.kt").write_text(
            "class AppLifecycleObserver { val listActivityDisableResume = arrayListOf(SplashActivity::class.java, LanguageActivity::class.java, OnBoardingActivity::class.java, WelcomeActivity::class.java, SurveyActivity::class.java); "
            "fun onStart(){ val currentActivity = GlobalApp.currentActivity; if(currentActivity != null){ val isDisable = listActivityDisableResume.any { clazz -> clazz.isInstance(currentActivity) }; "
            "if(!isDisable && ResumeAdsEntryRule.shouldShowWelcomeOnResume() && !AppOpenManager.getInstance().isInterstitialShowing && !AppPurchase.getInstance().isPurchased(currentActivity.applicationContext) && ERainAd.getInstance().getShouldDisplayInterWelcomeBack(AdRemoteConfig.inter_welcome.enableUaCheck)) { Routes.startWelcomeActivity(currentActivity) } } } }",
            encoding="utf-8",
        )
        (java_dir / "ResumeAdsEntryRule.kt").write_text(
            "object ResumeAdsEntryRule { fun currentMode(){ AdRemoteConfig.isInitialized(); AdRemoteConfig.open_resume.isEnable; AdRemoteConfig.native_welcome.isEnable; AdRemoteConfig.inter_welcome.isEnable } fun shouldEnableOpenResume() = currentMode() == ResumeAdsEntryMode.OPEN_RESUME; fun shouldShowWelcomeOnResume() = currentMode() == ResumeAdsEntryMode.WELCOME && !AdRemoteConfig.open_resume.isEnable }",
            encoding="utf-8",
        )
        (java_dir / "BaseActivityWithBanner.kt").write_text(
            "abstract class BaseActivityWithBanner<VB: ViewDataBinding>: BaseActivity<VB>() { abstract val bannerConfig: BannerConfig; private var reloadBannerHandler: Handler? = null; private var timeNeedReloadBanner = 0L; "
            "override fun onCreate(savedInstanceState: Bundle?){ super.onCreate(savedInstanceState); loadBanner() }; override fun onResume(){ super.onResume(); reloadBannerIfNeeded() }; "
            "fun loadBanner(){ val frAds = findViewById<FrameLayout>(R.id.fr_banner); if(!shouldShowBanner()){ frAds?.goneView(); cleanupHandler(); return }; AdsManager.loadBanner(this, bannerConfig.adUnitConfig, frAds, bannerConfig.isCollapse); val distanceReloadBanner = bannerConfig.adUnitConfig.reloadIntervalSeconds ?: 0; timeNeedReloadBanner = System.currentTimeMillis() + distanceReloadBanner * 1000L } "
            "fun reloadBannerIfNeeded(){ if(shouldReloadBanner()){ reloadBannerHandler = Handler(Looper.getMainLooper()); reloadBannerHandler?.postDelayed(reloadBannerRunnable, DISTANCE_TIME_NEED_CHECK_RELOAD_BANNER) } else cleanupHandler() } "
            "fun shouldShowBanner(): Boolean { return bannerConfig.adUnitConfig.isEnable && !AppPurchase.getInstance().isPurchased(this) && findViewById<FrameLayout>(R.id.fr_banner) != null } "
            "fun shouldReloadBanner(): Boolean { val distanceReloadBanner = bannerConfig.adUnitConfig.reloadIntervalSeconds ?: 0; return shouldShowBanner() && distanceReloadBanner > 0 } fun cleanupHandler(){ reloadBannerHandler?.removeCallbacksAndMessages(null) } }",
            encoding="utf-8",
        )

    def test_parses_contract_and_project_checklist(self):
        contract = parse_ads_script(self.ads_csv)
        checklist = parse_working_file(self.working_csv)

        self.assertEqual(contract.admob_app_id, "ca-app-pub-123~999")
        self.assertEqual(contract.placements["native_home"].ad_unit_id, "ca-app-pub-123/222")
        self.assertEqual(checklist.package_name, "com.example.player")
        self.assertEqual(checklist.required_values["Adjust token"], "adjust-secret")

    def test_parses_partner_csv_with_preamble_semicolon_and_alias_headers(self):
        partner_csv = self.root / "partner-semicolon.csv"
        partner_csv.write_text(
            "Exported by partner;2026-08-14\n"
            "Loại quảng cáo;Tên vị trí;Ad Unit ID;Mô tả\n"
            "interstitial;inter_splash;ca-app-pub-123/333;Splash placement\n"
            "native;native_home;ca-app-pub-123/444;Home placement\n"
            ";APP ID;ca-app-pub-123~999;\n",
            encoding="utf-8",
        )

        contract = parse_ads_script(partner_csv)

        self.assertEqual(contract.admob_app_id, "ca-app-pub-123~999")
        self.assertEqual(contract.placements["native_home"].ad_unit_id, "ca-app-pub-123/444")

    def test_infers_unnamed_ad_unit_id_column_without_confusing_serial_column(self):
        partner_csv = self.root / "partner-unnamed-id.csv"
        partner_csv.write_text(
            " ,Ads type,Name,,Mô tả,Des\n"
            "1,interstitial,inter_splash,ca-app-pub-123/555,Splash placement,\n"
            "2,native,native_home,ca-app-pub-123/666,Home placement,\n"
            ",,APP ID,ca-app-pub-123~999,,\n",
            encoding="utf-8",
        )

        contract = parse_ads_script(partner_csv)

        self.assertEqual(contract.placements["inter_splash"].ad_unit_id, "ca-app-pub-123/555")
        self.assertEqual(contract.admob_app_id, "ca-app-pub-123~999")

    def test_parses_google_sheet_working_file_content_and_detail_columns(self):
        working = self.root / "google-sheet-working.csv"
        working.write_text(
            "Order,Content,Detail,PIC\n"
            "1,App name,Partner Player,Alice\n"
            "2,Package name,com.partner.player,Bob\n"
            "3,Firebase,https://console.firebase.google.com/project/partner-player/overview,Carol\n",
            encoding="utf-8",
        )

        checklist = parse_working_file(working)

        self.assertEqual(checklist.app_name, "Partner Player")
        self.assertEqual(checklist.package_name, "com.partner.player")
        self.assertEqual(checklist.firebase_project, "partner-player")

    def test_infers_unknown_working_headers_from_recognized_row_content(self):
        working = self.root / "renamed-working.csv"
        working.write_text(
            "Exported partner checklist\n"
            "Row,Column A,Column B,Owner\n"
            "1,Application name,Partner Player,Alice\n"
            "2,Bundle ID,com.partner.player,Bob\n"
            "3,Firebase project,https://console.firebase.google.com/project/partner-player/overview,Carol\n",
            encoding="utf-8",
        )

        checklist = parse_working_file(working)

        self.assertEqual(checklist.app_name, "Partner Player")
        self.assertEqual(checklist.package_name, "com.partner.player")
        self.assertEqual(checklist.firebase_project, "partner-player")

    def test_parses_reordered_ads_sheet_with_partner_aliases(self):
        partner_csv = self.root / "partner-alias-ads.csv"
        partner_csv.write_text(
            "Notes,Unit Code,Format,Ads Key,Sequence\n"
            "Splash,ca-app-pub-123/555,interstitial,inter_splash,1\n"
            "Home,ca-app-pub-123/666,native,native_home,2\n"
            "Application,ca-app-pub-123~999,app,APP ID,3\n",
            encoding="utf-8",
        )

        contract = parse_ads_script(partner_csv)

        self.assertEqual(contract.placements["inter_splash"].ad_unit_id, "ca-app-pub-123/555")
        self.assertEqual(contract.placements["native_home"].ad_type, "native")
        self.assertEqual(contract.admob_app_id, "ca-app-pub-123~999")

    def test_infers_ads_columns_when_all_headers_are_unknown(self):
        partner_csv = self.root / "partner-inferred-ads.csv"
        partner_csv.write_text(
            "Column A,Column B,Column C,Column D,Column E\n"
            "Splash,ca-app-pub-123/555,interstitial,inter_splash,1\n"
            "Home,ca-app-pub-123/666,native,native_home,2\n"
            "Application,ca-app-pub-123~999,app,APP ID,3\n",
            encoding="utf-8",
        )

        contract = parse_ads_script(partner_csv)

        self.assertEqual(contract.placements["inter_splash"].ad_unit_id, "ca-app-pub-123/555")
        self.assertEqual(contract.placements["native_home"].ad_type, "native")
        self.assertEqual(contract.admob_app_id, "ca-app-pub-123~999")

    def test_rejects_ambiguous_working_value_columns_with_header_diagnostics(self):
        working = self.root / "ambiguous-working.csv"
        working.write_text(
            "Alpha,Beta,Gamma\n"
            "App name,Primary Player,Backup Player\n"
            "Package name,com.primary.player,com.backup.player\n"
            "Firebase,https://console.firebase.google.com/project/primary/overview,https://console.firebase.google.com/project/backup/overview\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "Alpha.*Beta.*Gamma"):
            parse_working_file(working)

    def test_redacts_secret_values_and_payload_never_contains_them(self):
        redacted = redact_value("facebook-client-secret")
        payload = build_webhook_payload(
            project_name="Demo",
            findings=[Finding.fail("TOKEN", "token", "facebook-client-secret", "missing", "fix")],
        )

        self.assertNotEqual(redacted, "facebook-client-secret")
        self.assertNotIn("facebook-client-secret", json.dumps(payload))
        self.assertEqual(payload["tong_quan"]["loi_can_sua"], 1)

    def test_passes_exact_identity_config_and_required_service_evidence(self):
        self.write_project()
        report = inspect_project(self.root, parse_ads_script(self.ads_csv), parse_working_file(self.working_csv))

        self.assertEqual(report.finding("APP_PACKAGE").status, "PASS")
        self.assertEqual(report.finding("ADMOB_APP_ID").status, "PASS")
        self.assertEqual(report.finding("AD_CONFIG_RELEASE:native_home").status, "PASS")
        self.assertEqual(report.finding("TOKEN:Adjust token").status, "PASS")
        self.assertEqual(report.finding("FIREBASE_PROJECT").status, "PASS")

    def test_flags_missing_placement_config_with_exact_rule_id(self):
        self.write_project(include_home_config=False)
        report = inspect_project(self.root, parse_ads_script(self.ads_csv), parse_working_file(self.working_csv))

        self.assertEqual(report.finding("AD_CONFIG_RELEASE:native_home").status, "FAIL")
        self.assertFalse(any(finding.rule_id.startswith("AD_CONFIG_DEBUG:") for finding in report.findings))

    def test_ignores_debug_config_id_difference(self):
        self.write_project()
        debug_path = self.root / "app/src/main/assets/ad_config_debug.json"
        debug_config = json.loads(debug_path.read_text(encoding="utf-8"))
        debug_config["native_home"]["id"] = "ca-app-pub-test/debug-only"
        debug_path.write_text(json.dumps(debug_config), encoding="utf-8")

        report = inspect_project(self.root, parse_ads_script(self.ads_csv), parse_working_file(self.working_csv))

        self.assertEqual(report.finding("AD_CONFIG_RELEASE:native_home").status, "PASS")
        self.assertFalse(any(finding.rule_id.startswith("AD_CONFIG_DEBUG:") for finding in report.findings))

    def test_uses_default_locale_app_name_instead_of_localized_translation(self):
        localized_dir = self.root / "app/src/main/res/values-vi"
        localized_dir.mkdir(parents=True)
        (localized_dir / "strings.xml").write_text(
            '<resources><string name="app_name">IPTV Smart Player</string></resources>',
            encoding="utf-8",
        )
        self.write_project()
        self.working_csv.write_text(
            self.working_csv.read_text(encoding="utf-8").replace("Demo Player", "Demo & Player"),
            encoding="utf-8",
        )
        (self.root / "app/src/main/res/values/strings.xml").write_text(
            '<resources><string name="app_name">Demo &amp; Player</string></resources>',
            encoding="utf-8",
        )

        report = inspect_project(self.root, parse_ads_script(self.ads_csv), parse_working_file(self.working_csv))

        self.assertEqual(report.finding("APP_NAME").status, "PASS")

    def test_webhook_identity_error_includes_expected_and_observed_values(self):
        checklist = parse_working_file(self.working_csv)
        payload = build_webhook_payload(
            "repo-folder",
            checklist,
            [
                Finding.fail("APP_NAME", "identity", "Demo Player", "Actual Player", "fix"),
                Finding.fail("APP_PACKAGE", "identity", "com.expected.player", "com.actual.player", "fix"),
            ],
        )

        description = payload["loi"][0]["mo_ta"]
        self.assertIn("expected `Demo Player`", description)
        self.assertIn("observed `Actual Player`", description)
        self.assertIn("expected `com.expected.player`", description)
        self.assertIn("observed `com.actual.player`", description)

    def test_marks_unmapped_placement_location_without_claiming_pass(self):
        self.write_project()
        self.ads_csv.write_text(
            self.ads_csv.read_text(encoding="utf-8").replace(
                ",,APP ID,ca-app-pub-123~999,\n",
                "3,interstitial,inter_partner_feature,ca-app-pub-123/333,Show on a partner feature\n"
                ",,APP ID,ca-app-pub-123~999,\n",
            ),
            encoding="utf-8",
        )
        report = inspect_project(self.root, parse_ads_script(self.ads_csv), parse_working_file(self.working_csv))

        self.assertEqual(report.finding("PLACEMENT_FLOW:inter_partner_feature").status, "NEEDS_MAPPING")

    def test_cli_writes_sanitized_reports_even_when_audit_fails(self):
        self.write_project()
        output_dir = self.root / "audit-output"
        script = SCRIPTS_DIR / "run_audit.py"

        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--project",
                str(self.root),
                "--ads-script",
                str(self.ads_csv),
                "--working-file",
                str(self.working_csv),
                "--output-dir",
                str(output_dir),
                "--no-webhook",
            ],
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 2)
        self.assertTrue((output_dir / "ads-audit-summary.md").is_file())
        evidence = (output_dir / "ads-audit-evidence.json").read_text(encoding="utf-8")
        self.assertNotIn("facebook-client-secret", evidence)

    def test_python_cli_auto_discovers_csv_inputs(self):
        self.write_project()
        config_dir = self.root / "partner-config"
        config_dir.mkdir()
        discovered_ads = config_dir / "Partner ADS SCRIPTS.csv"
        discovered_ads.write_text(self.ads_csv.read_text(encoding="utf-8"), encoding="utf-8")
        output_dir = self.root / "auto-audit-output"

        result = run_audit.main([
            "--project", str(self.root),
            "--output-dir", str(output_dir),
            "--no-webhook",
        ])

        self.assertEqual(result, 2)
        self.assertTrue((output_dir / "ads-audit-summary.md").is_file())

    def test_python_cli_rejects_ambiguous_csv_discovery(self):
        first = self.root / "First ADS SCRIPTS.csv"
        second = self.root / "Second ADS SCRIPTS.csv"
        first.write_text(self.ads_csv.read_text(encoding="utf-8"), encoding="utf-8")
        second.write_text(self.ads_csv.read_text(encoding="utf-8"), encoding="utf-8")
        stderr = io.StringIO()

        with patch("sys.stderr", stderr):
            result = run_audit.main([
                "--project", str(self.root),
                "--working-file", str(self.working_csv),
                "--output-dir", str(self.root / "audit-output"),
                "--no-webhook",
            ])

        self.assertEqual(result, 1)
        self.assertIn("--ads-script", stderr.getvalue())
        self.assertIn(first.name, stderr.getvalue())
        self.assertIn(second.name, stderr.getvalue())

    def test_python_cli_explicit_csv_path_overrides_discovery(self):
        duplicate = self.root / "Duplicate ADS SCRIPTS.csv"
        duplicate.write_text(self.ads_csv.read_text(encoding="utf-8"), encoding="utf-8")

        resolved = run_audit.resolve_csv_input(self.root, str(self.ads_csv), "ads")

        self.assertEqual(resolved, self.ads_csv.resolve())

    def test_cli_posts_to_embedded_webhook_by_default(self):
        self.write_project()
        output_dir = self.root / "audit-output"
        with patch.object(run_audit, "post_webhook", return_value=None) as post:
            result = run_audit.main([
                "--project", str(self.root),
                "--ads-script", str(self.ads_csv),
                "--working-file", str(self.working_csv),
                "--output-dir", str(output_dir),
            ])

        self.assertEqual(result, 2)
        self.assertGreaterEqual(post.call_count, 1)
        self.assertEqual(post.call_args_list[0].args[0], run_audit.DEFAULT_WEBHOOK_URL)
        discord_body = post.call_args_list[0].args[2]
        self.assertEqual(
            post.call_args_list[0].kwargs["attachment_path"].resolve(),
            (output_dir / "ads-audit-summary.md").resolve(),
        )
        for call in post.call_args_list[1:]:
            self.assertIsNone(call.kwargs["attachment_path"])
        self.assertIn("content", discord_body)
        self.assertIn("Demo Player", discord_body["content"])
        self.assertIn("com.example.player", discord_body["content"])
        self.assertNotIn("adjust-secret", discord_body["content"])
        summary = (output_dir / "ads-audit-summary.md").read_text(encoding="utf-8")
        self.assertNotIn("WEBHOOK_DELIVERY", summary)

    def test_cli_does_not_post_when_no_webhook_is_requested(self):
        self.write_project()
        with patch.object(run_audit, "post_webhook", return_value=None) as post:
            run_audit.main([
                "--project", str(self.root),
                "--ads-script", str(self.ads_csv),
                "--working-file", str(self.working_csv),
                "--output-dir", str(self.root / "audit-output"),
                "--no-webhook",
            ])

        post.assert_not_called()

    def test_webhook_url_adds_wait_parameter_without_leaking_credentials(self):
        url = "https://example.test/hook/secret"
        token = "bearer-secret"
        payload = {"content": "Báo cáo tiếng Việt", "allowed_mentions": {"parse": []}}
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"200\n", stderr=b"")
        with patch.object(run_audit.subprocess, "run", return_value=completed) as run:
            result = run_audit.post_webhook(url, token, payload)

        self.assertIsNone(result)
        command = run.call_args.args[0]
        self.assertIn(url + "?wait=true", command)
        self.assertIn("Authorization: Bearer " + token, command)
        self.assertEqual(run.call_args.kwargs["input"].decode("utf-8"), json.dumps(payload, ensure_ascii=False))

    def test_webhook_url_appends_wait_parameter_to_existing_query(self):
        url = "https://example.test/hook?thread_id=123"
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"204", stderr=b"")
        with patch.object(run_audit.subprocess, "run", return_value=completed) as run:
            result = run_audit.post_webhook(url, None, {"content": "ok"})

        self.assertIsNone(result)
        self.assertIn(url + "&wait=true", run.call_args.args[0])

    def test_webhook_http_error_and_process_failures_are_sanitized(self):
        url = "https://example.test/hook/secret"
        token = "bearer-secret"
        with patch.object(run_audit.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"403", b"forbidden")):
            result = run_audit.post_webhook(url, token, {"content": "x"})
        self.assertEqual(result, "HTTP 403")
        self.assertNotIn("secret", result)

        with patch.object(run_audit.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(run_audit.post_webhook(url, token, {}), "curl is not installed")
        with patch.object(run_audit.subprocess, "run", side_effect=subprocess.TimeoutExpired("curl", 10)):
            self.assertEqual(run_audit.post_webhook(url, token, {}), "curl timed out")
        with patch.object(run_audit.subprocess, "run", return_value=subprocess.CompletedProcess([], 7, b"", b"contains secret")):
            result = run_audit.post_webhook(url, token, {})
        self.assertEqual(result, "curl exited with code 7")
        self.assertNotIn("secret", result)

    def test_approved_override_proves_a_custom_csv_placement(self):
        self.write_project()
        (self.root / "app/src/main/java/com/example/PartnerFeatureActivity.kt").write_text(
            "class PartnerFeatureActivity { fun onClick() { AdsManager.showInterPartnerFeature() } }",
            encoding="utf-8",
        )
        self.ads_csv.write_text(
            self.ads_csv.read_text(encoding="utf-8").replace(
                ",,APP ID,ca-app-pub-123~999,\n",
                "3,interstitial,inter_partner_feature,ca-app-pub-123/333,Show on a partner feature\n"
                ",,APP ID,ca-app-pub-123~999,\n",
            ),
            encoding="utf-8",
        )
        overrides = self.root / "ads-audit-overrides.yaml"
        overrides.write_text(
            "placements:\n  inter_partner_feature:\n    class: PartnerFeatureActivity\n    show_call: AdsManager.showInterPartnerFeature\n",
            encoding="utf-8",
        )

        report = inspect_project(
            self.root,
            parse_ads_script(self.ads_csv),
            parse_working_file(self.working_csv),
            overrides_path=overrides,
        )

        self.assertEqual(report.finding("PLACEMENT_FLOW:inter_partner_feature").status, "PASS")

    def test_detects_interstitial_show_that_requires_debug_only_ignore_limit(self):
        self.write_project()
        manager = self.root / "app/src/main/java/com/example/AdsManager.kt"
        manager.write_text(
            "fun showInterOnboarding(ignoreLimit: Boolean = false) { if (interstitial != null && (ignoreLimit)) show() }",
            encoding="utf-8",
        )

        report = inspect_project(self.root, parse_ads_script(self.ads_csv), parse_working_file(self.working_csv))

        self.assertEqual(report.finding("FLOW_INTER_ONBOARDING_SHOW").status, "FAIL")

    def test_flags_single_activity_primary_fragment_architecture(self):
        self.write_project()
        manifest = self.root / "app/src/main/AndroidManifest.xml"
        manifest.write_text(
            '<manifest><application><activity android:name=".MainActivity"/></application></manifest>',
            encoding="utf-8",
        )
        navigation = self.root / "app/src/main/res/navigation"
        navigation.mkdir(parents=True)
        (navigation / "main_nav.xml").write_text(
            '<navigation><fragment android:name="com.example.SplashFragment"/>'
            '<fragment android:name="com.example.LanguageFragment"/>'
            '<fragment android:name="com.example.OnboardingFragment"/></navigation>',
            encoding="utf-8",
        )

        report = inspect_project(self.root, parse_ads_script(self.ads_csv), parse_working_file(self.working_csv))

        finding = report.finding("ARCH_PRIMARY_SCREENS_ACTIVITY")
        self.assertEqual(finding.status, "FAIL")
        self.assertIn("SplashFragment", finding.observed)
        self.assertIn("OnboardingFragment", finding.observed)

    def test_allows_primary_fragments_when_matching_activities_exist(self):
        self.write_project()
        manifest = self.root / "app/src/main/AndroidManifest.xml"
        manifest.write_text(
            '<manifest><application><activity android:name=".MainActivity"/>'
            '<activity android:name=".SplashActivity"/>'
            '<activity android:name=".LanguageActivity"/>'
            '<activity android:name=".OnboardingActivity"/></application></manifest>',
            encoding="utf-8",
        )
        navigation = self.root / "app/src/main/res/navigation"
        navigation.mkdir(parents=True)
        (navigation / "main_nav.xml").write_text(
            '<navigation><fragment android:name="com.example.SplashFragment"/>'
            '<fragment android:name="com.example.LanguageFragment"/>'
            '<fragment android:name="com.example.OnboardingFragment"/></navigation>',
            encoding="utf-8",
        )

        report = inspect_project(self.root, parse_ads_script(self.ads_csv), parse_working_file(self.working_csv))

        self.assertEqual(report.finding("ARCH_PRIMARY_SCREENS_ACTIVITY").status, "PASS")

    def test_allows_unrelated_ui_fragment(self):
        self.write_project()
        navigation = self.root / "app/src/main/res/navigation"
        navigation.mkdir(parents=True)
        (navigation / "main_nav.xml").write_text(
            '<navigation><fragment android:name="com.example.SettingsFragment"/></navigation>',
            encoding="utf-8",
        )

        report = inspect_project(self.root, parse_ads_script(self.ads_csv), parse_working_file(self.working_csv))

        self.assertEqual(report.finding("ARCH_PRIMARY_SCREENS_ACTIVITY").status, "PASS")

    def test_mkt_webhook_names_app_and_explains_primary_fragment_error(self):
        checklist = parse_working_file(self.working_csv)
        payload = build_webhook_payload(
            "repo-folder",
            checklist,
            [
                Finding.fail(
                    "ARCH_PRIMARY_SCREENS_ACTIVITY",
                    "architecture",
                    "separate Activities",
                    "SplashFragment, OnboardingFragment",
                    "Move primary screens to Activities.",
                )
            ],
        )

        self.assertEqual(payload["ket_qua"], "CẦN SỬA")
        self.assertEqual(payload["ten_app"], "Demo Player")
        self.assertEqual(payload["package_name"], "com.example.player")
        self.assertEqual(len(payload["loi"]), 1)
        self.assertIn("1 Activity", payload["loi"][0]["mo_ta"])
        self.assertNotIn("adjust-secret", json.dumps(payload, ensure_ascii=False))

    def test_mkt_payload_groups_duplicate_findings_and_keeps_original_counts(self):
        checklist = parse_working_file(self.working_csv)
        findings = [
            Finding.fail("APP_NAME", "identity", "expected", "wrong", "fix"),
            Finding.fail("APP_PACKAGE", "identity", "expected", "wrong", "fix"),
            Finding.fail("ADMOB_APP_ID", "identity", "expected", "wrong", "fix"),
        ]
        findings.extend(
            Finding.fail(f"AD_CONFIG_RELEASE:placement_{index}", "ad_config", "ad-unit-secret", "wrong", "fix")
            for index in range(25)
        )
        findings.extend([
            Finding.fail("TOKEN:Adjust token", "token", "secret", "missing", "fix"),
            Finding.needs_mapping("PLACEMENT_FLOW:banner_home", "mapping", "missing", "map it"),
            Finding.needs_mapping("PLACEMENT_FLOW:inter_home", "mapping", "missing", "map it"),
            Finding.needs_runtime("RUNTIME:inter_splash", "journey", "runtime", "test splash"),
            Finding.needs_runtime("RUNTIME:inter_onboarding", "journey", "runtime", "test onboarding"),
        ])

        payload = build_webhook_payload("repo", checklist, findings)
        entries = payload["loi"]
        app_info = [entry for entry in entries if entry["tieu_de"] == "Thông tin app chưa khớp checklist"]
        release_config = [entry for entry in entries if entry["tieu_de"] == "Cấu hình quảng cáo release (ad_config.json) chưa đúng"]

        self.assertEqual(len(app_info), 1)
        self.assertIn("app_name", app_info[0]["mo_ta"])
        self.assertIn("package_name", app_info[0]["mo_ta"])
        self.assertIn("AdMob App ID", app_info[0]["mo_ta"])
        self.assertEqual(len(release_config), 1)
        self.assertIn("placement_0", release_config[0]["mo_ta"])
        self.assertIn("và 15 key khác", release_config[0]["mo_ta"])
        self.assertEqual(len(entries), len({(entry["tieu_de"], entry["mo_ta"], entry["can_lam"]) for entry in entries}))
        self.assertEqual(payload["tong_quan"]["loi_can_sua"], 29)
        self.assertEqual(payload["tong_quan"]["can_ky_thuat_xac_nhan"], 4)
        self.assertEqual(len(payload["can_xac_nhan"]), 2)
        self.assertIn("banner_home", payload["can_xac_nhan"][0])
        self.assertIn("inter_splash", payload["can_xac_nhan"][1])

        discord = run_audit.discord_message_payload(payload)
        self.assertLessEqual(len(discord["content"]), 2000)
        self.assertNotIn("ad-unit-secret", discord["content"])
        self.assertNotIn("Adjust token", discord["content"])

    def test_mkt_payload_groups_base_flow_errors_by_area_without_duplicate_titles(self):
        checklist = parse_working_file(self.working_csv)
        findings = [
            Finding.fail("ARCH_GLOBAL_INIT_ORDER", "architecture", "base order", "wrong", "fix"),
            Finding.fail("ARCH_DEV_CONFIG_INIT", "architecture", "dev config", "missing", "fix"),
            Finding.fail("FLOW_SPLASH_REMOTE_CONFIG", "placement_flow", "splash", "missing", "fix"),
            Finding.fail("FLOW_SPLASH_INTER_PRELOAD_LANGUAGE", "placement_flow", "splash", "missing", "fix"),
            Finding.fail("FLOW_LANGUAGE_PRELOAD_AND_RENDER", "placement_flow", "language", "missing", "fix"),
            Finding.fail("ARCH_ADS_MANAGER_UA_GATES", "architecture", "ua", "hardcoded", "fix"),
            Finding.fail("ARCH_ADS_MANAGER_INTER_GATES", "architecture", "inter", "missing", "fix"),
        ]

        payload = build_webhook_payload("repo", checklist, findings)
        titles = [entry["tieu_de"] for entry in payload["loi"]]

        self.assertEqual(len(titles), len(set(titles)))
        self.assertIn("Khởi tạo Ads/Config chưa đúng base", titles)
        self.assertIn("Flow Splash chưa đúng base", titles)
        self.assertIn("Flow Language chưa đúng base", titles)
        self.assertIn("AdsManager chưa đúng base", titles)
        self.assertNotIn("Cần dev kiểm tra phần gắn quảng cáo", titles)
        splash = next(entry for entry in payload["loi"] if entry["tieu_de"] == "Flow Splash chưa đúng base")
        self.assertIn("Native Language", splash["mo_ta"])
        self.assertIn("sau khi inter_splash tải thành công", splash["mo_ta"])
        self.assertIn("SplashActivity", splash["can_lam"])
        self.assertIn("onAdLoaded", splash["can_lam"])
        language = next(entry for entry in payload["loi"] if entry["tieu_de"] == "Flow Language chưa đúng base")
        self.assertIn("preload quảng cáo cho trang Onboarding đầu tiên", language["mo_ta"])
        manager = next(entry for entry in payload["loi"] if entry["tieu_de"] == "AdsManager chưa đúng base")
        self.assertIn("điều kiện bật quảng cáo", manager["mo_ta"])
        technical_rule_ids = [
            "ARCH_GLOBAL_INIT_ORDER",
            "ARCH_DEV_CONFIG_INIT",
            "ARCH_ADS_CONFIG_FIELDS",
            "ARCH_APP_OPEN_EXCLUSIONS",
            "ARCH_MOBILE_ADS_INIT",
            "ARCH_REMOTE_CONFIG_INIT",
            "ARCH_ERAIN_INIT",
            "ARCH_INTERSTITIAL_INTERVAL",
            "FLOW_SPLASH_REMOTE_CONFIG",
            "FLOW_SPLASH_INTER_PRELOAD_LANGUAGE",
            "ARCH_ADS_MANAGER_UA_GATES",
        ]
        mkt_json = json.dumps(payload["loi"], ensure_ascii=False)
        for rule_id in technical_rule_ids:
            self.assertNotIn(rule_id, mkt_json)
        self.assertNotIn("Rule ảnh hưởng", mkt_json)

        discord = run_audit.discord_message_payload(payload)["content"]
        self.assertIn("Ads Audit: CẦN SỬA", discord)
        self.assertIn("**1. Khởi tạo Ads/Config chưa đúng base**", discord)
        self.assertNotIn("**1. Khởi tạo Ads/Config chưa đúng base**\n\nMô tả:", discord)
        self.assertNotIn("**1. Khởi tạo Ads/Config chưa đúng base**\n\n**Mô tả:**", discord)
        self.assertIn("**1. Khởi tạo Ads/Config chưa đúng base**\n**Mô tả:**\n", discord)
        self.assertIn("Mobile Ads, DevConfig, config quảng cáo và SDK quảng cáo chưa được khởi tạo đúng thứ tự.", discord)
        self.assertIn("\n**Cách sửa:**\n", discord)
        self.assertIn("Trong GlobalApp, khởi tạo lần lượt", discord)
        self.assertNotIn("Cách sửa: Dev sửa", discord)
        self.assertEqual(discord.count("Flow Splash chưa đúng base"), 1)
        self.assertNotIn("→", discord)
        for rule_id in technical_rule_ids:
            self.assertNotIn(rule_id, discord)

    def test_discord_report_can_split_long_audit_into_multiple_messages(self):
        payload = {
            "ket_qua": "CẦN SỬA",
            "ten_app": "Long App",
            "package_name": "com.example.long",
            "tong_quan": {"loi_can_sua": 12, "can_ky_thuat_xac_nhan": 0, "muc_da_kiem_tra_dung": 4},
            "loi": [
                {
                    "tieu_de": f"Lỗi nhóm {index}",
                    "mo_ta": "- " + ("Mô tả dễ hiểu cho MKT. " * 18),
                    "can_lam": "- " + ("Cách sửa chi tiết cho dev. " * 18),
                }
                for index in range(1, 13)
            ],
            "can_xac_nhan": [],
        }

        messages = run_audit.discord_message_payloads(payload, max_content_length=900)

        self.assertGreater(len(messages), 1)
        self.assertTrue(all(len(message["content"]) <= 900 for message in messages))
        self.assertIn("Ads Audit: CẦN SỬA", messages[0]["content"])
        self.assertIn("Ads Audit chi tiết (2/", messages[1]["content"])
        combined = "\n".join(message["content"] for message in messages)
        self.assertIn("**1. Lỗi nhóm 1**\n**Mô tả:**", combined)
        self.assertNotIn("**1. Lỗi nhóm 1**\n\n**Mô tả:**", combined)
        self.assertIn("**12. Lỗi nhóm 12**", combined)

    def test_webhook_posts_summary_markdown_as_discord_attachment(self):
        url = "https://example.test/hook"
        summary = self.root / "ads-audit-summary.md"
        summary.write_text("# Summary\n", encoding="utf-8")
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"200", stderr=b"")
        with patch.object(run_audit.subprocess, "run", return_value=completed) as run:
            result = run_audit.post_webhook(url, None, {"content": "ok"}, attachment_path=summary)

        self.assertIsNone(result)
        command = run.call_args.args[0]
        self.assertIn("--form", command)
        self.assertIn("--form-string", command)
        payload_arg = command[command.index("--form-string") + 1]
        self.assertTrue(payload_arg.startswith("payload_json="))
        self.assertEqual(json.loads(payload_arg.removeprefix("payload_json=")), {"content": "ok"})
        self.assertIn(f"files[0]=@{summary};filename=ads-audit-summary.md", command)
        self.assertNotIn("--data-binary", command)

    def test_welcome_back_requires_resume_gate_and_welcome_load_show_chain(self):
        self.write_project()
        global_app = self.root / "app/src/main/java/com/example/GlobalApp.kt"
        global_app.write_text(global_app.read_text(encoding="utf-8") + "\nProcessLifecycleOwner.get().lifecycle.addObserver(AppLifecycleObserver())\n", encoding="utf-8")
        self.ads_csv.write_text(
            self.ads_csv.read_text(encoding="utf-8").replace(
                ",,APP ID,ca-app-pub-123~999,\n",
                "3,interstitial,inter_welcome_back,ca-app-pub-123/333,Show when app resumes\n"
                ",,APP ID,ca-app-pub-123~999,\n",
            ),
            encoding="utf-8",
        )
        (self.root / "app/src/main/java/com/example/AppLifecycleObserver.kt").write_text(
            "class AppLifecycleObserver { fun onStart() { "
            "ResumeAdsEntryRule.shouldShowWelcomeOnResume(); "
            "ERainAd.getInstance().getShouldDisplayInterWelcomeBack(AdRemoteConfig.inter_welcome_back.enableUaCheck); "
            "Routes.startWelcomeActivity(currentActivity) } }",
            encoding="utf-8",
        )
        (self.root / "app/src/main/java/com/example/WelcomeActivity.kt").write_text(
            "class WelcomeActivity { fun initViews() { AdsManager.loadInterWelcome(this) } "
            "fun click() { AdsManager.showInterWelcome(this) } }",
            encoding="utf-8",
        )
        (self.root / "app/src/main/java/com/example/AdsManager.kt").write_text(
            "object AdsManager { fun loadInterWelcome() { val config = AdRemoteConfig.inter_welcome_back; "
            "if (!config.isEnable || AppPurchase.getInstance().isPurchased(context)) return; getInterstitialAds() } "
            "fun showInterWelcome() { forceShowInterstitial() } }",
            encoding="utf-8",
        )

        report = inspect_project(self.root, parse_ads_script(self.ads_csv), parse_working_file(self.working_csv))

        self.assertEqual(report.finding("FLOW_INTER_WELCOME_BACK_OBSERVER").status, "PASS")
        self.assertEqual(report.finding("FLOW_INTER_WELCOME_BACK_LOAD_SHOW").status, "PASS")
        self.assertEqual(report.finding("FLOW_INTER_WELCOME_BACK_REGISTRATION").status, "PASS")

    def test_full_base_flow_project_passes_static_architecture_pipeline(self):
        self.write_full_base_flow_project()

        report = inspect_project(self.root, parse_ads_script(self.ads_csv), parse_working_file(self.working_csv))

        expected_passes = [
            "ARCH_GLOBAL_INIT_ORDER",
            "ARCH_DEV_CONFIG_INIT",
            "ARCH_DEV_CONFIG_BUILD_FIELDS",
            "ARCH_ADS_CONFIG_FIELDS",
            "ARCH_APP_OPEN_EXCLUSIONS",
            "FLOW_SPLASH_REMOTE_CONFIG",
            "FLOW_SPLASH_INTER_PRELOAD_LANGUAGE",
            "FLOW_SPLASH_OPEN_RESUME",
            "FLOW_LANGUAGE_DEV_SETTING",
            "FLOW_LANGUAGE_PRELOAD_AND_RENDER",
            "FLOW_ONBOARDING_PRELOAD_AND_SHOW",
            "FLOW_ONBOARDING_PAGE_RENDERING",
            "FLOW_RESUME_RULE",
            "FLOW_WELCOME_NATIVE_AND_INTER",
            "ARCH_BANNER_BASE_RELOAD",
            "ARCH_ADS_MANAGER_NATIVE_GATES",
            "ARCH_ADS_MANAGER_UA_GATES",
            "ARCH_ADS_MANAGER_INTER_GATES",
            "ARCH_ADS_MANAGER_BANNER",
        ]
        for rule_id in expected_passes:
            with self.subTest(rule_id=rule_id):
                self.assertEqual(report.finding(rule_id).status, "PASS")

    def test_full_base_flow_audit_flags_broken_init_order_and_hardcoded_ua_gate(self):
        self.write_full_base_flow_project()
        global_app = self.root / "app/src/main/java/com/example/GlobalApp.kt"
        global_app.write_text(
            global_app.read_text(encoding="utf-8").replace(
                "MobileAds.initialize(this){}; DevConfig.init",
                "DevConfig.init"
            ),
            encoding="utf-8",
        )
        manager = self.root / "app/src/main/java/com/example/AdsManager.kt"
        manager.write_text(
            manager.read_text(encoding="utf-8").replace(
                "getShouldDisplayNativeHome(config.enableUaCheck)",
                "getShouldDisplayNativeHome(true)"
            ),
            encoding="utf-8",
        )

        report = inspect_project(self.root, parse_ads_script(self.ads_csv), parse_working_file(self.working_csv))

        self.assertEqual(report.finding("ARCH_GLOBAL_INIT_ORDER").status, "FAIL")
        self.assertEqual(report.finding("ARCH_ADS_MANAGER_UA_GATES").status, "FAIL")
        self.assertIn("config.enableUaCheck", report.finding("ARCH_ADS_MANAGER_UA_GATES").recommendation)

    def test_package_skill_zip_excludes_generated_caches_and_reports(self):
        skill_root = self.root / "infinity-ads-compliance-audit"
        skill_root.mkdir()
        (skill_root / "SKILL.md").write_text("name: infinity-ads-compliance-audit\n", encoding="utf-8")
        (skill_root / "scripts").mkdir()
        (skill_root / "scripts" / "run_audit.py").write_text("print('audit')\n", encoding="utf-8")
        (skill_root / "scripts" / "__pycache__").mkdir()
        (skill_root / "scripts" / "__pycache__" / "run_audit.pyc").write_bytes(b"cache")
        (skill_root / "ads-audit-output").mkdir()
        (skill_root / "ads-audit-output" / "ads-audit-summary.md").write_text("generated", encoding="utf-8")
        output_zip = self.root / "skill.zip"

        package_skill.package_skill(skill_root, output_zip)

        with zipfile.ZipFile(output_zip) as archive:
            names = set(archive.namelist())
        self.assertIn("infinity-ads-compliance-audit/SKILL.md", names)
        self.assertIn("infinity-ads-compliance-audit/scripts/run_audit.py", names)
        self.assertFalse(any("__pycache__" in name for name in names))
        self.assertFalse(any(name.endswith(".pyc") for name in names))
        self.assertFalse(any("ads-audit-output" in name for name in names))


if __name__ == "__main__":
    unittest.main()
