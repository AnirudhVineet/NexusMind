# Meme Templates

Place meme template PNG images in this directory. The content engine will look
for templates by name when rendering memes with Pillow.

## Expected filenames

Each filename is derived from the template name by lowercasing and replacing
spaces with underscores, then appending `.png`.

| Template name         | Expected filename                  |
|-----------------------|------------------------------------|
| Drake                 | `drake.png`                        |
| Two Buttons           | `two_buttons.png`                  |
| Expanding Brain       | `expanding_brain.png`              |
| Distracted Boyfriend  | `distracted_boyfriend.png`         |
| Change My Mind        | `change_my_mind.png`               |

## Image requirements

- Format: PNG (RGBA or RGB)
- Recommended resolution: 800x800 or wider for readability
- Leave blank areas at the top and/or bottom where text will be overlaid

## Fallback behaviour

If a template PNG is not found, the engine skips image rendering and sets
`file_path = null` on the generated content row. The meme JSON
(`content_json`) is still saved and can be rendered client-side.
