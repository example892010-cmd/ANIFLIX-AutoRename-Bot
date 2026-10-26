import unittest

from filename_parser import parse_filename
from filename_utils import build_filename


class TestFilenameParser(unittest.TestCase):
    def test_parse_season_episode_quality(self):
        result = parse_filename("Naruto S01E05 1080p.mkv")

        self.assertEqual(result["title"], "Naruto")
        self.assertEqual(result["season"], "01")
        self.assertEqual(result["episode"], "05")
        self.assertEqual(result["quality"], "1080P")

    def test_parse_season_episode_format(self):
        result = parse_filename("Anime Season 2 Episode 8 720p.mp4")

        self.assertEqual(result["title"], "Anime")
        self.assertEqual(result["season"], "2")
        self.assertEqual(result["episode"], "8")
        self.assertEqual(result["quality"], "720P")


class TestFilenameBuilder(unittest.TestCase):
    def test_build_filename(self):
        result = build_filename(
            "Naruto S01E05 1080p.mkv",
            "{title} S{season} Ep{episode} [{quality}] [TAMIL]",
        )

        self.assertTrue(result.endswith(".mkv"))
        self.assertIn("Naruto", result)
        self.assertIn("S", result)
        self.assertIn("Ep", result)


if __name__ == "__main__":
    unittest.main()
