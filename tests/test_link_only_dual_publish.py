import ast
import re
import unicodedata
import unittest
from urllib.parse import urlparse

from helper.file_names import normalize_anime_title
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LinkOnlyDualPublishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.file_source = (ROOT / "plugins" / "file_rename.py").read_text(encoding="utf-8")
        cls.ongoing_source = (ROOT / "plugins" / "ongoing_posts.py").read_text(encoding="utf-8")
        cls.file_tree = ast.parse(cls.file_source)
        cls.ongoing_tree = ast.parse(cls.ongoing_source)
        cls.link_handler = next(
            node for node in cls.file_tree.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "_publish_batch1renamed_link"
        )
        cls.ongoing_publisher = next(
            node for node in cls.ongoing_tree.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "post_ongoing_anime"
        )

    def test_link_only_publishes_to_both_destinations_independently(self):
        body = ast.get_source_segment(self.file_source, self.link_handler)
        self.assertIn("await _send_ongoing_bot_api(client, api_target, None, caption, button_rows)", body)
        self.assertIn("await _post_ongoing_anime(", body)
        self.assertIn("season=season", body)
        self.assertIn("episode_range=episode", body)
        self.assertIn("Anime Post:", body)
        self.assertIn("Ongoing:", body)
        # The Ongoing attempt is outside the Anime Post try/except and therefore still runs
        # when Anime Post publishing fails.
        self.assertLess(body.index("anime_result = f\"❌ Anime Post failed:"), body.index("await _post_ongoing_anime("))

    def test_link_only_does_not_download_rename_or_store_media(self):
        body = ast.get_source_segment(self.file_source, self.link_handler)
        for forbidden in ("download_media(", "auto_rename_files(", "store_file_and_process(", "client.download_media("):
            self.assertNotIn(forbidden, body)

    def test_private_numeric_anime_channel_uses_direct_bot_api_target(self):
        body = ast.get_source_segment(self.file_source, self.link_handler)
        self.assertIn('individual_target.lstrip("-").isdigit()', body)
        self.assertIn("api_target = (", body)
        # Do not resolve a private numeric channel through the Pyrogram peer cache.
        self.assertNotIn("client.get_chat(individual_target)", body)

    def test_ongoing_post_accepts_current_episode_and_resolves_global_targets(self):
        args = self.ongoing_publisher.args
        arg_names = [arg.arg for arg in args.args]
        self.assertIn("season", arg_names)
        self.assertIn("episode_range", arg_names)
        body = ast.get_source_segment(self.ongoing_source, self.ongoing_publisher)
        self.assertIn("season_value", body)
        self.assertIn("episode_value", body)
        self.assertIn("await resolve_ongoing_targets(route, codeflixbots.codeflixbots)", body)

    def test_ongoing_still_uses_saved_poster_text_buttons_and_anime_invites(self):
        body = ast.get_source_segment(self.ongoing_source, self.ongoing_publisher)
        self.assertIn('post_settings.get("ongoing_template")', body)
        self.assertIn('post_settings.get("ongoing_buttons_template")', body)
        self.assertIn('saved_template.get("poster_file_id")', body)
        self.assertIn('codeflixbots.codeflixbots["anime_invite_links"]', body)
        self.assertIn("_build_button_rows(button_template, links)", body)

    def test_ongoing_download_button_uses_the_matching_anime_saved_invite(self):
        wanted_functions = {
            "_plain_label", "_valid_http_url", "_select_anime_invite",
            "_is_dynamic_invite", "_build_button_rows",
        }
        nodes = [
            node for node in self.ongoing_tree.body
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted_functions)
            or (isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "_BUTTON_STYLES"
                for target in node.targets
            ))
        ]
        namespace = {
            "re": re, "unicodedata": unicodedata, "urlparse": urlparse,
            "normalize_anime_title": normalize_anime_title,
        }
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "plugins/ongoing_posts.py", "exec"), namespace)
        rows = namespace["_build_button_rows"](
            "#g DOWNLOAD NOW - {anime_invite}\n#b ANIME INDEX - https://t.me/aniflixindex",
            [{"label": "Naruto Download", "url": "https://t.me/+narutoInvite123"}],
        )
        self.assertEqual(rows[0][0]["url"], "https://t.me/+narutoInvite123")
        self.assertEqual(rows[0][0]["style"], "success")
        self.assertEqual(rows[1][0]["url"], "https://t.me/aniflixindex")


if __name__ == "__main__":
    unittest.main()
