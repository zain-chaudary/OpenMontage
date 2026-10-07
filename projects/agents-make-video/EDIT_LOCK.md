# Edit lock

Locked at render time; changing any of these invalidates the delivered render
and requires a re-render plus a re-logged decision.

| Item | Locked value |
|---|---|
| Pipeline | `animated-explainer` |
| Style playbook | premium-minimalist |
| render_runtime | **ffmpeg** (d-004) |
| Composition engine | bespoke atelier compositor (`composition/renderer.py`) |
| Runtime | 62.000 s, 1920×1080, 30 fps |
| Voice | espeak-ng en-GB, pitch 38, speed 156 |
| Music | FFmpeg-synthesised score (d-006) |
| Captions | frame-drawn, character-weighted (d-007) |
| Total spend | $0.00 |

Allowed without unlock: typo fixes in artifacts, README wording, preview page.
Not allowed: changing scripts/timeline/captions/scene order.
