import unittest
from pathlib import Path

from components import design_tokens


ROOT = Path(__file__).resolve().parents[1]


class DesignSystemTests(unittest.TestCase):
    def test_design_contract_and_agent_instruction_exist(self):
        self.assertTrue((ROOT / "DESIGN.md").is_file())
        self.assertIn("DESIGN.md", (ROOT / "AGENTS.md").read_text(encoding="utf-8"))

    def test_css_and_plotly_core_tokens_stay_aligned(self):
        css = (ROOT / "styles" / "main.css").read_text(encoding="utf-8")
        expected = {
            "--color-canvas": design_tokens.COLOR_CANVAS,
            "--color-surface-1": design_tokens.COLOR_SURFACE_1,
            "--color-text-primary": design_tokens.COLOR_TEXT_PRIMARY,
            "--color-text-secondary": design_tokens.COLOR_TEXT_SECONDARY,
            "--color-text-muted": design_tokens.COLOR_TEXT_MUTED,
            "--color-text-dim": design_tokens.COLOR_TEXT_DIM,
            "--color-action": design_tokens.COLOR_ACTION,
            "--color-positive": design_tokens.COLOR_POSITIVE,
            "--color-negative": design_tokens.COLOR_NEGATIVE,
            "--color-border-subtle": design_tokens.COLOR_BORDER,
            "--color-chart-grid": design_tokens.COLOR_GRID,
        }

        for token, value in expected.items():
            with self.subTest(token=token):
                self.assertIn(f"{token}: {value};", css)

    def test_editorial_accent_is_reserved_for_ai_commentary(self):
        css = (ROOT / "styles" / "main.css").read_text(encoding="utf-8")

        self.assertIn("--color-accent-peach: #fbe1d1;", css)
        self.assertEqual(css.count("background: var(--color-accent-peach);"), 1)
        self.assertIn(".ai-insight-card {", css)
        self.assertIn("'Yu Mincho'", css)


if __name__ == "__main__":
    unittest.main()
