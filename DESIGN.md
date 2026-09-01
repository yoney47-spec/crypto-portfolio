# CryptoFolio Design System

> Quiet financial clarity: an Apple-like dark interface with Linear-like precision.

This file is the design contract for CryptoFolio. It adapts ideas from high-quality
product references into an original system for a Japanese crypto portfolio. It is a
reference, not a request to reproduce any source website.

## Product character

- Calm, trustworthy, and native-app-like.
- Financial information is the visual focus; decoration stays quiet.
- Public pages feel polished and read-only. Admin pages feel capable without looking
  like a separate product.
- Japanese labels should sound natural. Avoid ornamental English, emoji-heavy labels,
  neon effects, and generic "AI dashboard" styling.

## Core principles

1. **Darkness is a canvas.** Build hierarchy with stepped neutral surfaces and thin
   borders, not glowing gradients or stacked shadows.
2. **One action color.** Blue is for primary actions, focus, links, and selected states.
3. **Financial colors are semantic.** Green means positive/success, red means
   negative/error, and yellow means warning. Never rely on color alone.
4. **Asset colors are data.** Coin brand colors may appear inside charts and asset
   marks, but must not become general UI accents.
5. **Numbers are stable.** Use tabular numerals for money, quantities, rates, and
   percentages. Currency symbols must follow the selected display currency.
6. **Motion explains state.** Transitions are short and subtle. Respect reduced-motion
   preferences and never animate continuously for decoration.

## Tokens

The implementation sources are `styles/main.css` for CSS and
`components/design_tokens.py` for Plotly. Keep their shared values aligned.

### Color

| Role | Token | Value | Usage |
|---|---|---:|---|
| Canvas | `--color-canvas` | `#0f0f10` | App background |
| Surface 1 | `--color-surface-1` | `#1c1c1e` | Cards, sidebar, forms |
| Surface 2 | `--color-surface-2` | `#242426` | Hover and nested regions |
| Surface 3 | `--color-surface-3` | `#2c2c2e` | Selected and raised controls |
| Primary text | `--color-text-primary` | `#f5f5f7` | Headings and important values |
| Secondary text | `--color-text-secondary` | `#aeaeb2` | Body copy and labels |
| Muted text | `--color-text-muted` | `#8e8e93` | Metadata and helper copy |
| Dim text | `--color-text-dim` | `#636366` | Disabled and low-priority text |
| Action | `--color-action` | `#0a84ff` | Primary action and focus |
| Action hover | `--color-action-hover` | `#2997ff` | Blue control hover only |
| Positive | `--color-positive` | `#30d158` | Gains and success |
| Negative | `--color-negative` | `#ff453a` | Losses and errors |
| Warning | `--color-warning` | `#ffd60a` | Warnings and attention |
| Hairline | `--color-border-subtle` | `rgba(255,255,255,.08)` | Default structure |
| Hairline hover | `--color-border-hover` | `rgba(255,255,255,.16)` | Interactive boundary |

Do not add a new general-purpose accent when an existing semantic color fits. Purple,
cyan, orange, and individual coin colors are allowed for data visualization only.

### Typography

- UI and body: `-apple-system`, `BlinkMacSystemFont`, `SF Pro Text`,
  `Helvetica Neue`, `Noto Sans JP`, sans-serif.
- Display: the same system stack using the display face where available.
- Data: prefer the system stack with `font-variant-numeric: tabular-nums`. Use the mono
  stack only for genuinely technical metadata, not every financial value.
- Body: 14px / 1.5. Do not put essential text below 12px.
- Page title: responsive 27-34px, weight 700, tight tracking.
- Section title: 16-19px, weight 600-650.
- Avoid weight 800+ and wide uppercase labels. Japanese labels are sentence case.

### Spacing

Use the 4px base grid: `4, 8, 12, 16, 24, 32, 48`.

- Element gap: 8-12px.
- Card padding: 16-24px; feature card padding may reach 28-32px.
- Section gap: 24-32px inside the application shell.
- Page max width: 1240px.
- Mobile horizontal padding: 16px.

### Shape and elevation

- Small controls: 10px radius.
- Standard cards and inputs: 14px radius.
- Feature cards: 18-22px radius.
- Pills: only statuses, chips, and segmented controls.
- Prefer a 1px hairline border. Use shadows sparingly and at low opacity.
- No glow around cards, text, chart lines, or status dots.
- No decorative gradients on cards, buttons, headings, or brand marks.

### Motion

- Fast interaction: 160ms.
- Normal entrance/change: 320ms.
- Easing: `cubic-bezier(0.22, 1, 0.36, 1)`.
- Hover movement is limited to 1-2px; active controls may scale to 0.985.
- All motion must collapse under `prefers-reduced-motion: reduce`.

## Component rules

### Application shell

- Keep the sidebar reopen control visible and reachable.
- Desktop content is centered at a maximum width of 1240px.
- The sticky header may use subtle backdrop blur; it must remain legible without blur.
- Public/admin state is shown with a compact text-and-dot status, not a large banner.

### Cards

- Default surface is Surface 1 with a subtle border.
- Hover may step to Surface 2 and move up at most 2px.
- Use spacing, typography, and surface steps before adding shadow.
- A card should have one clear reading order: label, value, supporting context.

### Buttons and inputs

- Only the primary action uses solid blue. Secondary actions use neutral surfaces.
- Controls are at least 42px tall where practical.
- Focus uses the action color with a crisp 1px ring.
- Destructive actions use red semantics and still require a clear text label.
- Do not make all actions pill-shaped.

### Status and performance

- Gains/success use green plus a sign, arrow, or word.
- Losses/errors use red plus a sign, arrow, or word.
- Neutral values use muted text.
- Never use green as a decorative accent or red simply to attract attention.

### Charts

- Plot and paper backgrounds are transparent over the app surface.
- Titles use secondary text; axes use muted text; grid lines use a 3% white hairline.
- The standard portfolio trend line uses action blue.
- Coin colors identify series only. "Other" uses dim neutral gray.
- Use tabular numerals and the selected currency symbol in totals, axes, and hover text.
- Donut slices use a canvas-colored separator so adjacent assets remain distinct.
- Chart labels must remain readable at mobile widths without forcing dense legends.

### AI commentary

- Treat AI commentary as supporting analysis, not a magical feature.
- Use the same neutral card language as the rest of the product.
- Do not use purple gradients, sparkles, robot emoji, or glowing borders.
- Always show the commentary date and keep the body readable.

## Responsive rules

- Break multi-column summaries to one column at 768px.
- Preserve value hierarchy and currency labels before secondary metadata.
- Avoid horizontal scrolling for forms, tables, and primary cards.
- Tap targets remain usable on iPhone-sized screens.
- Check both public read-only and authenticated admin states after layout changes.

## Accessibility

- Target WCAG AA contrast for text and interactive controls.
- Do not communicate meaning through color alone.
- Keep visible keyboard focus and meaningful control labels.
- Respect the user's reduced-motion setting.
- Use natural Japanese wording and expose full values in accessible text where visual
  truncation is necessary.

## Do

- Reuse tokens before inventing values.
- Prefer neutral surfaces and hairlines to gradients and shadows.
- Keep important numbers visually stable with tabular numerals.
- Test USD and JPY whenever currency-facing UI changes.
- Review desktop, mobile, public, and admin states.

## Do not

- Recreate Apple, Linear, Origin Financial, or any other product exactly.
- Introduce neon, glass everywhere, oversized emoji, or ornamental English.
- Use multiple competing action colors.
- hard-code `$` or `¥` where the user can switch currency.
- Hide the sidebar toggle or weaken authenticated/public state clarity.
- change Supabase, authentication, or market-data behavior during a visual-only task.
