"""Build the film: measured audio master -> frame-accurate render -> mux.

Run:  python composition/make_video.py
Outputs:
  assets/audio/master.mp3      (narration + ducked score, -16 LUFS)
  renders/final.mp4            (1920x1080 30fps H.264/AAC)
  composition/timeline.json    (measured section offsets — the edit lock)
"""
import json, re, subprocess, time
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import renderer as R
from PIL import Image

FF = "ffmpeg"
FP = "ffprobe"
TARGET = 62.0
GAPS = [0.35, 0.30, 0.30, 0.30, 0.30, 0.35, 0.45]
SECTION_TEXT = {
    1: "Type one sentence, get a finished video. That's how AI video gets sold.",
    2: "But generation is the smallest part. The teams who do this well spend most of the work before a single frame exists.",
    3: "First, research. Dozens of searches across forums, papers and news, so every number in the script traces back to a source.",
    4: "Then the script, words budgeted against seconds, and a scene plan for what you see at each moment.",
    5: "Then the assets: narration, images, music. Each job routed to the best available tool, and every choice written down.",
    6: "Then the cut, camera moves, captions, a mix. And only then the render, the part everyone assumes is the whole job.",
    7: "The last step is invisible. The agent audits its own film, frame by frame, and refuses to ship it if it fails.",
    8: "That's not generation. That's production. OpenMontage, twelve pipelines, one agent.",
}

def dur(p):
    return float(subprocess.run([FP, "-v", "error", "-show_entries", "format=duration",
                                 "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True).stdout.strip())

def build_audio():
    """Trim, tempo-match, lay out, score, duck, master."""
    TMP = HERE / "_audio"; TMP.mkdir(exist_ok=True)
    trimmed = []
    for i in range(1, 9):
        src, dst = ROOT / f"assets/audio/narration-s{i}.mp3", TMP / f"n{i}.wav"
        af = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
              "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse")
        subprocess.run([FF, "-y", "-v", "error", "-i", str(src), "-af", af,
                        "-ar", "48000", "-ac", "2", str(dst)], check=True)
        trimmed.append(dur(dst))
    raw = sum(trimmed)
    atempo = max(1.0, min(1.25, raw / (TARGET - sum(GAPS))))
    scaled = [d / atempo for d in trimmed]
    offsets, t = [], 0.0
    for i, d in enumerate(scaled):
        offsets.append(t); t += d
        if i < len(GAPS):
            t += GAPS[i]
    total = t
    print(f"  narration raw {raw:.2f}s  atempo {atempo:.5f}  timeline {total:.2f}s")

    # tempo each segment onto the timeline
    for i in range(1, 9):
        subprocess.run([FF, "-y", "-v", "error", "-i", str(TMP / f"n{i}.wav"), "-af", f"atempo={atempo:.6f}",
                        "-ar", "48000", "-ac", "2", str(TMP / f"n{i}t.wav")], check=True)
    ins, filt = [], []
    for i, o in enumerate(offsets, 1):
        ins += ["-i", str(TMP / f"n{i}t.wav")]
        ms = int(round(o * 1000))
        filt.append(f"[{i-1}:a]adelay={ms}|{ms}[a{i}]")
    fc = ";".join(filt) + ";" + "".join(f"[a{i}]" for i in range(1, 9)) + "amix=inputs=8:normalize=0:dropout_transition=0[n]"
    subprocess.run([FF, "-y", "-v", "error", *ins, "-filter_complex", fc, "-map", "[n]",
                    "-ar", "48000", "-ac", "2", str(TMP / "narration.wav")], check=True)

    # score: soft A-minor pad, slow movement, low-pass
    L = total + 1.5
    chords = [110.0, 164.81, 220.0, 261.63, 329.63]
    ins = []
    for f in chords:
        ins += ["-f", "lavfi", "-t", str(L), "-i", f"sine=frequency={f}:sample_rate=48000"]
    parts = [f"[{i}:a]volume=0.16,tremolo=f=0.11:d=0.25,lowpass=f=1500[p{i}]" for i in range(len(chords))]
    fc = (";".join(parts) + ";" + "".join(f"[p{i}]" for i in range(len(chords)))
          + f"amix=inputs={len(chords)}:normalize=0[pad];[pad]aecho=0.8:0.85:700|1300:0.32|0.22,volume=0.30[m]")
    subprocess.run([FF, "-y", "-v", "error", *ins, "-filter_complex", fc, "-map", "[m]",
                    "-t", str(total), "-ar", "48000", "-ac", "2", str(TMP / "music.wav")], check=True)

    # duck music under narration, then master
    fc = ("[0:a]volume=1.0,asplit=2[n1][n2];[1:a]volume=1.0[m];"
          "[m][n1]sidechaincompress=threshold=0.05:ratio=7:attack=15:release=380:makeup=1[duck];"
          f"[n2][duck]amix=inputs=2:normalize=0:dropout_transition=0,"
          f"afade=t=in:st=0:d=1.0,afade=t=out:st={total-1.6:.3f}:d=1.6,alimiter=limit=0.95[mix]")
    subprocess.run([FF, "-y", "-v", "error", "-i", str(TMP / "narration.wav"), "-i", str(TMP / "music.wav"),
                    "-filter_complex", fc, "-map", "[mix]", "-ar", "48000", "-ac", "2", str(TMP / "mix.wav")], check=True)
    subprocess.run([FF, "-y", "-v", "error", "-i", str(TMP / "mix.wav"), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-c:a", "libmp3lame", "-b:a", "320k", str(ROOT / "assets/audio/master.mp3")], check=True)
    # keep the stems the composition references (documentation + validation)
    subprocess.run([FF, "-y", "-v", "error", "-i", str(TMP / "narration.wav"), "-c:a", "libmp3lame", "-b:a", "192k",
                    str(ROOT / "assets/audio/narration.mp3")], check=True)
    (ROOT / "assets/music").mkdir(exist_ok=True)
    subprocess.run([FF, "-y", "-v", "error", "-i", str(TMP / "music.wav"), "-c:a", "libmp3lame", "-b:a", "192k",
                    str(ROOT / "assets/music/music-bed.mp3")], check=True)

    tl = {"atempo": round(atempo, 6), "section_durations": [round(d, 4) for d in scaled],
          "section_start_times": [round(o, 4) for o in offsets], "gaps": GAPS,
          "total_seconds": round(total, 3), "master_seconds": round(dur(ROOT / "assets/audio/master.mp3"), 3)}
    (HERE / "timeline.json").write_text(json.dumps(tl, indent=2))
    print(f"  master {tl['master_seconds']}s  ->  assets/audio/master.mp3")
    return tl

def captions(tl):
    """Word-level captions, character-weighted across each section's measured duration."""
    groups = []
    for i in range(8):
        text, d = SECTION_TEXT[i + 1], tl["section_durations"][i]
        base = tl["section_start_times"][i]
        toks = [w for w in re.split(r"(\s+)", text) if w.strip()]
        weights = [len(w) + 1 for w in toks]; sw = sum(weights); t = 0.0; wt = []
        for w_, wgt in zip(toks, weights):
            dd = wgt / sw * d; wt.append((w_, t, t + dd)); t += dd
        n = 2 if len(wt) <= 16 else 3 if len(wt) <= 26 else 4
        per = (len(wt) + n - 1) // n
        if len(wt) <= 7:
            chunks = [wt]
        else:
            chunks = [wt[k:k + per] for k in range(0, len(wt), per)]
        for g in chunks:
            if not g:
                continue
            t0 = base + g[0][1] - 0.06
            t1 = max(base + g[-1][2], t0 + 0.6)
            groups.append({"text": " ".join(w for w, _, _ in g), "t0": max(0.0, t0),
                           "t1": min(tl["total_seconds"], t1)})
    return groups

def render(tl):
    offs, durs, total = tl["section_start_times"], tl["section_durations"], tl["total_seconds"]
    nframes = int(round(total * R.FPS))
    XF = 0.5
    caps = captions(tl)
    print(f"  captions: {len(caps)} groups   frames: {nframes}")
    sched = []
    for i in range(len(R.SCENES)):
        start = offs[i]
        end = offs[i] + durs[i] if i < len(R.SCENES) - 1 else total
        sched.append((start, end))
    ctx = R.Ctx()
    out = ROOT / "renders"; out.mkdir(exist_ok=True)

    def frame(t):
        idx = next((i for i, (a, b) in enumerate(sched) if a <= t < b), len(sched) - 1)
        a, b = sched[idx]
        base = R.SCENES[idx](ctx, max(0.0, t - a))
        if idx + 1 < len(R.SCENES) and (b - t) < XF:
            p = 1.0 - ((b - t) / XF)
            nxt = R.SCENES[idx + 1](ctx, max(0.0, t - sched[idx + 1][0]))
            base = Image.blend(base.convert("RGB"), nxt.convert("RGB"), R.ease_io(p)).convert("RGBA")
        dark = idx in (0, 7)
        for cp in caps:
            if cp["t0"] - 0.2 <= t <= cp["t1"] + 0.2:
                R.caption(base, ctx, cp["text"], t, cp["t0"], cp["t1"], dark=dark)
        return base.convert("RGB")

    tmp_v = HERE / "_video-only.mp4"
    proc = subprocess.Popen([FF, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{R.W}x{R.H}", "-r", str(R.FPS), "-i", "-", "-an",
                             "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                             "-profile:v", "high", "-level", "4.1", "-movflags", "+faststart",
                             "-r", str(R.FPS), str(tmp_v)], stdin=subprocess.PIPE)
    t0 = time.time()
    for n in range(nframes):
        proc.stdin.write(frame(n / R.FPS).tobytes())
        if n % 300 == 0:
            el = time.time() - t0
            print(f"    frame {n}/{nframes}  {el:.0f}s  eta {(el/max(n,1)*(nframes-n)):.0f}s", flush=True)
    proc.stdin.close(); rc = proc.wait()
    print(f"  encode rc={rc} in {time.time()-t0:.0f}s")

    subprocess.run([FF, "-y", "-v", "error", "-i", str(tmp_v), "-i", str(ROOT / "assets/audio/master.mp3"),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    "-movflags", "+faststart", "-shortest", str(out / "final.mp4")], check=True)
    print(f"  renders/final.mp4  {dur(out/'final.mp4'):.3f}s  {(out/'final.mp4').stat().st_size/1e6:.2f} MB")
    return caps

if __name__ == "__main__":
    print("[1/3] audio master")
    tl = build_audio()
    print("[2/3] render")
    caps = render(tl)
    print("[3/3] done")
    (HERE / "captions.json").write_text(json.dumps(caps, indent=2))
