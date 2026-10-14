# Männermasche — design direction

## Product

A German-language men's underwear and swimwear store for Germany. Main brands: MANSTORE, Olaf Benz and CALIDA. Männermasche is a working name. Create a consistent design system and responsive storefront based on the supplied homepage reference.

## Visual direction

Calm, confident, contemporary. Warm off-white background, near-black text and deep forest-green accents. Product photography carries the visual identity; avoid heavy shadows, excessive decoration and oversized rounded controls.

Suggested starting palette, to refine against the reference:

- Page: #F8F8F3
- Secondary surface: #EEEEE7
- Primary text: #171E19
- Secondary text: #626960
- Accent: #183F30
- Border: #DCDED5

## Typography

Modern sans-serif with clear German characters. The exact reference font is unknown. Inter is a candidate, not a fixed requirement. Headings use medium weight, comfortable line height and restrained letter spacing. Body text and small labels must remain readable on mobile. Define font families, weight, size scale and line-height tokens. Final site fonts will be hosted locally.

## Homepage

- Compact header: logo and subtitle on the left, navigation in the centre, appropriate outline controls when implemented.
- Navigation: Neuheiten, Unterwäsche, Bademode, Marken, Sale.
- Wide hero: supplied photograph, model on the right; readable text on the left with a soft light gradient.
- Heading: “Dein Stil. Deine Underwear.”
- Description: “Entdecke besondere Styles von MANSTORE, Olaf Benz und CALIDA.”
- One primary action leading to the collection.
- Four categories: Boxershorts, Slips & Pants, Strings, Bodies.
- Product cards: photo, brand, model, price, small colour swatches. Quiet borders, consistent spacing.
- Brand section and compact footer.

Use the original homepage mockup as the visual reference. SVG garments in the current implementation are temporary illustrations, not the desired final product photography. Do not copy invented delivery promises, certifications or product claims from illustrative mockups.

## Product interaction

One product page combines colour/size variants. Selecting a colour switches to its real photo gallery where available. Selecting a size updates the chosen SKU, price and availability. Different sizes share their colour gallery. Define selected, unavailable, hover, focus, loading and error states.

## Responsive and accessibility

Desktop: broad hero and four-column category/product layout. Mobile: compact accessible menu, readable hero composition and two-column cards when space permits. Define spacing, container widths, breakpoints and control sizes. Ensure keyboard focus and readable contrast. Colour alone must not communicate availability or selection.

## Requested deliverables

Semantic CSS tokens for colour, typography, spacing, radii and layout; reusable component styles; desktop/mobile HTML previews. Keep tokens, foundations, components and page styles separate. Target Django Templates with HTMX/Alpine; do not introduce React or another application framework.

This document specifies desired design. It is not a claim that checkout, real stock, payments or legal pages are implemented.
