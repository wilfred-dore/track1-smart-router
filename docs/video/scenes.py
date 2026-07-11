"""Manim scenes for the demo video: the routing cascade and the token descent.

Render:  manim -qh --fps 30 docs/video/scenes.py CascadeScene DescentScene
"""
from manim import (Scene, VGroup, Rectangle, Text, Dot, Arrow, Create, Write as MWrite,
                   FadeIn, FadeOut, LaggedStart, MoveToTarget, config,
                   UP, DOWN, LEFT, RIGHT, ORIGIN, GREEN_D, RED_D, GREY_B, WHITE, YELLOW_D)

config.background_color = "#111111"

AMD_RED = "#ED1C24"
OK_GREEN = "#2EA043"


def stage_box(label, sub, color=GREY_B, width=9.4):
    box = Rectangle(width=width, height=1.0, stroke_color=color, stroke_width=2,
                    fill_color="#1c1c1c", fill_opacity=1.0)
    title = Text(label, font_size=26, color=WHITE).move_to(box.get_center() + UP * 0.18)
    subtitle = Text(sub, font_size=17, color=GREY_B).move_to(box.get_center() + DOWN * 0.25)
    return VGroup(box, title, subtitle)


class CascadeScene(Scene):
    def construct(self):
        title = Text("One pass. Free first. Pay last.", font_size=34, color=WHITE).to_edge(UP, buff=0.4)
        self.play(MWrite(title), run_time=1.2)

        stages = VGroup(
            stage_box("Deterministic solvers", "arithmetic - sentiment lexicon - spaCy NER", OK_GREEN),
            stage_box("Local LLM (Qwen2.5-3B, CPU)", "summarization - code, verified for free", OK_GREEN),
            stage_box("Zero-cost gate", "unverifiable answers move on", OK_GREEN),
            stage_box("Fireworks escalation", "kimi - reasoning_effort=none - batched", AMD_RED),
        ).arrange(DOWN, buff=0.42).shift(DOWN * 0.45 + LEFT * 1.1)
        cost_labels = VGroup(
            Text("0 tokens", font_size=22, color=OK_GREEN).next_to(stages[0], RIGHT, buff=0.4),
            Text("0 tokens", font_size=22, color=OK_GREEN).next_to(stages[1], RIGHT, buff=0.4),
            Text("0 tokens", font_size=22, color=OK_GREEN).next_to(stages[2], RIGHT, buff=0.4),
            Text("billed", font_size=22, color=AMD_RED).next_to(stages[3], RIGHT, buff=0.4),
        )
        arrows = VGroup(*[Arrow(stages[i].get_bottom(), stages[i + 1].get_top(),
                                buff=0.06, stroke_width=3, color=GREY_B) for i in range(3)])
        self.play(LaggedStart(*[FadeIn(s, shift=DOWN * 0.2) for s in stages], lag_ratio=0.25),
                  run_time=2.4)
        self.play(Create(arrows), FadeIn(cost_labels), run_time=1.0)

        # 19 tasks fall through the cascade; most stop at a free stage.
        dots = VGroup(*[Dot(radius=0.075, color=YELLOW_D) for _ in range(19)])
        dots.arrange(RIGHT, buff=0.14).next_to(title, DOWN, buff=0.28)
        self.play(FadeIn(dots), run_time=0.7)

        stops = [5, 7, 0, 7]  # solvers, local, (gate holds none itself), escalation
        idx = 0
        for stage_i, count in enumerate(stops):
            if count == 0:
                continue
            group = dots[idx:idx + count]
            idx += count
            for d in group:
                d.generate_target()
                d.target.move_to(stages[stage_i][0].get_center()
                                 + RIGHT * ((hash(str(d)) % 60 - 30) / 12.0))
                d.target.set_color(OK_GREEN if stage_i < 3 else AMD_RED)
            self.play(LaggedStart(*[MoveToTarget(d) for d in group], lag_ratio=0.08),
                      run_time=1.5)

        tally = Text("12 answered free  -  7 escalated in 4 tiny calls",
                     font_size=26, color=WHITE).to_edge(DOWN, buff=0.4)
        self.play(MWrite(tally), run_time=1.2)
        self.wait(1.6)
        self.play(FadeOut(VGroup(title, stages, arrows, cost_labels, dots, tally)), run_time=0.8)


class DescentScene(Scene):
    def construct(self):
        title = Text("Every step measured on the real Fireworks API",
                     font_size=32, color=WHITE).to_edge(UP, buff=0.4)
        self.play(MWrite(title), run_time=1.2)

        steps = [
            ("v11\nall escalated", 6559),
            ("+ batching", 3510),
            ("+ local\nsumm & code", 2758),
            ("+ reasoning\neffort none", 548),
            ("v20 final\n(solo logic)", 649),
        ]
        max_h = 4.6
        bars = VGroup()
        for i, (label, value) in enumerate(steps):
            h = max(0.35, max_h * value / 6559)
            bar = Rectangle(width=1.5, height=h, fill_opacity=1.0, stroke_width=0,
                            fill_color=(AMD_RED if i == 0 else
                                        OK_GREEN if i == len(steps) - 1 else GREY_B))
            bar.move_to(LEFT * 5.2 + RIGHT * (i * 2.35) + DOWN * 2.9 + UP * (h / 2))
            val = Text(f"{value:,}", font_size=24, color=WHITE).next_to(bar, UP, buff=0.12)
            lab = Text(label, font_size=16, color=GREY_B, line_spacing=0.8).next_to(bar, DOWN, buff=0.16)
            bars.add(VGroup(bar, val, lab))

        for group in bars:
            self.play(FadeIn(group, shift=UP * 0.3), run_time=0.85)

        leader_y = DOWN * 2.9 + UP * (max_h * 1377 / 6559)
        leader = VGroup(
            Rectangle(width=12.4, height=0.02, fill_color=YELLOW_D, fill_opacity=1.0,
                      stroke_width=0).move_to(leader_y + RIGHT * 0.5),
            Text("current leader: 1,377", font_size=20, color=YELLOW_D)
            .move_to(leader_y + RIGHT * 4.9 + UP * 0.25),
        )
        self.play(FadeIn(leader), run_time=1.0)
        punch = Text("19/19 accuracy on four consecutive runs", font_size=26, color=OK_GREEN
                     ).to_edge(DOWN, buff=0.35)
        self.play(MWrite(punch), run_time=1.2)
        self.wait(2.0)
        self.play(FadeOut(VGroup(title, bars, leader, punch)), run_time=0.8)
