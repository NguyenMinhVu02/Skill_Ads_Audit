# Kiểm tra tuân thủ Infinity Ads

Skill này kiểm tra app Android của đối tác theo đúng hai file riêng của app: `ADS SCRIPTS` và working file, đồng thời đối chiếu toàn bộ flow gắn ads với base `Example-AdLogic-Partner`. Skill chỉ đọc mã nguồn và config, không tự sửa app.

## Phạm vi kiểm tra hiện tại

- Thông tin app: package, app name, AdMob App ID, Firebase project, token/service trong working file. Tên app được lấy từ `res/values/strings.xml` mặc định; các file dịch theo locale không ghi đè giá trị này.
- Config quảng cáo: mọi key/ID trong CSV chỉ được đối chiếu với `ad_config.json` (release), phải đúng tuyệt đối và có `isEnable`. ID debug/test trong `ad_config_debug.json` được phép khác production và không bị báo lỗi contract.
- `GlobalApp`: thứ tự `MobileAds.initialize` → `DevConfig.init` → `AdRemoteConfig.initializeFromAssets` → `ERainAd.init`; đủ `BuildConfig` version fields; đủ Adjust/Facebook/TikTok/interval/resume id; AppOpen exclusions; lifecycle observer.
- `SplashActivity`: consent/RemoteConfig, apply `AdRemoteConfig` từ `RemoteConfigUtils`, load/show `inter_splash`, preload native language trong `onAdLoaded`, navigate trong `onNextAction`, setup `open_resume`.
- `LanguageActivity`: DevSetting trên `tvTitle`, delay 100ms, native language/click, preload onboarding page 1, observe/render/hide native ads.
- `OnBoardingActivity` và `OnboardingPageFragment`: preload native page 4/full/inter, widget gate, page LiveData mapping, final `showInterOnboarding` callback sang Home.
- `ResumeAdsEntryRule`, `AppLifecycleObserver`, `WelcomeActivity`: open-resume vs Welcome mode, disabled screens, purchase/interstitial/UA gates, load/show native/inter Welcome.
- `AdsManager`: central native/inter/banner load-show, `isEnable`, purchase, network, `config.enableUaCheck`, null fallback, callback navigation.
- `BaseActivityWithBanner`: `BannerConfig`, `AdsManager.loadBanner`, purchase/config/container gate, `reloadIntervalSeconds`.
- Các placement không map được thì trả `NEEDS_MAPPING`; các journey cần bấm/thời điểm runtime thì trả `NEEDS_RUNTIME_PROOF`.

## Cách dễ nhất cho đối tác: chạy bằng npx

Mở Terminal tại thư mục gốc của Android project rồi chạy:

```bash
npx -y github:NguyenMinhVu02/Skill_Ads_Audit audit \
  --project . \
  --no-webhook
```

CLI sẽ tự tìm đúng một file CSV có tên chứa `ADS SCRIPTS` và đúng một file có tên chứa `working` hoặc `work file`. Nếu không tìm thấy hoặc có nhiều file, CLI sẽ dừng và hướng dẫn truyền đường dẫn rõ ràng; không tự đoán file.

Cần có:

- Node.js 18 trở lên (có `npx`).
- Python 3.10 trở lên.
- Dự án Android và hai CSV riêng của app.

### CSV của từng đối tác có thể khác nhau

Auditor không bắt mọi đối tác dùng cùng một mẫu bảng. Với file `ADS SCRIPTS`, skill tự xử lý:

- delimiter là dấu phẩy, chấm phẩy, tab hoặc `|`;
- tên cột tiếng Anh hoặc tiếng Việt, khác hoa thường và khoảng trắng;
- một vài dòng tiêu đề/export nằm trước dòng header thật;
- alias phổ biến như `Ad Unit ID`, `Placement Name`, `Ad Type`, `Tên vị trí`, `Loại quảng cáo`;
- cột ID không có tên nếu dữ liệu trong cột đó rõ ràng giống ad-unit ID (ví dụ `ca-app-pub-.../...`).

Working file cũng không bắt buộc một mẫu cột cố định. Skill nhận các cặp key/value như `Task Detail / Document`, `Content / Detail`, `Field / Value`, `Key / Data` và các tên tiếng Việt thông dụng. Thứ tự cột không quan trọng; các cột phụ như `Order`, `PIC`, người phụ trách hoặc trạng thái sẽ được bỏ qua. Các nhãn dòng như `Application name`, `Bundle ID` và `Firebase project` được chuẩn hóa về trường checklist tương ứng.

Khi header lạ, parser có thể suy luận từ nội dung dễ nhận biết như nhãn checklist, package name, Firebase URL, placement key, loại quảng cáo và ad-unit ID. Alias rõ ràng luôn được ưu tiên. Nếu hai cột có khả năng đúng ngang nhau hoặc độ tin cậy thấp, audit sẽ dừng và báo delimiter, header cùng semantic còn thiếu, không âm thầm đọc nhầm dữ liệu.

Nếu có nhiều CSV trùng loại, truyền đường dẫn thủ công:

```bash
npx -y github:NguyenMinhVu02/Skill_Ads_Audit audit \
  --project . \
  --ads-script "./config/ADS SCRIPTS.csv" \
  --working-file "./config/working-file.csv" \
  --no-webhook
```

Kết quả nằm trong `ads-audit-output/ads-audit-summary.md` và `ads-audit-output/ads-audit-evidence.json`. Lệnh chỉ đọc dự án Android, không tự sửa source. Dùng `--no-webhook` để chỉ tạo báo cáo local.

## Dùng với Codex CLI (AI + skill + webhook)

Cài một lần để dùng trong mọi project trên máy:

```bash
mkdir -p "$HOME/.agents/skills"
git clone \
  https://github.com/NguyenMinhVu02/Skill_Ads_Audit.git \
  "$HOME/.agents/skills/infinity-ads-compliance-audit"
```

Hoặc chỉ cài trong một repository:

```text
partner-app/.agents/skills/infinity-ads-compliance-audit/
```

Sau đó mở Codex tại thư mục gốc Android project:

```bash
cd partner-app
codex
```

Gọi skill bằng `$infinity-ads-compliance-audit`:

```text
Hãy dùng $infinity-ads-compliance-audit để kiểm tra toàn bộ dự án hiện tại.
Tự tìm ADS SCRIPTS CSV và working-file CSV. Không sửa code.
Không kiểm tra app-ads.txt.
Trả về lỗi ngắn gọn bằng tiếng Việt cho MKT, gồm tên app, package name, lỗi cần sửa, mục cần kỹ thuật xác nhận và các mục đã đạt.
Gửi báo cáo đã làm sạch lên Discord webhook được cấu hình.
```

Codex sẽ đọc skill, tự chạy auditor, đọc các file báo cáo và gửi webhook, trừ khi bạn yêu cầu chỉ tạo báo cáo local. Đối tác không cần tự gõ lệnh Python.

## Dùng với Claude Code (AI + skill + webhook)

Cài một lần để dùng trong mọi project trên máy:

```bash
mkdir -p "$HOME/.claude/skills"
git clone \
  https://github.com/NguyenMinhVu02/Skill_Ads_Audit.git \
  "$HOME/.claude/skills/infinity-ads-compliance-audit"
```

Hoặc chỉ cài trong một repository:

```text
partner-app/.claude/skills/infinity-ads-compliance-audit/
```

Sau đó mở Claude Code tại thư mục gốc Android project:

```bash
cd partner-app
claude
```

Gọi skill bằng `/infinity-ads-compliance-audit`:

```text
/infinity-ads-compliance-audit

Hãy kiểm tra project Android hiện tại. Tự tìm ADS SCRIPTS CSV và working-file CSV,
không sửa source code, đọc các file báo cáo và gửi báo cáo đã làm sạch lên Discord webhook.
Trả kết quả bằng tiếng Việt.
```

Claude Code đọc skill từ `.claude/skills/<skill-name>/SKILL.md` trong project hoặc `$HOME/.claude/skills/<skill-name>/SKILL.md` dùng chung cho user. Nếu cài skill khi Claude Code đang mở, hãy khởi động lại hoặc reload skill.

Cả Codex và Claude đều cần Python 3.10 trở lên để chạy auditor. `npx` chỉ là phương án chạy bằng Terminal, không phải AI runtime.

## Chạy auditor Python trực tiếp (tùy chọn)

Tại thư mục gốc repository của đối tác:

```bash
python3 "/duong-dan/infinity-ads-compliance-audit/scripts/run_audit.py" \
  --project .
```

Python CLI tự tìm hai CSV giống lệnh npx. Nếu không tìm thấy hoặc có nhiều file trùng loại, hãy truyền đường dẫn cụ thể; đường dẫn truyền tay luôn được ưu tiên:

```bash
python3 "/duong-dan/infinity-ads-compliance-audit/scripts/run_audit.py" \
  --project . \
  --ads-script "/duong-dan/ADS SCRIPTS.csv" \
  --working-file "/duong-dan/working file.csv"
```

Kết quả nằm trong `ads-audit-output/`:

- `ads-audit-summary.md`: lỗi, vị trí và hướng sửa ngắn gọn.
- `ads-audit-evidence.json`: payload ngắn gọn để Infinity review hoặc gửi webhook Discord.

Mã trả về: `0` khi không có lỗi tĩnh, `2` khi cần sửa, `1` khi file đầu vào không hợp lệ.

## Đóng gói để gửi đối tác

Từ thư mục chứa skill:

```bash
python3 infinity-ads-compliance-audit/scripts/package_skill.py \
  --skill-root infinity-ads-compliance-audit \
  --output infinity-ads-compliance-audit.zip
```

File zip loại trừ `__pycache__`, `.pyc` và `ads-audit-output/` để đối tác chỉ nhận source skill sạch.

## Webhook Discord tự động

Skill đã có sẵn webhook Discord. Sau mỗi lần audit, nếu không truyền `--no-webhook`, báo cáo ngắn cho MKT sẽ tự gửi gồm tên app, package name, số lỗi, lỗi cần sửa và mục cần kỹ thuật xác nhận. Skill cũng đính kèm file `ads-audit-summary.md` lên Discord để dev mở chi tiết ngay.

Trong webhook, mỗi lỗi được tách dòng:

```text
1. Tên nhóm lỗi
**Mô tả:**
- Nội dung lỗi cụ thể, nói rõ flow nào đang đặt sai vị trí hoặc thiếu bước nào.
**Cách sửa:**
- Hướng sửa cụ thể cho dev.
```

Nếu báo cáo dài hơn giới hạn một tin nhắn Discord, skill tự chia thành nhiều tin nhắn `Ads Audit chi tiết (2/N)`, `Ads Audit chi tiết (3/N)`, ... và chỉ đính kèm `ads-audit-summary.md` ở tin nhắn đầu tiên.

Dùng `--no-webhook` nếu Infinity yêu cầu lần kiểm tra đó chỉ tạo báo cáo local.

## Ghi đè webhook (chỉ khi được Infinity duyệt)

```bash
python3 "/duong-dan/infinity-ads-compliance-audit/scripts/run_audit.py" \
  --project . --ads-script "/duong-dan/ADS SCRIPTS.csv" \
  --working-file "/duong-dan/working file.csv" \
  --webhook-url "https://your-endpoint.example/audits"
```

Nếu cần bearer token, thêm `--webhook-token "$TOKEN"`. Báo cáo không in Adjust token, Facebook client token hoặc TikTok token ở dạng gốc.

Payload gửi webhook gồm `ten_app`, `package_name`, trạng thái, số lỗi, lỗi viết ngắn gọn cho MKT và các mục cần kỹ thuật xác nhận. Không kiểm tra hoặc gửi thông tin `app-ads.txt`.

## Placement đặc biệt của từng app

Mỗi app được phép có key khác base vì `ADS SCRIPTS.csv` là chuẩn ID/key/vị trí của app đó. Khi kết quả là `NEEDS_MAPPING`, copy `templates/ads-audit-overrides.yaml` vào app và khai báo class/call/event đã được Infinity duyệt. `NEEDS_RUNTIME_PROOF` nghĩa là phải test trên app, không phải pass.

## Rule cấu trúc màn hình bắt buộc

Splash, Language, Onboarding, Home và Welcome là các màn chính của luồng ads. Chúng phải là `Activity` riêng theo base Infinity. Nếu app dùng một `Activity` và nhiều `Fragment` cho các màn này, skill báo lỗi yêu cầu dev chuyển các màn đó sang `Activity`. Fragment nhỏ chỉ để hiển thị UI trong một màn Activity không bị báo lỗi.

## Tóm tắt cách gọi AI

| Công cụ | Thư mục cài | Cách gọi |
| --- | --- | --- |
| Codex CLI | `$HOME/.agents/skills/` hoặc `.agents/skills/` | `$infinity-ads-compliance-audit` |
| Claude Code | `$HOME/.claude/skills/` hoặc `.claude/skills/` | `/infinity-ads-compliance-audit` |

AI host sẽ chạy auditor local rồi giải thích evidence. Bản thân auditor là Python code chạy theo rule cố định; `npx` không phải AI runtime.
