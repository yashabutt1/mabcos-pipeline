import tempfile
import unittest
from pathlib import Path

from compose import make_paragraph_card


class ParagraphCardTests(unittest.TestCase):
    def test_make_paragraph_card_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "paragraph.png"
            body = "First line of the story.\nSecond line still feels real.\nThird line closes it softly."
            result = make_paragraph_card(None, body, out_path)
            self.assertEqual(result, str(out_path))
            self.assertTrue(out_path.exists())
            self.assertTrue(out_path.stat().st_size > 0)


if __name__ == "__main__":
    unittest.main()
