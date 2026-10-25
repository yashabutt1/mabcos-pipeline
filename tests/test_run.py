import unittest

import run


class RunCliTests(unittest.TestCase):
    def test_default_count_is_one(self):
        args = run.parse_args([])
        self.assertEqual(args.count, 1)

    def test_count_flag_is_honored(self):
        args = run.parse_args(["--count", "7"])
        self.assertEqual(args.count, 7)

    def test_count_must_be_positive(self):
        with self.assertRaises(SystemExit):
            run.parse_args(["--count", "0"])


if __name__ == "__main__":
    unittest.main()
