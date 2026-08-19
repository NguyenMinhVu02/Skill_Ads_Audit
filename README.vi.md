**Language / Ngôn ngữ / भाषा:** [English](README.md) | [Tiếng Việt](README.vi.md) | [हिन्दी](README.hi.md)

# Infinity Ads Compliance Audit

Skill cho **Claude Code** và **Codex**, dùng để kiểm tra phần gắn quảng cáo của
một app Android so với project base Infinity và 2 tài liệu hợp đồng của chính
app đó. Skill chỉ đọc project, không sửa code.

Cài một lần, sau đó nhờ AI kiểm tra bất kỳ project Android nào.

## Cài đặt

```bash
git clone https://github.com/NguyenMinhVu02/Skill_Ads_Audit.git
cd Skill_Ads_Audit
./install.sh          # macOS / Linux
.\install.ps1         # Windows PowerShell
```

Script tự nhận diện các agent có trên máy và copy skill vào từng chỗ:

| Host | Vị trí | Gọi bằng |
| --- | --- | --- |
| Claude Code | `~/.claude/skills/` | `/infinity-ads-compliance-audit` |
| Codex CLI | `$CODEX_HOME/skills/` (mặc định `~/.codex/skills/`) | `$infinity-ads-compliance-audit` |
| Antigravity / Gemini | `~/.gemini/antigravity/skills/` | nhắn bằng lời bình thường |

Codex đọc skill ở `$CODEX_HOME/skills`, **không phải** `~/.agents/skills`. Script
cài vào cả hai nên Codex bản cũ vẫn chạy được.

Muốn cài cho riêng một repo thì clone vào
`<project>/.claude/skills/infinity-ads-compliance-audit/` (hoặc `.agents/skills/`).
Cài xong nhớ khởi động lại agent để nó nạp skill.

Yêu cầu: Python 3.9 trở lên và `curl`. Không cần cài thư viện Python nào.

## Cách dùng

Đứng ở thư mục gốc project Android.

**Claude Code** — chạy `claude`, rồi gõ:

```text
/infinity-ads-compliance-audit

Kiểm tra project này. Tài liệu:
  ADS SCRIPTS:  https://docs.google.com/spreadsheets/d/.../edit#gid=0
  Checklist:    https://docs.google.com/document/d/.../edit
Không sửa code. Trả lời bằng tiếng Việt.
```

**Codex CLI** — chạy `codex`, rồi dùng dấu `$`:

```text
$infinity-ads-compliance-audit

Kiểm tra project này. Tài liệu:
  ADS SCRIPTS:  https://docs.google.com/spreadsheets/d/.../edit#gid=0
  Checklist:    https://docs.google.com/document/d/.../edit
Không sửa code. Trả lời bằng tiếng Việt.
```

Cả hai đều có thể tự chọn skill khi bạn chỉ mô tả công việc ("kiểm tra tuân thủ
ads cho project này"). Gõ `/` hoặc `$` là cách chắc chắn nhất.

Nếu 2 file CSV đã nằm sẵn trong project thì bỏ hẳn phần Tài liệu — skill tự tìm.

AI sẽ chạy auditor, đọc báo cáo, đối chiếu từng lỗi với code thật, rồi gửi báo
cáo đã lọc bí mật lên Discord — trừ khi bạn yêu cầu chỉ chạy local.

### Hai tài liệu đầu vào

| Tài liệu | Chứa gì |
| --- | --- |
| **ADS SCRIPTS** | key vị trí, loại quảng cáo, ad-unit ID, AdMob APP ID |
| **Working checklist** | tên app, package, Firebase project, token Adjust/Facebook/TikTok |

Mỗi tài liệu có thể là file CSV trên máy, hoặc **link Google Sheets / Google
Docs**. Sheets được export sang CSV; Docs được đọc theo các dòng dạng
`nhãn: giá trị`. Nhớ để link ở chế độ *bất kỳ ai có link đều xem được*, nếu
không bản tải về sẽ là trang đăng nhập và audit dừng lại kèm thông báo lỗi chia
sẻ.

Nếu 2 file CSV đã nằm sẵn trong project thì skill tự tìm — một file có tên chứa
`ADS SCRIPTS`, một file chứa `working` hoặc `work file`. Khi không tìm thấy hoặc
tìm thấy nhiều file, skill dừng và yêu cầu chỉ rõ, không bao giờ đoán.

File của mỗi đối tác không cần cùng một layout. Parser xử lý được dấu phân cách
phẩy/chấm phẩy/tab/gạch đứng, tiêu đề tiếng Anh lẫn tiếng Việt, vài dòng thừa
phía trên header thật, và các alias thường gặp. Khi tên cột lạ, nó đoán cột dựa
trên nội dung — package name, URL Firebase, loại quảng cáo, ad-unit ID. Alias
khai báo rõ luôn được ưu tiên, và nếu hai cột có độ tin cậy ngang nhau thì audit
**dừng lại và báo**, thay vì chấm nhầm dữ liệu.

### Tài liệu được xin như thế nào

Skill không bao giờ audit khi thiếu tài liệu, và không bao giờ đoán. Nó đi lần
lượt theo 3 tầng:

| Tầng | Tình huống | Điều xảy ra |
| --- | --- | --- |
| **1** | 2 file CSV đã có sẵn trong project | Tự tìm thấy. Bạn không bị hỏi gì cả. |
| **2** | Thiếu tài liệu và chưa đưa link | AI hỏi xin cả 2 tài liệu — link hoặc file — **trước khi** chạy bất cứ thứ gì. |
| **3** | Có link nhưng không có quyền truy cập | Audit dừng và đưa 2 cách gỡ: đổi chế độ chia sẻ, hoặc tải file về rồi đưa đường dẫn. |

Nếu qua tầng 3 vẫn không có tài liệu, audit **dừng hẳn và báo rõ**. Nó sẽ không
xuất báo cáo nửa vời, không bịa ad-unit ID, không lấy giá trị của project base
thay thế — một bản audit thiếu dữ liệu nhưng trông như kết luận thì tệ hơn là
không audit.

Phần tự tìm file cũng không đoán bừa: không thấy file nào, hoặc thấy nhiều file
cùng lúc, đều rơi xuống tầng 2 chứ không tự chọn một cái.

## Kiểm tra những gì

Bộ rule được hiệu chỉnh theo project base Infinity, để một app làm đúng sẽ đạt
sạch.

- **Định danh** — package, tên app (lấy từ `res/values/strings.xml` mặc định,
  không lấy bản dịch), AdMob app id lấy từ `manifestPlaceholders` bản **release**,
  Firebase project, các token dịch vụ.
- **Config** — mọi key/ID trong hợp đồng phải có trong `ad_config.json` bản
  release, khớp tuyệt đối và có `isEnable`. `ad_config_debug.json` được miễn trừ
  có chủ đích.
- **Thứ tự khởi tạo** — `MobileAds.initialize` → `DevConfig.init` →
  `AdRemoteConfig.initializeFromAssets` → `ERainAd.init`, kèm các field version
  của DevConfig, các field `ERainAdConfig`, `intervalInterstitialAd`, danh sách
  chặn AppOpen, lifecycle observer và activity callbacks.
- **Cấu trúc màn hình** — Splash, Language, Onboarding, Home, Welcome phải là
  `Activity` riêng. Làm 5 màn này bằng Fragment trong một Activity duy nhất là
  lỗi. Fragment dùng làm *trang bên trong* các màn đó là đúng base.
- **Preload / load / show** — vị trí preload từng quảng cáo, đủ 4 gate khi load
  (`isEnable`, đã mua VIP, mạng, `getShouldDisplay*(config.enableUaCheck)`),
  hành vi ẩn container khi null, và inter chỉ chuyển màn từ callback.
- **Resume và Welcome** — cách chọn chế độ, 2 danh sách màn bị chặn, và các gate
  ngăn App Open chồng lên inter Welcome.
- **Banner** — gate config/mua VIP/container và `reloadIntervalSeconds`.

Vị trí chưa có mapping giữ trạng thái `NEEDS_MAPPING`. Điều static không chứng
minh được giữ `NEEDS_RUNTIME_PROOF` kèm kịch bản test. Cả hai đều **không phải
là đạt**.

## Kết quả

Ghi vào `ads-audit-output/` bên trong project được kiểm tra:

- `ads-audit-summary.md` — danh sách lỗi đầy đủ cho dev.
- `ads-audit-evidence.json` — payload tiếng Việt cho MKT, đã lọc bí mật.

Mã thoát: `0` khi không có lỗi tĩnh, `2` khi cần sửa, `1` khi đầu vào không hợp lệ.

Báo cáo luôn che giá trị Adjust, Facebook client và TikTok, và không kiểm tra
`app-ads.txt`.

## Vị trí quảng cáo riêng

Nếu một vị trí trả về `NEEDS_MAPPING`, copy `templates/ads-audit-overrides.yaml`
vào app rồi khai báo class và hàm gọi đã được duyệt, giữ nguyên key và ID trong
hợp đồng. Một số vị trí — `native_home`, `native_permission`,
`native_onboarding_fullscreen_*_4`, `banner_splash`, `reward_example` — có sẵn
trong `AdsManager` nhưng base không gắn vào màn nào, nên rơi vào đây là bình thường.

## Webhook Discord

Sau mỗi lần audit, skill gửi báo cáo ngắn cho MKT kèm file summary. Tắt cho một
lần chạy bằng `--no-webhook`. Đổi endpoint bằng `--webhook-url` hoặc biến môi
trường `ADS_AUDIT_WEBHOOK_URL` / `DISCORD_WEBHOOK_URL`.

## Chạy auditor trực tiếp

Dùng cho CI hoặc khi cần debug; cách chuẩn vẫn là gọi qua AI ở trên.

```bash
python3 scripts/run_audit.py --project /duong/dan/app --no-webhook
python3 scripts/run_audit.py --project . \
  --ads-script "https://docs.google.com/spreadsheets/d/<id>/edit#gid=0" \
  --working-file "./working file.csv"
```

## Đóng gói cho repo đối tác

```bash
python3 scripts/package_skill.py --skill-root . --output infinity-ads-audit.zip
```

## Tài liệu tham chiếu

- `references/base-code-reference.md` — code base thật: Gradle, `GlobalApp`,
  `AdsManager`, từng màn hình, các gate, schema config.
- `references/base-integration-rules.md` — cùng bộ rule ở dạng checklist.
- `references/placement-rule-map.yaml` — bằng chứng được duyệt cho từng vị trí.
