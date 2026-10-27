import unittest

from helper.file_names import (
    extract_quality,
    extract_season_episode,
    format_caption,
    metadata_enabled,
    render_filename,
    sanitize_filename,
)


class FileNameTests(unittest.TestCase):
    def test_standard_season_episode(self):
        self.assertEqual(
            extract_season_episode("Naruto Shippuden S01E02 [1080p].mkv"),
            ("01", "02"),
        )

    def test_ep_only_pattern_does_not_crash(self):
        self.assertEqual(extract_season_episode("Anime EP12 480p.mp4"), (None, "12"))

    def test_full_episode_pattern(self):
        self.assertEqual(
            extract_season_episode("One Piece Episode 101 [1080p].mkv"),
            (None, "101"),
        )

    def test_quality_detection(self):
        self.assertEqual(extract_quality("Anime S01E02 [720p].mkv"), "720p")

    def test_template_placeholders(self):
        self.assertEqual(
            render_filename(
                "Naruto Shippuden S01E02 [1080p].mkv",
                "ANIFLIX - {title} S{season} Ep{episode} [{quality}] [TAMIL]",
            ),
            "ANIFLIX - Naruto Shippuden S01 Ep02 [1080p] [TAMIL].mkv",
        )

    def test_legacy_template(self):
        self.assertEqual(
            render_filename("Anime EP12 480p.mp4", "Sseason Eepisode quality"),
            "SXX E12 480p.mp4",
        )

    def test_missing_fields_use_safe_defaults(self):
        self.assertEqual(
            render_filename("Show.mkv", "{title} S{season} Ep{episode} [{quality}]"),
            "Show SXX EpXX [Unknown].mkv",
        )

    def test_filename_is_not_a_path(self):
        result = sanitize_filename("../../evil:show.mkv")
        self.assertNotIn("/", result)
        self.assertNotIn("\\", result)
        self.assertTrue(result.endswith(".mkv"))

    def test_caption_placeholders(self):
        self.assertEqual(
            format_caption("{filename} | {filesize} | {duration}", "ep.mkv", 1024, 65),
            "ep.mkv | 1.00 KB | 01:05",
        )

    def test_metadata_settings_compatibility(self):
        self.assertTrue(metadata_enabled(True))
        self.assertTrue(metadata_enabled("On"))
        self.assertFalse(metadata_enabled("Off"))


if __name__ == "__main__":
    unittest.main()
