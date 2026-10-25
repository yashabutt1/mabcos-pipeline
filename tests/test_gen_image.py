import tempfile
import unittest
from pathlib import Path

import config
from gen_image import make_background, make_gradient_background


class LocalBackgroundTests(unittest.TestCase):
    def test_gradient_background_creates_png_without_network(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "bg.png"
            result = make_gradient_background("cozy dusk", out_path, 1080, 1350)
            self.assertEqual(result, str(out_path))
            self.assertTrue(out_path.exists())
            self.assertTrue(out_path.stat().st_size > 0)

    def test_make_background_falls_back_to_gradient_when_source_disabled(self):
        original = config.IMAGE_SOURCE
        config.IMAGE_SOURCE = "gradient"  # force the offline path regardless of key
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                out_path = Path(tmpdir) / "bg.png"
                result = make_background("cozy dusk", out_path, 1080, 1350)
                self.assertEqual(result, str(out_path))
                self.assertTrue(out_path.exists())
                self.assertTrue(out_path.stat().st_size > 0)
        finally:
            config.IMAGE_SOURCE = original


if __name__ == "__main__":
    unittest.main()
