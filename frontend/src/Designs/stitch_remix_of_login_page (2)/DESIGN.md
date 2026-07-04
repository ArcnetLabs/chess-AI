# Design System Specification: The Grandmaster Editorial

## 1. Overview & Creative North Star
The Creative North Star for this design system is **"The Digital Grandmaster."** 

We are moving away from the "generic dashboard" look common in chess software. Instead, we are building a high-precision, editorial-grade interface that feels like a top-tier racing HUD meets a luxury tech journal. The aesthetic is defined by **Kinetic Precision**: a feeling of immense calculation power hidden behind a calm, dark, and sophisticated glass-like veneer.

To break the "template" look, we utilize **Intentional Asymmetry**. Large-scale `display` typography should be used to anchor the eye, while secondary data points are tucked into sophisticated, nested layers. Elements should overlap slightly—a chess piece silhouette bleeding into a background container—to create a sense of depth and curated intent.

---

## 2. Colors: Tonal Depth & Luminous Accents
This system thrives on the contrast between a deep, "Void" background and hyper-luminous interactive elements.

### The Color Palette
*   **Primary:** `primary_fixed` (#84FF00) — Our "Neon Lime" signature. Use sparingly for critical actions.
*   **Success:** `secondary` (#69f6b8) — The "Electric Green" for positive engine evaluations.
*   **Surface:** `surface` (#0a0f14) — The deep "Dark Background."
*   **Error:** `error` (#ff7351) — For blunders and critical warnings.

### The "No-Line" Rule
**Explicit Instruction:** Do not use 1px solid borders to section off the UI. 
Boundaries must be defined through **Background Color Shifts**. For example, a side-panel should be `surface_container_low`, sitting against the main `surface` background. The eye should perceive the edge via the change in luminance, not a drawn line.

### Surface Hierarchy & Nesting
Treat the UI as a series of stacked, semi-transparent layers:
1.  **Level 0 (Base):** `surface` (#0a0f14) - The table.
2.  **Level 1 (Sections):** `surface_container_low` (#0e1419) - The main content zones.
3.  **Level 2 (Cards):** `surface_container` (#141a20) - Information clusters.
4.  **Level 3 (Floating):** `surface_bright` (#252d35) - Pop-ups or active elements.

### The "Glass & Gradient" Rule
Main CTAs and high-priority engine readouts should use a subtle linear gradient from `primary` (#cfffa7) to `primary_container` (#84ff00). For floating toolbars, apply a **Backdrop Blur** (minimum 12px) to the container to create a "Frosted Neon" effect, allowing the chess board's colors to bleed through beautifully.

---

## 3. Typography: Technical Authority
We pair **Space Grotesk** (Display/Headlines) with **Inter** (UI/Body) to balance high-tech personality with absolute readability.

*   **Display (Space Grotesk):** Large, bold, and slightly aggressive. Use `display-lg` for win probabilities or move numbers.
*   **Headline (Space Grotesk):** Use for section headers. Always set to "Bold" or "Semi-Bold."
*   **Body (Inter):** Clean and neutral. Used for notation logs and engine descriptions.
*   **Label (Inter):** Uppercase with increased letter-spacing (0.05em) for technical data points (e.g., "DEPTH: 24").

The contrast between the wide, geometric Space Grotesk and the tight, functional Inter creates an editorial rhythm that feels curated.

---

## 4. Elevation & Depth: Tonal Layering
We do not use drop shadows to indicate "material." We use light.

*   **The Layering Principle:** Depth is achieved by "stacking" container tiers. A `surface_container_lowest` card placed on a `surface_container_low` background creates a "sunken" effect. A `surface_bright` element on a `surface` background creates a "lifted" effect.
*   **Ambient Shadows:** If a floating element (like a context menu) requires a shadow, use a large blur (24px+) with a 4% opacity of the `primary` color. This mimics a neon glow reflecting off the dark surface.
*   **The "Ghost Border" Fallback:** If a border is required for accessibility, use `outline_variant` at 15% opacity. Never use 100% opaque borders.

---

## 5. Components: Precision Instruments

### Buttons
*   **Primary:** Solid `primary_fixed` (#84FF00) with `on_primary_fixed` (#214800) text. Sharp `sm` (0.125rem) corners for a "tech-edge" look.
*   **Secondary:** Glassmorphic. `surface_variant` at 40% opacity with a `backdrop-blur`.
*   **Interactive Glow:** On hover, primary buttons should emit a soft 8px outer glow of the same color.

### Analysis Cards
*   **Rule:** Forbid divider lines.
*   **Execution:** Separate chess moves and engine evals using `body-md` for the move and `label-md` (dimmed to `on_surface_variant`) for the timestamp. Use 16px of vertical whitespace between items.

### Chess Icons & Logo
*   **The Rook Crown:** The signature logo should be rendered in `primary_fixed`.
*   **Iconography:** Use "Stroke" style icons with a 1.5px weight. Never use filled icons unless they are in an "Active" state.

### Input Fields
*   Set background to `surface_container_highest`. 
*   No border. 
*   The cursor/caret should be the `primary` neon lime.

---

## 6. Do’s and Don'ts

### Do
*   **Do** use asymmetrical layouts (e.g., a left-aligned header with right-aligned data points that don't share a vertical axis).
*   **Do** lean into the "Neon Glow" for the active square on the chessboard.
*   **Do** use "Inter" for all data-heavy tables to ensure maximum legibility during fast-paced analysis.

### Don't
*   **Don't** use standard 1px borders to separate the chess board from the analysis panel. Use a `surface_container` background shift.
*   **Don't** use pure white (#FFFFFF). Use `on_surface` (#e7ebf3) to reduce eye strain during long study sessions.
*   **Don't** use "Full" rounded corners (pills) for everything. Use `sm` (0.125rem) or `md` (0.375rem) to maintain a sharp, high-performance "machined" feel.