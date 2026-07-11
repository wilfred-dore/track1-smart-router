#!/usr/bin/env python3
"""Build the submission demo video: Beamer slide stills + Manim animated scenes,
narrated with Gradium TTS (edge-tts fallback), assembled with ffmpeg.

Prereq: manim scenes rendered to docs/video/media/videos/scenes/1080p30/
  .venv/bin/manim render -qh --fps 30 --media_dir docs/video/media docs/video/scenes.py CascadeScene DescentScene
Usage: [GRADIUM_API_KEY=...] .venv/bin/python docs/video/build_video.py
"""
import asyncio
import json
import os
import subprocess

import fitz  # PyMuPDF

HERE = os.path.dirname(os.path.abspath(__file__))
PDF = os.path.join(HERE, "..", "slides", "smart-router-slides.pdf")
CLIPS = os.path.join(HERE, "media", "videos", "scenes", "1080p30")
OUT = os.path.join(HERE, "out")
EDGE_VOICE = "en-US-AndrewNeural"
GRADIUM_VOICE_ID = os.environ.get("GRADIUM_VOICE_ID", "POBHtemksfWQbng0")  # Garrett
TAIL_SILENCE = 0.9

# The narration avoids first-person identity claims: a synthetic voice must not
# present itself as a real person. Attribution lives in slides, README, repo.
SEGMENTS = [
    ("slide", 0,
     "This is Smart Router, team Robot ROCm's entry for Track 1 of the AMD "
     "Developer Hackathon: a general-purpose AI agent that answers natural "
     "language tasks while spending as few Fireworks tokens as possible."),
    ("slide", 1,
     "The scoring mirrors an enterprise reality: pass an eighty percent accuracy "
     "gate, then rank by the fewest paid tokens. Local inference costs zero, so "
     "the winning principle is simple: answer for free whatever can be verified "
     "for free, and escalate the rest deliberately."),
    ("clip", os.path.join(CLIPS, "CascadeScene.mp4"),
     "Every task makes a single pass. Deterministic solvers handle exact "
     "arithmetic, sentiment, and named entities at zero cost. A bundled "
     "three-billion-parameter model answers summaries and code, checked by free "
     "verifiers. Whatever cannot be verified for free - math, logic, factual "
     "claims, code fixes - escalates to Fireworks: logic runs solo for "
     "determinism, everything else goes in two tiny batched calls with billed "
     "reasoning switched off."),
    ("clip", os.path.join(CLIPS, "DescentScene.mp4"),
     "Nothing here is assumed. Measured on the real Fireworks API, the bill went "
     "from six and a half thousand tokens fully escalated down to under seven "
     "hundred: batching collapsed the reasoning overhead, local answering removed "
     "the long prompts, and switching reasoning effort to none cut the hidden "
     "thinking - at nineteen out of nineteen accuracy, four runs in a row."),
    ("slide", 4,
     "Before any resubmission, three independent validations: real A P I "
     "evaluations, an adversarial generalization gauntlet of unseen tasks, and a "
     "simulated judge from a different model family. Continuous integration "
     "replays the exact grading environment: four gigabytes of RAM, two virtual "
     "CPUs, nineteen tasks in ninety seconds."),
    ("slide", 5,
     "Answer at zero cost first. Route by verifiability, not difficulty. Measure "
     "everything. And remember: plumbing wins hackathons. Techniques adapted from "
     "publicly shared competitor write-ups are credited in the repository. "
     "Thanks for watching."),
]


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def duration_of(path):
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
        check=True, capture_output=True, text=True)
    return float(json.loads(out.stdout)["format"]["duration"])


async def synthesize(text, path):
    api_key = os.environ.get("GRADIUM_API_KEY")
    if api_key:
        import gradium
        client = gradium.GradiumClient(api_key=api_key)
        result = await gradium.speech.tts(
            client, {"voice_id": GRADIUM_VOICE_ID, "output_format": "wav"}, text)
        with open(path, "wb") as f:
            f.write(result.raw_data)
    else:
        import edge_tts
        await edge_tts.Communicate(text, EDGE_VOICE).save(path)


VF = ("scale=1920:1080:force_original_aspect_ratio=decrease,"
      "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,"
      "tpad=stop_mode=clone:stop_duration=120")


def main():
    os.makedirs(OUT, exist_ok=True)
    doc = fitz.open(PDF)
    pages = {}
    for kind, src, _ in SEGMENTS:
        if kind == "slide" and src not in pages:
            png = os.path.join(OUT, f"slide{src}.png")
            page = doc[src]
            page.get_pixmap(matrix=fitz.Matrix(1920 / page.rect.width,
                                               1920 / page.rect.width)).save(png)
            pages[src] = png

    parts = []
    for i, (kind, src, narration) in enumerate(SEGMENTS):
        ext = "wav" if os.environ.get("GRADIUM_API_KEY") else "mp3"
        voice = os.path.join(OUT, f"voice{i}.{ext}")
        asyncio.run(synthesize(narration, voice))
        seg_duration = duration_of(voice) + TAIL_SILENCE
        seg = os.path.join(OUT, f"seg{i}.mp4")
        if kind == "slide":
            visual = ["-loop", "1", "-framerate", "30", "-i", pages[src]]
        else:
            visual = ["-i", src]
        run(["ffmpeg", "-y", *visual, "-i", voice, "-t", f"{seg_duration:.2f}",
             "-vf", VF, "-r", "30",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium",
             "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-af", "apad",
             "-map", "0:v:0", "-map", "1:a:0", seg])
        parts.append(seg)
        print(f"segment {i} ({kind}): {seg_duration:.1f}s")

    concat_list = os.path.join(OUT, "list.txt")
    with open(concat_list, "w") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    final = os.path.join(HERE, "smart-router-demo.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
         "-c", "copy", final])

    run(["cp", pages[0], os.path.join(HERE, "cover.png")])
    print(f"\nvideo: {final} ({duration_of(final):.0f}s)")
    print(f"cover: {os.path.join(HERE, 'cover.png')}")


if __name__ == "__main__":
    main()
