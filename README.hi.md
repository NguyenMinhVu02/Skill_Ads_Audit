**Language / Ngôn ngữ / भाषा:** [English](README.md) | [Tiếng Việt](README.vi.md) | [हिन्दी](README.hi.md)

# Infinity Ads Compliance Audit

**Claude Code** और **Codex** के लिए एक agent skill, जो किसी Android app के
Infinity ads integration को base project और उस app के अपने contract documents
के विरुद्ध जाँचती है। यह audit project को सिर्फ़ पढ़ती है; source code कभी नहीं
बदलती।

एक बार install कीजिए, फिर किसी भी Android project की जाँच AI से करवाइए।

## Install

```bash
git clone https://github.com/NguyenMinhVu02/Skill_Ads_Audit.git
cd Skill_Ads_Audit
./install.sh          # macOS / Linux
.\install.ps1         # Windows PowerShell
```

Installer मशीन पर मौजूद agents को पहचानता है और skill को हर एक में copy कर देता
है:

| Host | जगह | कैसे बुलाएँ |
| --- | --- | --- |
| Claude Code | `~/.claude/skills/` | `/infinity-ads-compliance-audit` |
| Codex CLI | `$CODEX_HOME/skills/` (default `~/.codex/skills/`) | `$infinity-ads-compliance-audit` |
| Antigravity / Gemini | `~/.gemini/antigravity/skills/` | सामान्य भाषा में कहिए |

Codex skills को `$CODEX_HOME/skills` से पढ़ता है, `~/.agents/skills` से **नहीं**।
Installer दोनों जगह लिखता है, ताकि पुराना Codex भी चलता रहे।

पूरी मशीन के बजाय सिर्फ़ एक repository में install करना हो तो
`<project>/.claude/skills/infinity-ads-compliance-audit/` (या `.agents/skills/`)
में clone कीजिए। उसके बाद agent को restart कीजिए ताकि नई skill load हो जाए।

ज़रूरत: Python 3.9+ और `curl`. कोई Python package install नहीं करना पड़ता —
सिर्फ़ standard library।

## इस्तेमाल

Android project की root से चलाइए।

**Claude Code** — `claude` शुरू कीजिए, फिर:

```text
/infinity-ads-compliance-audit

इस project की जाँच कीजिए। Documents:
  ADS SCRIPTS:  https://docs.google.com/spreadsheets/d/.../edit#gid=0
  Checklist:    https://docs.google.com/document/d/.../edit
Source मत बदलिए। जवाब हिन्दी में दीजिए।
```

**Codex CLI** — `codex` शुरू कीजिए, फिर `$` sigil लगाइए:

```text
$infinity-ads-compliance-audit

इस project की जाँच कीजिए। Documents:
  ADS SCRIPTS:  https://docs.google.com/spreadsheets/d/.../edit#gid=0
  Checklist:    https://docs.google.com/document/d/.../edit
Source मत बदलिए। जवाब हिन्दी में दीजिए।
```

दोनों hosts काम का ब्यौरा देने भर से भी skill खुद चुन लेते हैं ("इस project का
ads compliance check करो")। `/` या `$` लिखना सिर्फ़ पक्का करने के लिए है।

अगर दोनों CSV files पहले से project में हैं, तो Documents वाला हिस्सा हटा
दीजिए — वे अपने आप मिल जाती हैं।

Agent bundled auditor चलाता है, बनी हुई reports पढ़ता है, हर finding को code से
मिलाकर देखता है, और sanitized report Discord पर भेज देता है — जब तक आप
local-only run न माँगें।

### दो documents

| Document | इसमें क्या होता है |
| --- | --- |
| **ADS SCRIPTS** | placement key, ad type, ad-unit ID, AdMob APP ID |
| **working checklist** | app name, package, Firebase project, Adjust/Facebook/TikTok tokens |

हर एक या तो local CSV हो सकता है, या **Google Sheets / Google Docs link**।
Sheets को CSV के रूप में export किया जाता है; Docs को `label: value` पंक्तियों
की तरह पढ़ा जाता है। Link की sharing *anyone with the link → Viewer* रखिए, वरना
download में sign-in page आ जाता है और audit sharing error के साथ रुक जाती है।

अगर दोनों documents पहले से project के अंदर CSV हैं, तो वे अपने आप मिल जाती
हैं — एक filename में `ADS SCRIPTS`, दूसरे में `working` या `work file`। शून्य
या एक से ज़्यादा matches मिलने पर discovery कभी अंदाज़ा नहीं लगाती।

Partner की spreadsheet का layout तय नहीं होना चाहिए। Parser comma, semicolon,
tab और pipe delimiters, अंग्रेज़ी और वियतनामी column labels, असली header से पहले
की title rows, और आम aliases सँभाल लेता है। Headers अनजाने हों तो वह पहचानने
योग्य values से column का अनुमान लगाता है — package names, Firebase URLs, ad
formats, ad-unit IDs। स्पष्ट alias हमेशा जीतता है, और अगर दो columns बराबर के
संभावित हों तो audit ग़लत data जाँचने के बजाय **रुककर बताती है**।

### Documents कैसे माँगे जाते हैं

Skill दोनों documents के बिना कभी audit नहीं करती, और कभी अंदाज़ा नहीं लगाती।
यह तीन स्तरों पर काम करती है:

| स्तर | स्थिति | क्या होता है |
| --- | --- | --- |
| **1** | दोनों CSV पहले से project में हैं | अपने आप मिल जाती हैं। आपसे कुछ नहीं पूछा जाता। |
| **2** | नहीं हैं, और कोई link भी नहीं दिया | Agent कुछ भी चलाने से **पहले** दोनों documents माँगता है — link हो या file। |
| **3** | Link दिया गया पर access नहीं है | Audit रुक जाती है और दो रास्ते देती है: link sharing बदलिए, या file download करके उसका path दीजिए। |

स्तर 3 के बाद भी document न मिले तो audit **रुक जाती है और यह साफ़ बता देती है**।
वह अधूरी report नहीं बनाएगी, ad-unit ID नहीं गढ़ेगी, और base project की values
पर वापस नहीं जाएगी — फ़ैसले जैसी दिखने वाली आधी-अधूरी audit, बिना audit से भी
ख़राब है।

Discovery उम्मीदवारों के बीच भी अंदाज़ा नहीं लगाती: शून्य matches हों या कई,
दोनों हालात में यह किसी एक को चुनने के बजाय स्तर 2 पर चली जाती है।

## क्या-क्या जाँचा जाता है

नियम Infinity base project के हिसाब से calibrate किए गए हैं, ताकि सही app साफ़
तरीक़े से pass हो।

- **पहचान** — package, app name (default `res/values/strings.xml` से, किसी
  translation से नहीं), **release** `manifestPlaceholders` से AdMob app id,
  Firebase project, service tokens।
- **Config** — contract की हर key/ID release `ad_config.json` में मौजूद हो,
  बिलकुल मेल खाए, और `isEnable` घोषित करे। `ad_config_debug.json` को जान-बूझकर
  छोड़ा जाता है।
- **Init क्रम** — `MobileAds.initialize` → `DevConfig.init` →
  `AdRemoteConfig.initializeFromAssets` → `ERainAd.init`, साथ में DevConfig के
  version fields, `ERainAdConfig` fields, `intervalInterstitialAd`, AppOpen
  exclusions, lifecycle observer और activity callbacks।
- **Screen संरचना** — Splash, Language, Onboarding, Home और Welcome अलग-अलग
  Activity होने चाहिए। इन screens को single-Activity + Fragment से बनाना ग़लती
  है। इनके *अंदर pages* के रूप में इस्तेमाल हुए Fragments सही हैं।
- **Preload / load / show** — हर ad कहाँ preload होता है, load के चार gates
  (`isEnable`, purchase, network, `getShouldDisplay*(config.enableUaCheck)`),
  null मिलने पर container छिपाना, और interstitial का सिर्फ़ अपने callback से
  navigate करना।
- **Resume बनाम Welcome** — mode का चुनाव, disabled-screen सूचियाँ, और वे gates
  जो App Open ad को Welcome interstitial के ऊपर चढ़ने से रोकते हैं।
- **Banner** — config/purchase/container gates और `reloadIntervalSeconds`।

बिना mapping वाले placements `NEEDS_MAPPING` पर रहते हैं। जो दावे static
analysis तय नहीं कर सकती, वे test case के साथ `NEEDS_RUNTIME_PROOF` पर रहते
हैं। इनमें से कोई भी pass नहीं है।

## नतीजा

जाँचे गए project के अंदर `ads-audit-output/` में लिखा जाता है:

- `ads-audit-summary.md` — developers के लिए पूरी finding सूची।
- `ads-audit-evidence.json` — sanitized वियतनामी MKT payload।

Command बिना static failure के `0`, सुधार ज़रूरी होने पर `2`, और ग़लत input पर
`1` return करती है।

Reports में Adjust, Facebook client और TikTok की values छिपा दी जाती हैं।
`app-ads.txt` की जाँच कभी शामिल नहीं होती।

## अपने placements

अगर कोई placement `NEEDS_MAPPING` लौटाए, तो `templates/ads-audit-overrides.yaml`
को app में copy कीजिए और स्वीकृत class व call mapping जोड़िए — contract की key
और ID बिलकुल वैसी ही रखिए। कुछ placements — `native_home`, `native_permission`,
`native_onboarding_fullscreen_*_4`, `banner_splash`, `reward_example` —
`AdsManager` में मौजूद तो हैं, पर base में किसी screen से जुड़े नहीं हैं, इसलिए
इनका यहाँ आना अपेक्षित है।

## Discord webhook

हर audit के बाद skill एक छोटी MKT report और summary file भेजती है। किसी एक run
के लिए `--no-webhook` से बंद कीजिए। Endpoint बदलने के लिए `--webhook-url` या
`ADS_AUDIT_WEBHOOK_URL` / `DISCORD_WEBHOOK_URL` environment variables।

## Auditor सीधे चलाना

CI या debugging के लिए उपयोगी; ऊपर बताया गया AI वाला रास्ता ही असल तरीक़ा है।

```bash
python3 scripts/run_audit.py --project /path/to/app --no-webhook
python3 scripts/run_audit.py --project . \
  --ads-script "https://docs.google.com/spreadsheets/d/<id>/edit#gid=0" \
  --working-file "./working file.csv"
```

## Partner repo के लिए package बनाना

```bash
python3 scripts/package_skill.py --skill-root . --output infinity-ads-audit.zip
```

## संदर्भ

- `references/base-code-reference.md` — base implementation, code में: Gradle,
  `GlobalApp`, `AdsManager`, हर screen, gates, config schema।
- `references/base-integration-rules.md` — वही नियम checklist के रूप में।
- `references/placement-rule-map.yaml` — हर placement के लिए स्वीकृत evidence।
