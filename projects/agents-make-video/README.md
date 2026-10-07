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
| Size | 7.04 MB |
| Captions | 22 word-timed groups (`composition/captions.json`) |
| Self-review | `status: pass` — `recommended_action: present_to_user` |
| Cost | $0.00 (zero-key path; no provider APIs used) |

## Pipeline trace

Stage gates are recorded as checkpoints in this directory
(`checkpoint_<stage>.json`, each with a review checklist):

    research → proposal → script → scene_plan → assets → edit → compose

Stage gates are recorded as checkpoints in this directory
(`checkpoint_<stage>.json`, each with a review checklist):

    research -> proposal -> script -> scene_plan -> assets -> edit -> compose -> publish

The **publish** gate is `awaiting_human`: the export bundle is built and checked in, but nothing
was uploaded anywhere — publishing is the one decision the pipeline leaves to you.

## Export bundle (creator kit)

`publish/make_publish.py` prepares the SEO metadata and thumbnail, exports subtitles, then hands
the packaging to the repo's own `export_bundle` tool (`tools/publishers/export_bundle.py`):

    exports/
      metadata/   metadata.json · description.txt · chapters.txt · tags.txt
      thumbnails/ thumbnail.jpg (1280x720) · concept.json
      video/      output.mp4 · subtitles.srt

`video/output.mp4` is byte-identical to `renders/final.mp4` and is not duplicated into git —
re-run `python3 publish/make_publish.py` to lay the bundle down again.

**Title** — AI Agents Make a Video: Generation Is the Smallest Part (56 chars)
**Chapters** — 0:00 The pitch vs the reality · 0:13 Research and script · 0:28 Assets, edit and the render · 0:47 The self-review gate

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
- `artifacts/publish_log.json` — export entry (status `exported`, no upload)

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

## Self-review (the repo's own tools)

The post-render audit is not ad-hoc: it runs OpenMontage's analysis tools and stores their raw
output in `renders/self-review/tool_results.json`.

| Tool | Result |
|---|---|
| `tools/analysis/composition_validator.py` | `valid: true` — 0 errors, 1 warning (narration stem marginally longer than the video) |
| `tools/analysis/frame_sampler.py` | 8 frames at the eight scene midpoints → `renders/self-review/frames/` |
| `tools/analysis/audio_probe.py` | 62.0 s, AAC 48 kHz stereo @ 193 kbps, 7,041,739 bytes |

`composition.json` (the ffmpeg runtime's composition spec) is regenerated from `timeline.json`
on every artifacts run, so the validator always checks exactly what was rendered.

## Publish gate

`checkpoint_publish.json` records `human_approved: true` — the export bundle was reviewed and
approved by the project owner. The pipeline is complete; nothing has been uploaded anywhere.

## Revisions

- **v2 (2026-10-07)** — full-resolution QA caught four defects in v1 and all were fixed:
  the frame scheduler's fallback flashed the closing shot in the 0.30–0.45 s gaps between
  scenes (7 flashes, 2.35 s total) — scenes now hold through their gap and the cross-fade
  ends exactly at the next section start; scene 5's asset-chip labels were baked with their
  pre-animation colour (the layer-cache key omitted the state flag) and rendered invisible on
  the dark cards; scene 3's stat label could be overlapped by the caption band; and the
  progress rail showed per-scene instead of film-wide progress. Review frames are now sampled
  at scene midpoints, which is what exposed the gap flashes. 8.65 MB → 7.04 MB.
- **v1 (2026-10-07)** — first delivered render.

## Rebuild

    export PATH=/home/user/tools/bin:$PATH      # ffmpeg + ffprobe
    export PYTHONPATH=/home/user/pydeps
    python3 composition/make_video.py          # audio master → frames → encode → mux
    python3 composition/make_artifacts.py      # every artifact, stills, report, review, checkpoints
    python3 publish/make_publish.py            # publish stage: metadata, thumbnail, srt, export bundle
    python3 publish/make_publish.py --approve  # ...and close the publish gate (human approval)

`composition/renderer.py` holds the eight scene functions; `composition/timeline.json`
holds section start times and `composition/captions.json` the word-timed cues.
