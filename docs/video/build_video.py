#!/usr/bin/env python3
"""Build the submission demo video from the Beamer slides.

Pipeline: render each PDF page to a 1080p PNG (PyMuPDF), synthesize the
narration per slide (edge-tts neural voice), assemble slide+voice segments
with ffmpeg, then concatenate. Also exports slide 1 as the cover image.

Usage: .venv/bin/python docs/video/build_video.py
"""
import asyncio
import json
import os
import subprocess
import sys

import fitz  # PyMuPDF

HERE = os.path.dirname(os.path.abspath(__file__))
PDF = os.path.join(HERE, "..", "slides", "smart-router-slides.pdf")
OUT = os.path.join(HERE, "out")
VOICE = "en-US-AndrewNeural"
TAIL_SILENCE = 1.0  # seconds of slide hold after the narration ends

NARRATION = [
    # Slide 1 — title
    "Hi, I'm Wilfred Doré, and this is Smart Router, my entry for Track 1 of the "
    "AMD Developer Hackathon: a general-purpose AI agent that handles natural "
    "language tasks while spending as few Fireworks tokens as possible.",
    # Slide 2 — problem
    "Track 1 mirrors a real enterprise problem: not every task deserves a premium "
    "model. The scoring makes this explicit. You must pass an eighty percent "
    "accuracy gate, and once you pass, ranking is purely about how few Fireworks "
    "tokens you spend. Local inference costs zero, so the winning strategy is to "
    "answer locally whenever it is safe, and to escalate only when it matters.",
    # Slide 3 — architecture
    "Every task flows through a single-pass cascade, never a loop. First, "
    "deterministic solvers: an arithmetic parser, a sentiment lexicon, and "
    "gazetteers for named entities. When they fire, the answer costs zero tokens. "
    "Next, a three billion parameter Qwen model, quantized to four bits, running "
    "on CPU inside the container. A zero-cost confidence gate then scores every "
    "local answer. Only the hard residue, and the categories where a small model "
    "fails silently, like math and logic, escalate to Fireworks, with the model "
    "resolved from the allowed list at runtime and a tight output contract.",
    # Slide 4 — engineering
    "Everything is driven by a single config file: gate thresholds, model mapping, "
    "token budgets, escalation policy. Nothing is hardcoded, and no answers are "
    "cached. The pipeline survives failure: if the local runtime breaks, it "
    "degrades to full escalation instead of crashing. And a mock mode runs the "
    "whole system end to end without any API key, which is how it was built "
    "before credits even arrived.",
    # Slide 5 — results
    "Everything here is measured in continuous integration, under the exact "
    "grading limits: four gigabytes of RAM and two virtual CPUs. Nineteen tasks "
    "complete in ninety seconds against a ten minute budget. The image compresses "
    "to under two gigabytes. And a full run spends roughly nine hundred tokens, "
    "while the current leader spends over four thousand.",
    # Slide 6 — takeaways
    "Three takeaways. Answer at zero cost first. Route by reliability, not by "
    "difficulty. And plumbing wins hackathons: most failed submissions break on "
    "infrastructure, so the CI reproduces the grading environment exactly. The "
    "image is public, linux amd64, weights bundled. Thanks for watching.",
]


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def duration_of(path):
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
        check=True, capture_output=True, text=True)
    return float(json.loads(out.stdout)["format"]["duration"])


async def synthesize(text, path):
    import edge_tts
    await edge_tts.Communicate(text, VOICE).save(path)


def main():
    os.makedirs(OUT, exist_ok=True)
    doc = fitz.open(PDF)
    assert len(doc) == len(NARRATION), f"{len(doc)} pages vs {len(NARRATION)} scripts"

    segments = []
    for i, page in enumerate(doc):
        png = os.path.join(OUT, f"slide{i + 1}.png")
        zoom = 1920 / page.rect.width
        page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)).save(png)

        mp3 = os.path.join(OUT, f"voice{i + 1}.mp3")
        asyncio.run(synthesize(NARRATION[i], mp3))
        seg_duration = duration_of(mp3) + TAIL_SILENCE

        seg = os.path.join(OUT, f"seg{i + 1}.mp4")
        run(["ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-i", png,
             "-i", mp3, "-t", f"{seg_duration:.2f}",
             "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
                    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:white",
             "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-af", "apad",
             seg])
        segments.append(seg)
        print(f"slide {i + 1}: {seg_duration:.1f}s")

    concat_list = os.path.join(OUT, "list.txt")
    with open(concat_list, "w") as f:
        f.writelines(f"file '{s}'\n" for s in segments)
    final = os.path.join(HERE, "smart-router-demo.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
         "-c", "copy", final])

    cover = os.path.join(HERE, "cover.png")
    run(["cp", os.path.join(OUT, "slide1.png"), cover])
    print(f"\nvideo: {final} ({duration_of(final):.0f}s)")
    print(f"cover: {cover}")


if __name__ == "__main__":
    main()
