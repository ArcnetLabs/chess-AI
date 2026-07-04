---
name: Obsidian Emerald
colors:
  surface: '#131313'
  surface-dim: '#131313'
  surface-bright: '#3a3939'
  surface-container-lowest: '#0e0e0e'
  surface-container-low: '#1c1b1b'
  surface-container: '#201f1f'
  surface-container-high: '#2a2a2a'
  surface-container-highest: '#353534'
  on-surface: '#e5e2e1'
  on-surface-variant: '#bbcabf'
  inverse-surface: '#e5e2e1'
  inverse-on-surface: '#313030'
  outline: '#86948a'
  outline-variant: '#3c4a42'
  surface-tint: '#4edea3'
  primary: '#4edea3'
  on-primary: '#003824'
  primary-container: '#10b981'
  on-primary-container: '#00422b'
  inverse-primary: '#006c49'
  secondary: '#b9c7e0'
  on-secondary: '#233144'
  secondary-container: '#3c4a5e'
  on-secondary-container: '#abb9d2'
  tertiary: '#ffb3af'
  on-tertiary: '#650911'
  tertiary-container: '#fc7c78'
  on-tertiary-container: '#711419'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#6ffbbe'
  primary-fixed-dim: '#4edea3'
  on-primary-fixed: '#002113'
  on-primary-fixed-variant: '#005236'
  secondary-fixed: '#d5e3fd'
  secondary-fixed-dim: '#b9c7e0'
  on-secondary-fixed: '#0d1c2f'
  on-secondary-fixed-variant: '#3a485c'
  tertiary-fixed: '#ffdad7'
  tertiary-fixed-dim: '#ffb3af'
  on-tertiary-fixed: '#410005'
  on-tertiary-fixed-variant: '#842225'
  background: '#131313'
  on-background: '#e5e2e1'
  surface-variant: '#353534'
typography:
  display:
    fontFamily: Geist
    fontSize: 48px
    fontWeight: '600'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.2'
  headline-md:
    fontFamily: Geist
    fontSize: 20px
    fontWeight: '500'
    lineHeight: '1.4'
  body-lg:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: '1.4'
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Geist
    fontSize: 11px
    fontWeight: '500'
    lineHeight: '1.2'
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 40px
  container-max: 1200px
  gutter: 24px
---

## Brand & Style

The design system is engineered for a high-performance SaaS environment that prioritizes analytical clarity and professional trust. It targets power users who value efficiency, precision, and a calm working atmosphere.

The aesthetic follows a **Modern Minimalist** philosophy with a focus on functional utility. It draws inspiration from "Utility-First" interfaces like Raycast and Linear, utilizing a restrained dark theme to reduce eye strain during deep work. The emotional response should be one of "quiet intelligence"—the UI disappears to let the content and data take center stage, using subtle micro-interactions rather than flashy animations to guide the user.

## Colors

The palette is built on a "Deep Obsidian" foundation. Unlike standard grays, the neutrals are slightly desaturated to ensure the Emerald accent feels organic and sophisticated rather than neon.

- **Primary Emerald (#10b981):** Used sparingly for primary actions, success states, and active indicators. It represents growth and analytical "correctness."
- **Surface Strategy:** The system uses a tiered dark mode. The canvas is the darkest layer (`#0a0a0a`), while cards and navigation elements sit on a slightly lighter surface (`#171717`). 
- **Borders:** High-contrast lines are avoided. Instead, use subtle dividers (`#262626`) to create structure without visual noise.

## Typography

This design system utilizes **Geist** for its clean, geometric neo-grotesque qualities and excellent legibility in dark environments. For technical data and metadata, **JetBrains Mono** is introduced to provide an analytical, precise feel without appearing "hacky."

- **Hierarchy:** Large displays use tight letter spacing and semi-bold weights to appear authoritative.
- **Body Text:** Use `body-md` (14px) as the standard for chat messages and documentation to maximize information density while maintaining readability through generous 1.5 line heights.
- **Labels:** Use the monospaced font for timestamps, version numbers, or status indicators to reinforce the "pro" nature of the tool.

## Layout & Spacing

The layout follows a strict **4px baseline grid** to ensure mathematical consistency. 

- **Grid System:** Use a 12-column fluid grid for main dashboard views. For conversational interfaces, use a centered, max-width container (800px) to maintain focus and prevent long line lengths.
- **Rhythm:** Use `lg` (24px) for padding within cards and main sections. Use `md` (16px) for internal component spacing (e.g., between an icon and text).
- **Responsive:** On mobile, reduce horizontal margins to `md` (16px) and stack sidebars into a bottom sheet or full-screen drawer.

## Elevation & Depth

This design system avoids traditional heavy shadows in favor of **Tonal Layers** and **Low-Contrast Outlines**.

- **Level 0 (Canvas):** Background layer, `#0a0a0a`.
- **Level 1 (Card/Surface):** `#171717` with a 1px solid border of `#262626`. No shadow.
- **Level 2 (Popovers/Modals):** `#222222` with a 1px solid border of `#3f3f46` and a very soft, large-radius shadow (0px 12px 24px rgba(0,0,0,0.5)) to create a "lifted" effect.
- **Backdrop:** Use a 4px blur with a 40% black overlay for modals to maintain context without visual clutter.

## Shapes

The design system uses a "Soft" corner radius (4px to 8px) to feel modern and approachable without the playfulness of a fully rounded system.

- **Small Components:** Checkboxes and small tags use `rounded-sm` (4px).
- **Standard Components:** Buttons, inputs, and cards use `rounded-lg` (8px).
- **Specialty Components:** Search bars (like Raycast style) may use `rounded-xl` (12px) to differentiate global actions from local ones.

## Components

### Conversational Interface
- **Chat Bubbles:** AI responses are borderless on the primary surface. User messages are contained within a subtle `#171717` box with a `#262626` border. Avoid high-contrast bubbles.
- **Message Input:** A fixed-width container at the bottom. Use a 1px border and a subtle inner glow on focus using the Emerald accent.
- **Intelligence Cards:** Used for AI-generated data. These should have a subtle top-border (2px) in Emerald to signify "system-generated" content.

### Action Elements
- **Buttons:**
    - *Primary:* Emerald background, black text for high legibility.
    - *Secondary:* Transparent background, `#262626` border, white text.
- **Chips:** Small, mono-spaced text labels with a subtle background color for categorization.

### Inputs & Controls
- **Fields:** Minimalist styling. No background fill—only a bottom border or a light 4-sided border that shifts from gray to Emerald on active state.
- **Modals:** Centered, floating cards with sharp typography and clear "Esc" or "Close" affordances. Focus on the "Command Palette" style for rapid navigation.