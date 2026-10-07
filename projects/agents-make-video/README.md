# How AI Agents Actually Make a Video

A 62-second animated explainer produced end-to-end by this repository's own
`animated-explainer` pipeline — researched, proposed, scripted, storyboarded,
sourced, cut, rendered and self-reviewed by the agent, not hand-written FFmpeg.

**Watch it:** `python3 preview/serve.py` → open <http://localhost:8080/>
(direct player page, Range-capable so seeking works), or open
`renders/final.mp4` directly.

## Deliverable

| | |
|---|---|
| File | `renders/final.mp4` |
| Runtime | 62.000 s · 1860 frames @ 30 fps |
| Picture | 1920×1080, H.264 high, yuv420p, `+faststart` |
| Sound | AAC 192 kbps, 48 kHz stereo |
| Size | 8.65 MB |
| Captions | 22 word-timed groups (`composition/captions.json`) |
| Self-review | `status: pass` — `recommended_action: present_to_user` |
| Cost | $0.00 (zero-key path; no provider APIs used) |

## Pipeline trace

Stage gates are recorded as checkpoints in this directory
(`checkpoint_<stage>.json`, each with a review checklist):

    research → proposal → script → scene_plan → assets → edit → compose

Artifacts (all validated against `schemas/artifacts/*.json`):

- `artifacts/research_brief.json` — 8 sources, 7 sourced data points, 3 angles
- `artifacts/proposal_packet.json` — 3 concepts, itemized cost, runtime locked
- `artifacts/script.json` — 146 words, 8 sections, delivery cues
- `artifacts/scene_plan.json` — 8 scenes, 3 scene types, no 3-in-a-row repeats
- `artifacts/asset_manifest.json` — 28 assets, every file present
- `artifacts/edit_decisions.json` — 8 cuts, captions, music ducking
- `artifacts/decision_log.json` — d-001…d-007, append-only
- `artifacts/render_report.json` — outputs, verification notes
- `artifacts/final_review.json` — 5/5 check groups, PASS

## How it was made (the honest version)

Topology: still plates + typographic animation, composited frame by frame with
Pillow (`composition/renderer.py`), encoded and muxed with FFmpeg
(`composition/make_video.py`).

Two decisions are explicitly disclosed in the decision log rather than hidden:

- **d-004 — render runtime = ffmpeg.** The manifest's preferred runtimes
  (Remotion, HyperFrames) need a Chrome/Chromium binary whose shared libraries
  are not installable in this environment. The substitution is declared, and
  the delivery promise (animated explainer, not a slideshow) is verified after
  render: 8/8 scenes show measurable motion.
- **d-006 — music synthesised** from a chord progression with FFmpeg
  (`sine` + `tremolo` + `lowpass` + `aecho`) instead of a provider music bed.

## Rebuild

    export PATH=/home/user/tools/bin:$PATH      # ffmpeg + ffprobe
    export PYTHONPATH=/home/user/pydeps
    python3 composition/make_video.py          # audio master → frames → encode → mux
    python3 composition/make_artifacts.py      # every artifact, stills, report, review, checkpoints

`composition/renderer.py` holds the eight scene functions; `composition/timeline.json`
holds section start times and `composition/captions.json` the word-timed cues.
