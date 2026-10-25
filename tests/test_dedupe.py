import tempfile
import unittest
from pathlib import Path

from dedupe import is_duplicate, load_used_content
import gen_text


class DedupeTests(unittest.TestCase):
    def test_is_duplicate_matches_normalized_text(self):
        self.assertTrue(is_duplicate("Silence can say more than a fight!", "silence can say more than a fight"))
        self.assertTrue(is_duplicate("You need to stop texting him", "You need to stop texting him, honestly"))
        self.assertFalse(is_duplicate("You need to stop texting him", "You should start setting better boundaries"))

    def test_load_used_content_reads_previous_captions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prev = root / "output" / "2026-07-05"
            prev.mkdir(parents=True, exist_ok=True)
            (prev / "captions.json").write_text(
                '{"cards": [{"line": "Silence can say more than a fight."}]}',
                encoding="utf-8",
            )
            used = load_used_content(root / "output")
            self.assertIn("silence can say more than a fight", used)

        def test_make_paragraphs_fallback_returns_unique_items(self):
            orig_client = gen_text._client
            try:
                gen_text._client = None
                paragraphs = gen_text.make_paragraphs(2)
                self.assertEqual(len(paragraphs), 2)
                self.assertNotEqual(paragraphs[0]["body"], paragraphs[1]["body"])
            finally:
                gen_text._client = orig_client


if __name__ == "__main__":
    unittest.main()
