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
    from urllib.parse import urlparse
    namespace = {"re": re, "urlparse": urlparse}
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

    def test_batch1renamed_accepts_single_and_range_episode_values(self):
        for episode, expected in (("04", "04"), ("01 - 04", "01-04"), ("15", "15"), ("590", "590"), ("1000", "1000")):
            with self.subTest(episode=episode):
                batch_number, result = self.parse_command(f"/batch1renamed\nNaruto\nSeason 01\n{episode}")
                self.assertEqual(batch_number, 1)
                self.assertTrue(result["skip_rename"])
                self.assertEqual(result["episode_range"], expected)

    def test_batch1renamed_link_only_parses_stored_url_without_changing_episode(self):
        batch_number, result = self.parse_command(
            "/batch1renamed\nNaruto\nSeason 01\n590\nhttps://t.me/Aniflixanimefilestorebot?start=ABC123"
        )
        self.assertEqual(batch_number, 1)
        self.assertTrue(result["skip_rename"])
        self.assertTrue(result["link_only"])
        self.assertEqual(result["episode_range"], "590")
        self.assertEqual(result["stored_link"], "https://t.me/Aniflixanimefilestorebot?start=ABC123")

    def test_batch1renamed_still_supports_file_store_mode_without_link(self):
        batch_number, result = self.parse_command("/batch1renamed\nNaruto\nSeason 01\n01 - 04")
        self.assertEqual(batch_number, 1)
        self.assertTrue(result["skip_rename"])
        self.assertNotIn("link_only", result)
        self.assertEqual(result["episode_range"], "01-04")

    def test_link_only_button_template_renders_episode_and_uses_supplied_url(self):
        from urllib.parse import urlparse
        import re
        source = (ROOT / "plugins" / "file_rename.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        wanted = {"_build_batch1renamed_button_rows"}
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
        assignment = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "DEFAULT_BATCH1RENAMED_BUTTON_TEMPLATE" for t in n.targets))
        namespace = {"re": re, "urlparse": urlparse}
        exec(compile(ast.Module(body=[assignment, *nodes], type_ignores=[]), "plugins/file_rename.py", "exec"), namespace)
        rows = namespace["_build_batch1renamed_button_rows"](
            "#g EPISODE {episode} - {link}",
            {"title": "Naruto", "season": "1", "episode_range": "590"},
            "https://t.me/stored/file",
        )
        self.assertEqual(rows[0][0]["text"], "EPISODE 590")
        self.assertEqual(rows[0][0]["url"], "https://t.me/stored/file")
        self.assertEqual(rows[0][0]["style"], "success")

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


    def test_force_sub_membership_status_helpers_are_fail_safe(self):
        source = (ROOT / "plugins" / "force_subs.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        wanted = {"_member_status", "_member_is_missing"}
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
        namespace = {}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "plugins/force_subs.py", "exec"), namespace)

        class Member:
            def __init__(self, status, is_member=False):
                self.status = status
                self.is_member = is_member

        self.assertTrue(namespace["_member_is_missing"](Member("left")))
        self.assertTrue(namespace["_member_is_missing"](Member("kicked")))
        self.assertTrue(namespace["_member_is_missing"](Member("restricted", False)))
        self.assertFalse(namespace["_member_is_missing"](Member("restricted", True)))
        self.assertEqual(namespace["_member_status"](Member("administrator")), "administrator")

    def test_force_sub_invite_url_is_normalized_for_join_button(self):
        source = (ROOT / "plugins" / "admin_panel.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_normalize_fsub_invite_url")
        from urllib.parse import urlparse
        namespace = {"urlparse": urlparse}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "plugins/admin_panel.py", "exec"), namespace)
        normalize = namespace["_normalize_fsub_invite_url"]
        self.assertEqual(normalize("https://www.t.me/+abc123"), "https://t.me/+abc123")
        self.assertEqual(normalize("https://telegram.me/joinchat/abc123"), "https://t.me/joinchat/abc123")
        with self.assertRaises(ValueError):
            normalize("https://example.com/not-an-invite")

    def test_file_delivery_runs_force_sub_check_before_lookup(self):
        source = (ROOT / "plugins" / "start_cb.py").read_text(encoding="utf-8")
        handler = source[source.index("async def _deliver_file_token"):source.index('@Client.on_message(filters.private & filters.command("start"))')]
        self.assertIn("check_fsub_membership(client, user_id)", handler)
        self.assertLess(handler.index("check_fsub_membership(client, user_id)"), handler.index('"file_store"'))

    def test_link_only_publish_and_custom_button_template_are_wired(self):
        file_rename = (ROOT / "plugins" / "file_rename.py").read_text(encoding="utf-8")
        panel = (ROOT / "plugins" / "admin_panel.py").read_text(encoding="utf-8")
        self.assertIn('if details.get("link_only"):', file_rename)
        self.assertIn('_send_ongoing_bot_api(client, int(chat.id), None, caption, button_rows)', file_rename)
        self.assertIn('batch1renamed_button_template', panel)
        self.assertIn('adm:batch1renamed_button_edit', panel)

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


def test_reupload_published_episode_allows_republish():
    """Previously published batches must be reusable when an admin re-uploads a quality."""
    from pathlib import Path

    source = (Path(__file__).parents[1] / "plugins" / "episode_publisher.py").read_text()
    assert 'return exact, "republish"' in source
    assert 'return published[0][1], "republish"' in source
    assert '"published_targets": {}} if republishing else {}' in source
    assert "duplicate {quality} was not published again" not in source
