# Đặc tả sản phẩm — AI Livestream Strategist cho Bibica
**Cuộc thi AREA_303 · Người 3: "Khi nào live, bán giá nào, tung voucher lúc nào?"**

> Tài liệu source-of-truth. Phiên bản trực quan (sơ đồ pipeline + wireframe dashboard) nằm ở
> HTML artifact đi kèm. Cập nhật file này khi chốt thay đổi với nhóm.

---

## A. Tổng quan sản phẩm

**Tên:** AI Livestream Strategist — Decision Engine cho phiên live Bibica trên Shopee VN.

**Mục tiêu:** Trước mỗi phiên live, AI đề xuất một **kế hoạch triển khai** hoàn chỉnh gồm:
- Sản phẩm nào đưa lên live và theo thứ tự nào (Hero Score)
- Mỗi sản phẩm giữ giá / giảm nhẹ / flash sale, với mức giảm cụ thể
- Combo nào ghép (hero + SKU bán chậm + quà tặng)
- Voucher nào tung (số tiền, ngưỡng chi tối thiểu, thời điểm tung)
- Khung giờ live tối ưu

**Điểm khác biệt cốt lõi:** AI **học lại sau mỗi phiên** — lưu kết quả thực tế của phiên trước
(thực tế bán bao nhiêu so với dự đoán, voucher nào được dùng, combo nào thoát hàng), rồi
retrain model và cập nhật tham số trước phiên sau. Đây không phải roadmap — đây là cơ chế
thật chạy trong pipeline.

**Sản phẩm nộp (2 thành phần, một nguồn dữ liệu):**
1. **Code pipeline** chạy end-to-end trên `Data/country_code=vn/`, ra file đề xuất mỗi phiên.
2. **Dashboard web tương tác** demo pipeline: nhập ngân sách/thời gian → xem đề xuất + giải thích.

**Khán giả:** ban giám khảo AREA_303 (mix kỹ-thương mại) → dashboard phải dễ hiểu cho người
phi-technical, code phải đủ rõ ràng để chứng minh tính khả thi.

**Luồng dữ liệu chung (đơn giản):**
```
Data/country_code=vn  →  Loader  →  [Module 1..5]  →  Learner loop  →  recommendation_<session>.json
                          ▲                              │
                          │            learning_state.json ┘
                          └──── retrain trước phiên sau ──┘
```

---

## B. Kiến trúc pipeline & Contract các module

Pipeline gồm 1 loader + 5 module quyết định + 1 learner loop. Đây là contract chuẩn theo đề bài
(Nguyễn 3). Module nào đã có code trong `bibica_methods.py` / `bibica_playbook.py` sẽ được đồng bộ
vào contract này; phần nào chưa có sẽ bổ sung.

### 0. Loader (L)
**Input:**
- `Data/country_code=vn/dataset=products/shop_id=*/products.csv` (Bibica `213989179` + 9 đối thủ)
- `Data/country_code=vn/dataset=category_list/shop_id=*/category_list.csv`
- `pricing.json` và `daily.json` của Bibica (item_daily 3 ngày snapshot)

**Output:** `data_pool`: danh sách SKU chuẩn hoá, mỗi SKU gồm tối thiểu:
`item_id, shop_id, name, price, price_original, discount_percent, monthly_sold_value,
rating_count, rating, ctime, voucher_discount, voucher_min_spend, voucher_start_time,
voucher_end_time, has_voucher, line` (line ∈ Zoo/Quasure/Gooka/Sumika/ Other).

**Trách nhiệm:** gom 10 shop, chuẩn hoá kiểu, bỏ dòng thiếu `item_id`, phân dòng sản phẩm cho
Bibica bằng từ khóa trong tên (Zoo/Quasure/Gooka/Sumika) vì Bibica chỉ có 1 catid chung.

---

### Module 1 — Quyết định giá: giữ / giảm nhẹ / flash sale
**Câu trả lời:** SKU này nên giữ giá hay giảm? Giảm bao nhiêu %?

**Input:** `data_pool` (đặc biệt: history giá vs sold của Bibica + 9 đối thủ, ≥2 snapshot/SKU).

**Output:** cho mỗi SKU Bibica:
```json
{
  "item_id": "...",
  "scenario": "hold | mild | flash",
  "discount_pct": 0 | 10..15 | 25+,
  "expected_revenue_hold": 0,
  "expected_revenue_mild": 0,
  "expected_revenue_flash": 0,
  "elasticity_beta": -1.7,        // hệ số co giãn riêng Bibica, tách nhiễu ngành
  "confidence": "high | medium | low",
  "used_fallback": false          // true nếu β không ước lượng được, dùng -1
}
```

**Hàm chính:**
- `estimate_elasticity(rows)` — hồi quy log-log OLS **fixed effects**, stdlib thuần
  (tự viết, không numpy/sklearn):
  ```
  log(Δsold) = β·log(Δprice) Σ_k γ_k·shop_dummy[shop_id=k] + Σ_l δ_l·line_dummy[line=l] + ε
  ```
  - `shop_fe`: dummy `shop_id` — 10 cấp (Bibica + 9 đối thủ) → tách đặc thù từng shop.
  - `cat_fe`: vì Bibica dùng chung 1 `catid`, thay bằng `line_or_catid` = dòng sản phẩm
    (Zoo/Quasure/Gooka/Sumika cho Bibica) + `catid` thật cho 9 đối thủ → tách nhiễu ngành.
  - Cài đặt: dựng ma trận thiết kế X = [log(Δprice), dummies...], giải
    β = (X'X)⁻¹ X'y bằng tay (giải ma trận qua phép khử Gauss, ~50 dòng stdlib).
  - Tách phần "do price Bibica" vs "do xu hướng ngành" bằng 9 đối thủ
    (difference-in-differences đơn giản).
- `expected_revenue(discount_pct, beta, ms_baseline)` — mô phỏng doanh thu kỳ vọng ở từng mức.
- `decide(elasticity_info)` — so 3 kịch bản, chọn doanh thu kỳ vọng cao nhất, kẹp trong khoảng
  discount thực tế Bibica (~17% trung bình, tối đa 36%).

**Ràng buộc nghiệp vụ:** không đề xuất flash sale > 36% (cao nhất từng thấy); flash sale chỉ
khi expected_revenue_flash > mild với biên an toàn.

---

### Module 2 — Hero Score (xếp hạng SKU lên live)
**Câu trả lời:** Trong phiên này, sản phẩm nào nên ghim đầu, theo thứ tự nào?

**Input:** danh sách SKU ứng viên của phiên (chọn theo line + ngân sách).

**Output:**
```json
{
  "item_id": "...", "name": "...", "line": "Zoo",
  "hero_score": 0.0..1.0,
  "components": {"ms": 0.0..1.0, "rc": 0.0..1.0, "rating": 0.0..1.0,
                 "headroom": 0.0..1.0, "freshness": 0.0..1.0},
  "rank": 1
}
```

**Hàm:**
- `hero_score(sku)` = `0.30·ms + 0.25·rc + 0.15·rating + 0.15·headroom + 0.15·freshness`
- `freshness(sku)` = `exp(-Δngày/30)`, Δngày từ `ctime`.
- **Chuẩn hoá min-max theo từng dòng (Zoo/Quasure/Gooka/Sumika)** trước khi nhân trọng số —
  tránh dòng Zoo (trẻ em, bán chạy) lấn át hoàn toàn Quasure trong mọi phiên.

---

### Module 3 — Chọn khung giờ live
**Câu trả lời:** Phiên này nên bắt đầu giờ nào, kết thúc giờ nào?

**Input:** `voucher_start_time`/`voucher_end_time` của Kinh Đô (shop có nhãn LIVE thật) + giờ
nhiều shop cùng bật voucher khuyến mãi trên benchmark 10 shop.

**Output:**
```json
{
  "start_hour": 20, "end_hour": 22,
  "reason": "Kinh Đô gói voucher 20-22h + 7/10 shop cùng bật voucher",
  "confidence": "low",          // luôn low — suy luận gián tiếp
  "evidence": {"kinh_do_windows": [...], "industry_overlap_score": 0.0..1.0}
}
```

**Ghi chú Phase 2:** khi Bibica tự log viewer/watch-time/đơn theo giờ → thay proxy bằng ranking
model thật. Dashboard thể hiện đây là gợi ý tin cậy thấp.

---

### Module 4 — Ghép combo
**Câu trả lời:** SKU bán chạy nên ghép với SKU bán chậm nào, tặng kèm quà gì để thoát hàng tồn?

**Input:** Hero Score cao (Module 2) + danh sách SKU bán chậm (freshness thấp, ms thấp) + SKU
"quà tặng không bán" + combo có sẵn từ parse tên.

**Output:**
```json
{
  "combo_id": "...",
  "type": "bundled | gift_with_purchase",
  "hero_item_id": "...", "hero_name": "...",
  "slow_item_id": "...", "slow_name": "...", "slow_freshness": 0.12,
  "gift_item_id": "...",          // SKU "quà tặng không bán", có thể null
  "bundle_price": 0, "bundle_discount_pct": 0,
  "gift_cost": 0                   // chia sẻ ngân sách với Module 5
}
```

**Hàm & quy tắc:**
- `parse_existing_combos(name)` — trích combo có sẵn ("Combo 3 Kẹo Tứ Quý…") làm khởi điểm.
- `group_by_line` — chỉ ghép cùng dòng hoặc dòng tương thích (không ghép Zoo với Quasure).
- `pick_slow_sku(candidates)` — SKU có freshness thấp nhất (tồn kho lâu nhất) ưu tiên trước.
- 2 kiểu dùng song song: **bundled** (giảm nhẹ trên tổng, giảm chủ yếu đổ vào SKU chậm) hoặc
  **gift_with_purchase** (mua hero tặng kèm SKU chậm; chi phí = giá vốn × số đơn dự kiến).
- **Chi phí gift_with_purchase đi chung ngân sách với voucher ở Module 5**, không tách riêng.

---

### Module 5 — Đề xuất voucher
**Câu trả lời:** Mỗi SKU nên có voucher số tiền bao nhiêu, ngưỡng chi tối thiểu bao nhiêu, trong
giới hạn ngân sách tháng?

**Input:** `data_pool` gộp (Bibica 96 SKU + 9 shop) + ngân sách voucher tháng + chi phí mua-tặng
(từ Module 4) + α, β hiện tại (từ learner).

**Output:**
```json
{
  "item_id": "...", "name": "...",
  "discount_pct": 0, "voucher_amount": 0,
  "min_spend": 0, "price_final": 0,
  "expected_sales": 0, "voucher_cost": 0,
  "is_selected": false                // true nếu knapsack chọn cấu hình này
}
```
Kèm bảng tổng: `budget`, `used`, `remaining`, `total_est_sales`, `n_selected`.

**Hàm (giữ nguyên `bibica_methods.py`, KHÔNG cài GBT):**
- `estimated_sales(ms, A, B, C, α, β)` = `ms × (1 + α·B/price_original − β·C/200000)`
  - `A = price − voucher_discount` (giá thực trả), `B = price_original − A`, `C = voucher_min_spend`.
  - α = 0.5, β = 0.2 mặc định; **learner cập nhật sau mỗi phiên**.
- `gen_config_grid` — lưới 168 cấu hình/SKU (discount 7×voucher 6×min_spend 4).
- `knapsack(budget)` — chọn 1 cấu hình/SKU tối đa tổng estimated_sales, ràng buộc
  `Σ(voucher_discount × estimated_sales) ≤ ngân sách voucher/tháng`, cộng nhánh chi phí
  mua-tặng (2 loại "vật phẩm": voucher tiền + quà tặng).

> Quyết định: **không học hàm máy**. "Mô hình" Module 5 = công thức `estimated_sales` +
> knapsack. Ưu điểm: stdlib, không train, không overfit; learner chỉ cần điều 3 tham số.
> Hệ quả Phase 2: không phải retrain gì khi có dữ liệu thật — cùng code, đổi đầu vào.

---

### Learner loop — AI học lại sau mỗi phiên
**Câu trả lời:** Sau phiên live vừa rồi, AI cập nhật gì để phiên sau chính xác hơn?

**Đây là phần dạy thực sự, không phải roadmap.**

**Input phiên trước (actual):**
```json
{
  "session_id": "...", "date": "...",
  "actual": [
    {"item_id": "...", "scenario_used": "flash", "discount_used_pct": 28,
     "estimated_sales": 120, "actual_sales": 95, "voucher_amount_used": 30000,
     "voucher_redeemed": true, "combo_sold": true}
  ]
}
```

**Cập nhật `learning_state.json`:**
```json
{
  "version": 1,
  "last_session_id": "...",
  "params": {
    "alpha": 0.5,        // hệ số thưởng mức giảm B  → tinh chỉnh theo error
    "beta": 0.2,         // hệ số phạt ngưỡng C       → tinh chỉnh theo redeemed_rate
    "elasticity_beta_by_line": {"Zoo": -1.7, "Quasure": -0.9, "Gooka": -1.2, "Sumika": -1.1}
  },
  "metrics": {
    "n_sessions": 0,
    "rolling_mape_estimated_vs_actual": 0.0,  // sai số dự đoán, càng giảm càng tốt
    "rolling_redeem_rate": 0.0,                // % voucher được dùng
    "lift_vs_hold": 0.0                        // doanh thu so với kịch bản giữ giá
  },
  "bounds": {"alpha": [0.1, 1.0], "beta": [0.05, 0.5], "discount_pct": [0, 36]}
}
```

**Cơ chế học:**
1. **Tính sai số dự đoán** phiên trước: `MAPE = mean(|estimated − actual|/actual)`.
2. **Cập nhật α**: nếu estimated_sales hệ thiên cao (thực tế thấp hơn dự đoán nhiều) → giảm α
   (mức giảm giá nền đang đóng góp quá nhiều) ; ngược lại tăng. Cắt theo `bounds`.
3. **Cập nhật β** theo `redeem_rate`: voucher ít được dùng → β tăng (phạt ngưỡng khó hơn);
   được dùng nhiều → β giảm để khuyến khích.
4. **Cập nhật elasticity_beta_by_line**: re-run hồi quy trên toàn history cộng thêm snapshot
   mới của phiên vừa rồi (actual_sales như một điểm thực nghiệm).
5. **Từ phiên sau**: Module 1 & Module 5 đọc `learning_state.json` lấy α, β, β_elasticity mới.

> **Quyết định kỹ thuật đã chốt (2026-08-24):**
> - **Không dùng GBT.** Module 5 giữ nguyên công thức `estimated_sales` trong
>   `bibica_methods.py` — không học hàm máy. Hệ quả: learner chỉ cập nhật **3 tham số**
>   (α, β, β_elasticity_by_line), cực nhẹ, chạy stdlib.
> - **Module 1 = OLS fixed effects stdlib thuần.** Tự viết OLS với dummy `shop_id` (10 cấp)
>   + dummy `line_or_catid` (Zoo/Quasure/Gooka/Sumika cho Bibica, catid thật cho 9 đối thủ).
>   Không numpy/sklearn — giữ nguyên nguyên tắc "stdlib only" của `bibica_playbook.py`,
>   tránh xung đột `inspect.py` có sẵn.
> - **Hệ quả Phase 2:** khi có dữ liệu Bibica thật, **không cần train lại từ đầu.**
>   `learning_state.json` tích lũy từ phiên mô phỏng làm *warm start*; cùng code,
>   chỉ đổi đầu vào `--learn_from` sang actual thật. Learner loop tiếp tục cập nhật incremental.

**Chạy trong pipeline:** `pipeline.py --learn_from session_<id>.json` → ghi đè `learning_state.json`
→ phiên sau tự dùng tham số mới. Dashboard có tab "Học" để xem evolution α/β/MAPE qua phiên.

---

## C. Wireframe Dashboard

Dashboard câu chuyện xuyên 7 tab. Nhập liệu (sidebar trái) dùng chung cho tất cả tab.

**Nhập liệu chung (sidebar trái):**
- Ngày live (date)
- Ngân sách voucher tháng (VND) — default 500M
- Dòng sản phẩm (multi-select: Zoo/Quasure/Gooka/Sumika)
- Số SKU muốn đưa lên live (slider 3–15)
- [Generate Recommendation] (nút chính)

### Tab 1 — Tổng quan phiên live
- **KPI cards (hàng trên):** Doanh thu kỳ vọng phiên · Tổng voucher dùng (đã dùng/ngân sách) ·
  #SKU lên live · #Combo · Doanh số tăng so với giữ giá (lift).
- **Timeline phiên (hàng dưới):** thanh ngang t:00 → t:End, đánh dấu thời điểm tung voucher,
  thời điểm flash sale, mỗi mốc kèm annotation lý do ("tung voucher sau 30–45 phút khi đã xem demo").
- **Mục tiêu:** giám khảo phi-technical hiểu ngay phiên này sẽ diễn ra thế nào.

### Tab 2 — Hero Score (Module 2)
- **Bảng xếp hạng SKU** (sortable): rank, tên, line, hero_score (cột thanh bar), 5 sub-score
  chip (ms/rc/rating/headroom/freshness), nút "đưa vào giỏ live".
- **Cho phép:** toggle hiển thị chuẩn hoá theo dòng vs gộp chung (minh hoạ vì sao phải chuẩn hoá
  theo line — Zoo không lấn át Quasure).
- **Mini chart:** bar chart top 8 theo hero_score, tô màu theo line.

### Tab 3 — Chiến lược giá (Module 1)
- **Bảng mỗi SKU:** scenario (hold/mild/flash badge màu), discount_pct, expected_revenue ở 3
  kịch bản, elasticity_beta, confidence.
- **Bar chart so sánh** 3 kịch bản doanh thu cho 1 SKU (click hàng → chart cập nhật).
- **Chú thích:** "Flash sale chỉ khi doanh thu > mild + biên an toàn; ≤36%".

### Tab 4 — Combo (Module 4)
- **Card mỗi combo:** hero (ảnh/mã) + slow item (kèm freshness thấp badge) + gift (nếu có),
  type (bundled/gift), giá gom, % giảm.
- **Cột bên:** danh sách SKU bán chậm ưu tiên (freshness thấp → cao), hover lý do chọn.
- **Tổng chi phí mua-tặng** (badge) — chạy chung ngân sách voucher.

### Tab 5 — Voucher (Module 5)
- **Bảng đề xuất SKU:** discount% | voucher_amount | min_spend | price_final | expected_sales |
  voucher_cost (cột highlighted nếu selected).
- **Thanh ngân sách:** progress bar `đã dùng / ngân sách`, breakdown voucher tiền vs mua-tặng.
- **Heat map:** trục discount% × voucher_amount, ô tô màu expected_sales → thấy vùng tối ưu 1 SKU.

### Tab 6 — Khung giờ (Module 3)
- **Bản đồ nhiệt 24h:** trục giờ × интенсивность voucher ngành (10 shop), overlay khung giờ
  Kinh Đô.
- **Kết luận card:** "Đề xuất 20–22h · Confidence LOW · Lý do …".
- **Roadmap Phase 2** (collapse): "khi Bibica có log viewer → thay proxy bằng ranking model".

### Tab 7 — Học (Learner loop)
- **Line chart:** α, β, MAPE, redeem_rate, lift qua các phiên (trục x = session_id).
- **Bảng:** phiên gần nhất, actual vs estimated từng SKU, đánh dấu over/under.
- **Nút:** "Nhập kết quả phiên vừa rồi" (upload session_<id>.json) → retrain → cập nhật chart.
- **Mục tiêu:** chứng minh trực quan "AI tự động chính xác hơn qua thời gian".

---

## D. Sản phẩm nộp & cách chạy

**Cấu trúc nộp (dự kiến):**
```
model_bibica/
├── pipeline.py                 # orchestrator end-to-end (loader → 5 mod → learner → output)
├── modules/
│   ├── m1_price.py
│   ├── m2_heroscore.py
│   ├── m3_timeslot.py
│   ├── m4_combo.py
│   ├── m5_voucher.py            # wrap bibica_methods.py có sẵn
│   └── learner.py               # NEW: online learning
├── bibica_methods.py            # code Module 5 + elasticity đã có
├── dashboard.html               # dashboard tương tác (nâng cấp)
├── learning_state.json          # state học (mới mỗi phiên)
├── recommendations/
│   └── recommendation_<session>.json
└── spec/DELIVERABLE_SPEC.md     # file này
```

**Chạy pipeline (CLI):**
```
python pipeline.py --date 2026-08-24 --budget 500000000 --sku_count 8
# → recommendations/recommendation_2026-08-24.json + dashboard đọc file này

python pipeline.py --learn_from recommendations/session_2026-08-24_actual.json
# → cập nhật learning_state.json
```

**Chạy dashboard:** mở `dashboard.html` (static, stdlib, không backend) → chọn input sidebar →
Generate → load recommendation JSON hiển thị 7 tab.

**Data:** dùng `Data/country_code=vn/` (đã có trong repo).

---

## E. Ghi chú cho nhóm
- Module 5 + phần Module 1 đã có code trong `bibica_methods.py` — wrap lại theo contract, KHÔNG
  viết từ đầu. Đồng bộ tên hàm + schema output với đặc tả này.
- Module 2/3/4 + Learner loop là phần cần xây mới.
- Dashboard nâng cấp từ `dashboard.html` (66KB) có sẵn — giữ style, thêm 7 tab + sidebar input.
- Online learning là USP: đảm bảo `learner.py` chạy thật và dashboard Tab 7 hiển thị được.
- Mọi con số trong đặc tả (500M budget, 168 config, weight 30/25/15/15/15, α=0.5, β=0.2, cap
  36% discount) lấy từ đề bài `Đề bài 5.docx` — không tự chế.
