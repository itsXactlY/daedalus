# Artistic Style Variants for Mazemaker Comics

## 23 Distinct Styles (Tested with Riverflow)

These styles were validated generating 341/345 images successfully:

| ID | Directory | Style Description |
|----|-----------|-------------------|
| style_01 | style_01 | cyberpunk neon: electric glowing lines, rain-soaked streets, neon kanji, teal/magenta highlights |
| style_02 | style_02 | steampunk brass: Victorian machinery, gears, copper pipes, leather, sepia gaslight |
| style_03 | style_03 | Art Deco luxury: geometric patterns, gold/black, 1920s skyscrapers, chrome |
| style_04 | style_04 | biopunk organic: living circuitry, bio-mechanical, bioluminescence, green glow |
| style_05 | style_05 | solarpunk futurism: solar panels, green tech, sunlight through leaves |
| style_06 | style_06 | dark academia: libraries, candlelight, leather books, parchment |
| style_07 | style_07 | terminal green: CRT phosphor, scanlines, 80s computer matrix rain |
| style_08 | style_08 | paper cutout flat: minimalist shapes, no gradients, kirigami aesthetic |
| style_09 | style_09 | isometric low-poly: 3D geometric, faceted surfaces, technical precision |
| style_10 | style_10 | Ukiyo-e woodblock: Japanese print, flowing lines, indigo/rust palette |
| style_11 | style_11 | Pop Art comic: halftone dots, Ben-Day dots, saturated colors |
| style_12 | style_12 | noir chiaroscuro: high-contrast black/white, dramatic shadows, film noir |
| style_13 | style_13 | glitch digital: data corruption, RGB separation, static interference |
| style_14 | style_14 | pixel art retro: 16-bit gaming, chunky pixels, SNES aesthetic |
| style_15 | style_15 | wireframe tech: transparent 3D, thin lines, CAD drawing |
| style_16 | style_16 | crystalline geometric: sharp crystals, refractive light, prismatic |
| style_17 | style_17 | neural network glow: synaptic connections, fiber optic trails |
| style_18 | style_18 | architectural blueprint: technical drawing, measurement marks, cyan |
| style_19 | style_19 | watercolor wash: flowing pigments, paper texture, soft edges |
| style_20 | style_20 | ink brush: sumi-e strokes, black ink, rice paper, zen aesthetic |
| style_21 | style_21 | diesel punk heavy: massive engines, riveted steel, industrial grime |
| style_22 | style_22 | quantum superposition: probability clouds, wave duality, overlapping realities |
| style_23 | style_23 | analog cybernetics: oscilloscopes, tape reels, orange CRTs |

## Prompt Construction Pattern

```
{CHARACTERS} Style: {style_desc}. {page_text}. Ultrawide 21:9. ALL text rendered.
```

Where CHARACTERS contains consistent character definitions across all pages.