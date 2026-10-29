import ast
import re
import unittest
from pathlib import Path

from helper.file_names import extract_season_episode, extract_title

ROOT = Path(__file__).resolve().parents[1]

def _load_batch_parser():
    """Load the actual _parse_upload_details function without importing Telegram/Mongo clients."""
    source = (ROOT / "plugins" / "file_rename.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {"_parse_upload_details", "_parse_batch_command"}]
    module = ast.Module(body=nodes, type_ignores=[])
    namespace = {"re": re}
    exec(compile(module, "plugins/file_rename.py", "exec"), namespace)
    return namespace["_parse_upload_details"], namespace["_parse_batch_command"]


class RequestedUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parse_details, cls.parse_command = _load_batch_parser()
        cls.parse_details = staticmethod(cls.parse_details)
        cls.parse_command = staticmethod(cls.parse_command)

    def test_multiline_title_and_episode_range(self):
        batch_number, result = self.parse_command(
            "/batch1\nTHE EXILED HEAVY KNIGHT\nKNOWS HOW TO GAME THE SYSTEM\nSeason 01\n01 -14"
        )
        self.assertEqual(batch_number, 1)
        self.assertEqual(result, {
            "title": "THE EXILED HEAVY KNIGHT KNOWS HOW TO GAME THE SYSTEM",
            "season": "1",
            "episode_range": "01-14",
        })

    def test_large_episode_numbers_keep_entered_digits(self):
        for episode in ("15", "1000", "590", "05", "09"):
            with self.subTest(episode=episode):
                self.assertEqual(self.parse_command(f"/batch1\nNaruto\nSeason 01\n{episode}")[1]["episode_range"], episode)

    def test_four_digit_filename_episode_is_detected(self):
        self.assertEqual(extract_season_episode("Anime S01E1000 [1080p].mkv"), ("01", "1000"))
        self.assertEqual(extract_title("Anime S01E1000 [1080p].mkv"), "Anime")

    def test_force_sub_limit_and_new_setup_exist(self):
        fsub = (ROOT / "plugins" / "force_subs.py").read_text(encoding="utf-8")
        panel = (ROOT / "plugins" / "admin_panel.py").read_text(encoding="utf-8")
        self.assertIn("_MAX_CHANNELS = 7", fsub)
        self.assertIn("MAX_FSUB_CHANNELS = 7", panel)
        self.assertIn('stage == "fsub_add_forward"', panel)
        self.assertIn('stage == "fsub_add_link"', panel)
        self.assertIn('action.startswith("fsub_mode:")', panel)

    def test_stored_files_and_link_replacement_are_wired(self):
        panel = (ROOT / "plugins" / "admin_panel.py").read_text(encoding="utf-8")
        self.assertIn('callback_data="adm:stored_files"', panel)
        self.assertIn('callback_data="adm:stored_files_clear"', panel)
        self.assertIn('action == "stored_files_clear_confirm"', panel)
        self.assertIn('anime_replace_button_link', panel)
        self.assertIn('_find_recorded_anime_post', panel)
        self.assertIn('editMessageReplyMarkup', panel)
        publisher = (ROOT / "plugins" / "episode_publisher.py").read_text(encoding="utf-8")
        self.assertIn('"episode_display": episode_display', publisher)
        self.assertIn('batch.get("episode_display") or batch["episode"]', publisher)
        self.assertIn('episode_display = str(episode).strip() if episode else None', publisher)

if __name__ == "__main__":
    unittest.main()
