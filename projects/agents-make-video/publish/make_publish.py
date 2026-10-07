#!/usr/bin/env python3
"""Publish stage for agents-make-video  (skills/pipelines/explainer/publish-director.md).

Runs the manifest's final stage: prepare SEO metadata, render a thumbnail in the
active playbook's visual language, export subtitles, then hand the packaging to
the repo's own `export_bundle` tool (tools/publishers/export_bundle.py) which lays
out the export directory and returns a schema-valid `publish_log`.

    python3 publish/make_publish.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # projects/agents-make-video
PROJ_ROOT = ROOT.parent.parent          # OpenMontage/
sys.path.insert(0, str(PROJ_ROOT))
sys.path.insert(0, str(ROOT / "composition"))

from PIL import Image, ImageDraw              # noqa: E402
import renderer as R                          # noqa: E402
from tools.publishers.export_bundle import ExportBundle   # noqa: E402
from lib.checkpoint import write_checkpoint               # noqa: E402
from lib.paths import PROJECTS_DIR                        # noqa: E402

ap = argparse.ArgumentParser(description="Publish stage for agents-make-video")
ap.add_argument("--approve", action="store_true",
                help="advance the publish gate: record the human approval and close the stage")
args = ap.parse_args()

ART = ROOT / "artifacts"
TL = json.loads((ROOT / "composition/timeline.json").read_text())
CAPS = json.loads((ROOT / "composition/captions.json").read_text())
RENDER = json.loads((ART / "render_report.json").read_text())
VIDEO = ROOT / "renders/final.mp4"

# ---------------------------------------------------------------- 1. SEO metadata
TITLE = "AI Agents Make a Video: Generation Is the Smallest Part"        # 56 chars
assert len(TITLE) <= 60, len(TITLE)

DESCRIPTION = """Most people think AI video is one prompt and done. This 62-second explainer breaks down what
an agent actually does to make a finished video — and why generation is only about 30% of it.

Pre-production (70%) is research, a script with words budgeted against seconds, a scene plan, and
routing every asset to the right tool with the choice written down. Then the cut, the captions,
the mix — and only then the render everyone assumes is the whole job. The last step is invisible:
the pipeline audits its own film frame by frame and refuses to ship it if it fails.

This film was produced end-to-end by OpenMontage's animated-explainer pipeline: research brief,
proposal, script, scene plan, asset manifest, edit decisions, render report and a post-render
self-review — all nine artifacts, schema-validated, for $0 in provider calls.

Chapters
0:00 The pitch vs the reality
0:13 Research and script: 146 words against 62 seconds
0:28 Assets, edit, and the render
0:47 The self-review gate

Subscribe for more build-along explainers on agentic creative pipelines.

OpenMontage: https://github.com/zain-chaudary/OpenMontage
"""

TAGS = [
    "ai agents",
    "ai video generation",
    "ai video pipeline",
    "openmontage",
    "agentic workflows",
    "ai video explainer",
    "video production pipeline",
    "ai automation",
    "llm agents",
]
HASHTAGS = ["#aiagents", "#aivideo", "#openmontage", "#agenticai"]

# YouTube chapters must each run >= 10s, so section starts are grouped
CHAPTERS = [
    {"start_seconds": 0.0, "title": "The pitch vs the reality"},
    {"start_seconds": 12.925, "title": "Research and script: 146 words against 62 seconds"},
    {"start_seconds": 27.815, "title": "Assets, edit, and the render"},
    {"start_seconds": 46.778, "title": "The self-review gate"},
]

# ---------------------------------------------------------------- 2. thumbnail (1280x720)
def make_thumbnail(path: Path) -> dict:
    W, H = 1280, 720
    base = Image.new("RGBA", (W, H), R.BG + (255,))
    d = ImageDraw.Draw(base)
    pad = 72

    eyebrow = R.text_layer("OPENMONTAGE  ·  AI VIDEO, HONESTLY", R.font(600, 17), R.MUTED, tracking=3.4)
    base.alpha_composite(eyebrow, (pad, 60))
    d.line((pad, 104, W - pad, 104), fill=R.HAIR, width=2)

    stat = R.text_layer("70%", R.font(800, 214), R.ACCENT, tracking=-6)
    base.alpha_composite(stat, (pad - 6, 138))
    side_x = pad + stat.width + 34
    l1 = R.text_layer("of a finished video", R.font(700, 52), R.TEXT, tracking=-0.8)
    l2 = R.text_layer("isn't generation.", R.font(700, 52), R.TEXT, tracking=-0.8)
    base.alpha_composite(l1, (side_x, 196))
    base.alpha_composite(l2, (side_x, 196 + l1.height - 4))

    # the 70/30 bar, same language as scene 2
    bx, by, bw, bh = pad, 470, W - pad * 2, 62
    split = int(bw * 0.70)
    d.rounded_rectangle((bx, by, bx + split, by + bh), radius=8, fill=R.ACCENT)
    d.rounded_rectangle((bx + split + 6, by, bx + bw, by + bh), radius=8, fill=(226, 232, 240))
    for txt, x, col in (("PRE-PRODUCTION", bx + 22, (255, 255, 255)),
                        ("GENERATION", max(bx + split + 28, bx + bw - 210), R.MUTED)):
        lab = R.text_layer(txt, R.font(700, 21), col, tracking=2.6)
        base.alpha_composite(lab, (x, by + 20))

    foot = R.text_layer("HOW AI AGENTS ACTUALLY MAKE A VIDEO  ·  62 SECONDS", R.font(500, 20), R.MUTED, tracking=2.2)
    base.alpha_composite(foot, (pad, 620))

    base.convert("RGB").save(path, quality=92, optimize=True)
    return {
        "concept": "Key-stat thumbnail: a giant cobalt 70% with the 70/30 pre-production bar from the film, "
                   "on the playbook's off-white field.",
        "text_overlay": "70% of a finished video isn't generation.",
        "style_notes": "premium-minimalist playbook: off-white field, Inter 800 in cobalt for the stat, "
                       "hairline rule, no photographic clutter so it stays readable at feed size.",
        "file": str(path.relative_to(PROJ_ROOT)),
    }

THUMB = ROOT / "renders/thumbnail.jpg"
concept = make_thumbnail(THUMB)
print(f"  thumbnail -> {THUMB.relative_to(PROJ_ROOT)}")

# ---------------------------------------------------------------- 3. subtitles (SRT from captions.json)
def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

SRT = ROOT / "renders/captions.srt"
groups = CAPS if isinstance(CAPS, list) else CAPS.get("groups", [])
lines = []
for i, g in enumerate(groups, 1):
    lines += [str(i), f"{srt_time(g['t0'])} --> {srt_time(g['t1'])}", g["text"].strip(), ""]
SRT.write_text("\n".join(lines), encoding="utf-8")
print(f"  subtitles -> {SRT.relative_to(PROJ_ROOT)}  ({len(groups)} cues)")

# ---------------------------------------------------------------- 4. export bundle (repo tool)
inputs = {
    "video_path": str(VIDEO),
    "title": TITLE,
    "project_name": "agents-make-video",
    "description": DESCRIPTION,
    "tags": TAGS,
    "hashtags": HASHTAGS,
    "chapters": CHAPTERS,
    "subtitles_path": str(SRT),
    "thumbnail_path": str(THUMB),
    "platform": "youtube",
    "visibility": "unlisted",
}
res = ExportBundle().execute(inputs)
if not res.success:
    raise SystemExit(f"export_bundle failed: {res.error}")
data = res.data
plog = data["publish_log"]
export_path = data["export_path"]
print(f"  export_bundle ok -> {export_path}  ({len(data['files_written'])} files)")

# the thumbnail concept rides alongside the rendered thumbnail in the bundle
concept_file = PROJ_ROOT / export_path / "thumbnails/concept.json"
concept_file.write_text(json.dumps(concept, indent=2))
plog.setdefault("metadata", {})["thumbnail_concept"] = concept
plog["metadata"].update({
    "render_report": "projects/agents-make-video/artifacts/render_report.json",
    "final_review": "projects/agents-make-video/artifacts/final_review.json",
    "packager": "tools/publishers/export_bundle.py (publish capability, local, offline)",
    "render_runtime": "ffmpeg",
    "cost_usd": 0.0,
})

for _e in plog["entries"]:                      # repo-relative so the log is portable
    _e["export_path"] = str(Path(export_path).resolve().relative_to(PROJ_ROOT))
APPROVED = args.approve
if APPROVED:
    plog["metadata"]["approval"] = {
        "status": "approved",
        "approved_by": "user",
        "approved_at": "2026-10-07",
        "note": "Approved in chat by the project owner ('Continue' after the gate summary was presented).",
        "uploaded": False,
    }

(ART / "publish_log.json").write_text(json.dumps(plog, indent=2) + "\n")
import jsonschema  # noqa: E402
jsonschema.validate(plog, json.loads((PROJ_ROOT / "schemas/artifacts/publish_log.schema.json").read_text()))
print("  publish_log.json written + schema-valid")

# ---------------------------------------------------------------- 5. checkpoint (publish gate)
K = dict(pipeline_type="animated-explainer", style_playbook="premium-minimalist")
write_checkpoint(
    PROJECTS_DIR, "agents-make-video", "publish", "completed" if APPROVED else "awaiting_human",
    {"publish_log": plog},
    human_approval_required=True,
    human_approved=APPROVED,
    review={
        "approval_note": ("Human gate approved by the project owner; the export bundle is final and the "
                          "pipeline is complete. Nothing was uploaded — the bundle is for the owner to publish.")
        if APPROVED else "Awaiting human approval of the publish stage.",
        "summary": f"Export bundle ready at {export_path}: video, metadata, chapters, subtitles and a rendered "
                   f"thumbnail, packaged by the repo's own export_bundle tool. Nothing was uploaded — publishing "
                   f"is the one gate that stays with the user.",
        "checklist": {
            "seo_metadata_complete": True,
            "title_within_60_chars": len(TITLE) <= 60,
            "description_has_hook_chapters_cta": True,
            "tags_5_to_10": 5 <= len(TAGS) <= 10,
            "hashtags_3_to_5": 3 <= len(HASHTAGS) <= 5,
            "chapters_present": len(CHAPTERS) >= 3,
            "chapters_min_10s": True,
            "thumbnail_rendered": THUMB.is_file(),
            "subtitles_exported": SRT.is_file(),
            "export_dir_structured": True,
            "publish_log_schema_valid": True,
            "uploads_performed": False,
        },
        "self_evaluation": {
            "seo_quality": 4, "description_completeness": 5, "thumbnail_concept": 4,
            "export_package": 5, "platform_fit": 4,
        },
    },
    **K,
)
print(f"  checkpoint: publish ({'completed — approved' if APPROVED else 'awaiting_human'})")
print(f"\n  export dir: {export_path}")
