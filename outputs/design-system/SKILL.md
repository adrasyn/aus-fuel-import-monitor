---
name: style-petrol-press
description: Editorial data-journalism design system. Use when building dashboards, data visualisations, or long-form reading interfaces that should feel like a serious newspaper or research publication. Pairs Instrument Serif headlines with Inter body, a restrained grey hierarchy, and a petrol-teal → bright-green accent ramp (#034159 → #0CF25D) for binary states and continuous data scales.
---

# Petrol Press

A restrained, editorial design system for data-heavy interfaces. The aesthetic borrows from the Financial Times, The Economist, and broadsheet front pages: large light-weight serif headlines over hairline rules, tiny tracked-out uppercase eyebrow labels, and dense type that respects the reader's time. Colour is used sparingly and meaningfully — almost everything is monochrome grey, and the brand accent appears only where it carries information.

Use this style when you want the work to read as *considered* rather than *designed* — the kind of page where the data does the talking and the chrome gets out of the way.

## Voice & principles

- **Quiet by default.** Most of the page is set in greys. Colour is reserved for data, status, and one or two anchor moments.
- **Type carries the page.** Hierarchy is built primarily through type — size, weight, serif-vs-sans, tracking — not through panels, shadows, or borders.
- **Hairlines, not boxes.** Sections divide with 1px hairline rules. The masthead gets a single 2.5px rule beneath it. No drop shadows. No rounded card containers.
- **Tiny labels, generous numbers.** Stats are set in a light serif at 2.5–3× the body size. The label beneath them is 10px uppercase with 0.15em tracking — almost a whisper.
- **Footnotes are first-class.** Methodology, caveats, sources, and timestamps sit in 9–10px label-light grey and run *with* the content, not hidden in a separate panel.
- **No emoji, no icons-as-decoration.** Icons appear only when they encode meaning (e.g. a vessel marker on a map).

## Typography

| Role          | Family             | Size                | Weight  | Notes                                       |
| ------------- | ------------------ | ------------------- | ------- | ------------------------------------------- |
| Display       | Instrument Serif   | 24–30px (text-2xl/3xl) | 400     | Italics-leaning forms; never bold.          |
| Stat numerals | Instrument Serif   | 30px (text-3xl)     | 300     | `font-light` — wispy, almost editorial.     |
| Body          | Inter              | 14–16px             | 400     | Default reading weight.                     |
| UI label      | Inter              | 10px                | 400     | `uppercase`, `tracking: 0.15em`, grey-500.  |
| Footnote      | Inter              | 9–10px              | 400     | `text-label-light` (grey-400), italic OK.   |

Load from Google Fonts:
```
https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600;700&display=swap
```

**Tracking tokens**
- `tracking-label: 0.15em` — for any uppercase label, eyebrow, axis title, legend item.
- Body and headlines use default tracking. Never letter-space the serif.

## Colour

### Greyscale (the page)
The page is mostly this scale. Pick from it for text, rules, axis ticks, fills.

| Token            | Hex     | Use                                                  |
| ---------------- | ------- | ---------------------------------------------------- |
| `ink`            | #111827 | Body copy, headlines, heavy rules.                   |
| `ink-soft`       | #374151 | Secondary text, dense chart fills.                   |
| `label`          | #6b7280 | Uppercase labels, axis ticks, muted body.            |
| `label-light`    | #9ca3af | Footnotes, timestamps, tertiary metadata.            |
| `rule-soft`      | #d1d5db | Hairline borders on light panels.                    |
| `rule`           | #e2e8f0 | Default 1px section divider.                         |
| `panel`          | #f8fafc | Subtle table-row or callout background.              |
| `paper`          | #ffffff | Page background. Always.                             |

### Accent — Petrol → Lime
The brand carries through one diatonic ramp. Use it for binary state pairs (low/high, off/on, idle/active) and as the gradient stops for any continuous data scale.

| Token        | Hex     | Use                                                       |
| ------------ | ------- | --------------------------------------------------------- |
| `accent-low` | #034159 | Low end of any scale. Off / idle / minimum state.         |
| `accent-high`| #0CF25D | High end of any scale. On / active / maximum state.       |

**Continuous gradient (linear).** For heatmaps, choropleths, density maps, any value-encoded fill:
```css
background: linear-gradient(90deg, #034159 0%, #0CF25D 100%);
```

**5-stop discrete ramp** (HSL-interpolated; safe for stacked bars, swatch legends, sequential categorical scales where the order is meaningful):

| Stop | Hex     | Swatch role                  |
| ---- | ------- | ---------------------------- |
| 0    | #034159 | Deepest — minimum            |
| 1    | #057D80 | Petrol teal                  |
| 2    | #06A88A | Sea green                    |
| 3    | #08CD7B | Spring green                 |
| 4    | #0CF25D | Brightest — maximum          |

Rules of thumb:
- **Never use the ramp purely decoratively.** If a fill isn't encoding a value, use grey.
- **Don't pair the accent with red/blue.** If you need a contrasting alert state, use `#dc2626` *only* for genuine warnings (errors, experimental flags, breaking news) and never alongside ramp colours.
- **For colour-blind safety**, anything plotted on the ramp should also be encoded by position or label — the teal→green transition is not safe on its own for protan/deutan viewers.

## Space & rhythm

- **Container.** `max-w-7xl` (1280px), `px-4 sm:px-6`, `py-8`. Single column; the page is for reading.
- **Section spacing.** `mb-6` between major blocks. `pt-6` after a top rule, `pb-3` before a bottom rule.
- **Masthead rule.** 2.5px solid `ink` beneath the title block. This is the only heavy rule on the page.
- **Section rules.** 1px `rule` between sub-sections.
- **Stat groups.** Flex with `gap-x-8 gap-y-4` between stats. Numbers align to the *baseline*, not the centre.

## Components

### Masthead
- Eyebrow: 10px uppercase, `tracking-label`, `text-label`.
- H1: Instrument Serif, 24–30px, leading-tight, set in `ink`.
- Sub-deck: 11px italic, `text-label-light`.
- Right rail (optional): 10px `text-label-light`, right-aligned, two lines — "Updated daily at 6am AEST" / "Last updated [timestamp]".
- Closes with a 2.5px `ink` rule, then `mb-6`.

### Stat
A single number with a label beneath.
```html
<div>
  <div class="font-headline text-3xl font-light">12.4B</div>
  <div class="text-[10px] uppercase tracking-[0.15em] text-[#6b7280]">Litres en route</div>
</div>
```
Group stats in a row with `gap-x-8`. For a secondary row of stats beneath a primary row, separate with `pt-4 border-t border-[#e2e8f0]`.

### Section header (above charts/tables)
A 10px uppercase `tracking-label` label sits 8px above the artwork; a 9px `label-light` footnote sits 8px below.

### Footnote
Always 9–10px, `text-label-light`, `leading-relaxed`. Hyperlinks: underline, `hover:text-label`. No bold.

### Footer
1px top rule, `pt-6 mt-8 pb-8`. Two 10px paragraphs in `label-light`: methodology disclaimer, then byline.

## Charts

- **Axis & grid:** ticks 10px in `label`. Grid lines `#e2e8f0`, `strokeDasharray="3 3"`.
- **Default fill:** anything not value-encoded uses the grey ramp `#111827 → #d1d5db`.
- **Value-encoded fill:** use the petrol→lime ramp. A high-low diverging scale stays inside the ramp — do not introduce a third hue.
- **Legend & tooltip:** 10px Inter on `#fff` with a 1px `#d1d5db` border and 4–6px padding. No drop shadow.
- **Annotations** (e.g. "Experimental", "No data"): 10px medium-weight, rotated -90° over the bar if vertical space is tight.

## Don'ts

- No drop shadows, no glassmorphism, no blurred backgrounds.
- No rounded corners above 4px. Stat cards and chart panels are square.
- No gradients on text. The petrol→lime gradient is for fills only.
- No purple, no pastel, no "designed by AI" colour washes.
- No emoji in copy, headings, or labels.
- Don't bold the serif. Don't italicise the sans.

## Files in this skill

- `tokens.css` — drop-in CSS custom properties + a few utility classes.
- `example.html` — a single self-contained page demonstrating masthead, stat bar, gradient legend, and footnote treatment. Open it in a browser to see the system in motion.
