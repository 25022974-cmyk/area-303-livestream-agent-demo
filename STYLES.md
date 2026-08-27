# AREA_303 UI Style Guide & Design System

## 1. Design Philosophy
The AREA_303 Livestream Strategist interface provides a clean, professional, enterprise-grade command center for e-commerce livestream planning, on-air execution, and post-live analytics.
All pages in the application must strictly adhere to the unified layout, color palette, component design, and typography specified in this document.

---

## 2. Color Palette & CSS Variables

| Variable Name | Hex Code | Semantic Role |
| :--- | :--- | :--- |
| `--brand` | `#1e293b` | Primary Brand Navy (Headers, Primary Badges, Step Numbers) |
| `--brand-accent` | `#0284c7` | Brand Accent Cyan / Primary Action buttons & active indicators |
| `--brand-soft` | `rgba(30, 41, 59, 0.06)` | Subtle brand tint for highlights & light surfaces |
| `--bg` | `#f8fafc` | Global Page Background (Slate 50) |
| `--card-bg` | `#ffffff` | Card & Panel Background |
| `--line` | `#e2e8f0` | Border & Divider Lines (Slate 200) |
| `--text` | `#0f172a` | Primary Text Color (Slate 900) |
| `--muted` | `#64748b` | Muted Secondary Text (Slate 500) |
| `--ok` | `#16a34a` | Success / Positive Metrics / High Score (Emerald 600) |
| `--ok-bg` | `#dcfce7` | Success Badge Background (Emerald 100) |
| `--warn` | `#d97706` | Warning / Medium Attention (Amber 600) |
| `--warn-bg` | `#fef3c7` | Warning Badge Background (Amber 100) |
| `--danger` | `#dc2626` | Flash Sale / Danger / High Discount (Red 600) |
| `--danger-bg` | `#fee2e2` | Danger Badge Background (Red 100) |
| `--purple` | `#7c3aed` | Combo / Bundling Accent (Violet 600) |
| `--purple-bg` | `#ede9fe` | Combo Badge Background (Violet 100) |

---

## 3. Typography & Sizing

- **Font Family**: System UI stack: `ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`
- **Headings**:
  - `h1 / Page Title`: `font-weight: 800; font-size: 1.25rem (20px); letter-spacing: -0.02em`
  - `h2 / Section Heading`: `font-weight: 700; font-size: 1.00rem (16px); color: var(--brand)`
  - `h3 / Card Title`: `font-weight: 600; font-size: 0.875rem (14px)`
- **Body & Captions**:
  - Standard Body: `font-size: 0.875rem (14px); line-height: 1.5`
  - Small / Secondary / Labels: `font-size: 0.75rem (12px)`
  - Micro / Meta / Tooltips: `font-size: 0.6875rem (11px)`
- **Numeric & Financial Display**:
  - Monetary amounts in Vietnamese Dong: formatted with `k ₫`, `M ₫`, or comma-separated integers (`#,### ₫`).

---

## 4. Unified Components

### 4.1. Global Navigation Header (`header.navbar`)
- Fixed/sticky top navigation bar with:
  - Brand Logo Icon (`A3` in rounded indigo/navy badge)
  - Application Title & Subtitle ("AREA_303 · AI Livestream Strategist")
  - Active Shop Indicator & Shop Switcher dropdown
  - Lifecycle Breadcrumb Tracker (1. Pre-live → 2. On-air → 3. Post-live)
  - Quick Action button (Reset, Start Live, Review)

### 4.2. 3-Stage Progress Breadcrumb (`.progress-tracker`)
- Visual multi-step bar connecting `1 · Pre-live Planner` $\rightarrow$ `2 · On-air Assistant` $\rightarrow$ `3 · Post-live Review`.
- Current stage has solid accent dot with highlighted label; completed stages have checkmarked green dot.

### 4.3. Card Container (`.card`)
- Standard container for all sections:
  ```css
  background: var(--card-bg);
  border: 1px solid var(--line);
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05), 0 1px 2px rgba(0, 0, 0, 0.03);
  padding: 1.25rem;
  ```

### 4.4. Section Heading with Step Pill (`.section-h`)
- Includes a circular step badge (`.step-badge`):
  ```css
  display: inline-flex; align-items: center; justify-content: center;
  width: 24px; height: 24px; border-radius: 9999px;
  background: var(--brand); color: #ffffff; font-size: 12px; font-weight: 700;
  ```

### 4.5. KPI Metric Cards (`.stat-card`)
- Four-column grid of key indicators:
  - `.stat-label`: uppercase small muted description
  - `.stat-value`: bold large numeric metric
  - `.stat-sub`: contextual comparison or breakdown

### 4.6. Badges & Tags (`.badge-tag`)
- `.tag-hold`: Gray background with muted text (Keep standard price)
- `.tag-mild`: Cyan background with blue text (Mild discount 10-15%)
- `.tag-flash`: Red background with bold crimson text (Flash sale ≥25%)
- `.tag-hero`: Amber/Gold star badge (High HeroScore)
- `.tag-bundle`: Violet badge for smart combo products
- `.tag-gift`: Rose badge for Gift-with-purchase promotional items

### 4.7. Data Tables (`.data-table`)
- Compact, clean tables with sticky headers, zebra hover effects, numerical alignments (right-aligned), and responsive horizontal scrolling wrappers.

### 4.8. Buttons (`.btn`)
- `.btn-primary`: Brand accent background (`--brand-accent`), white text, hover elevation.
- `.btn-secondary`: White background, slate border, dark text.
- `.btn-ghost`: Transparent background, subtle hover fill.
- `.btn-danger`: Crimson background for live-ending or flash alert triggers.

---

## 5. Responsive Behavior
- **Mobile (< 768px)**: Single column layouts, collapsible filter bars, horizontal scroll on tables.
- **Tablet (768px - 1024px)**: 2-column KPI grid, stacked run-of-show timeline.
- **Desktop (≥ 1024px)**: Full multi-column dashboard, split view on On-air assistant (timeline on left, live script & cue controls on right).
