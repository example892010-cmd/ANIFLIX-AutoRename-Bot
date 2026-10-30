import ast
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "apply_fix.py"
SPEC = importlib.util.spec_from_file_location("apply_fix", SCRIPT)
apply_fix = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(apply_fix)


class PatchTransformTests(unittest.TestCase):
    def test_file_rename_adds_ongoing_import_and_two_independent_publish_attempts(self):
        source = (
            apply_fix.IMPORT_ANCHOR + "\n\n"
            "async def _publish_batch1renamed_link(client, message, details: dict) -> None:\n"
            "    pass\n\n"
            "async def _active_batch_task(user_id: int) -> dict | None:\n"
            "    pass\n"
        )
        changed = apply_fix.transform_file_rename(source)
        self.assertIn(apply_fix.ONGOING_IMPORT, changed)
        self.assertIn("await _send_ongoing_bot_api", changed)
        self.assertIn("await _post_ongoing_anime(", changed)
        self.assertIn("season=season", changed)
        self.assertIn("episode_range=episode", changed)
        self.assertIn("No media was downloaded or stored", changed)
        self.assertLess(changed.index("except Exception as exc:", changed.index("anime_result =")),
                        changed.index("ongoing_result = await _post_ongoing_anime"))

    def test_link_only_handler_keeps_media_out_of_its_flow(self):
        source = (
            apply_fix.IMPORT_ANCHOR + "\n"
            "async def _publish_batch1renamed_link(client, message, details: dict) -> None:\n"
            "    pass\n\n"
            "async def _active_batch_task(user_id: int) -> dict | None:\n"
            "    pass\n"
        )
        changed = apply_fix.transform_file_rename(source)
        body = changed.split("async def _publish_batch1renamed_link", 1)[1].split(
            "async def _active_batch_task", 1
        )[0]
        self.assertNotIn("auto_rename_files(", body)
        self.assertNotIn("store_file_and_process(", body)
        self.assertNotIn("download_media(", body)

    def test_ongoing_overrides_episode_without_changing_admin_call_compatibility(self):
        source = (
            apply_fix.OLD_ONGOING_SIGNATURE + "\n"
            "    values = {\n"
            + apply_fix.OLD_ONGOING_VALUES + "\n"
            "    }\n"
            "    return values\n"
        )
        changed = apply_fix.transform_ongoing_posts(source)
        self.assertIn("season: str | None = None", changed)
        self.assertIn("episode_range: str | None = None", changed)
        self.assertIn("season if season is not None", changed)
        self.assertIn("episode_range if episode_range is not None", changed)
        self.assertIn("details.get(\"episode_range\")", changed)

    def test_inserted_python_blocks_are_syntactically_valid(self):
        ast.parse(apply_fix.NEW_LINK_ONLY_FUNCTION)
        ast.parse(apply_fix.NEW_ONGOING_SIGNATURE + "\n    pass\n")
        ast.parse("values = {\n" + apply_fix.NEW_ONGOING_VALUES + "\n}\n")

    def test_transforms_are_idempotent(self):
        file_source = (
            apply_fix.IMPORT_ANCHOR + "\n"
            "async def _publish_batch1renamed_link(client, message, details: dict) -> None:\n"
            "    pass\n\n"
            "async def _active_batch_task(user_id: int) -> dict | None:\n"
            "    pass\n"
        )
        ongoing_source = (
            apply_fix.OLD_ONGOING_SIGNATURE + "\n"
            "    values = {\n" + apply_fix.OLD_ONGOING_VALUES + "\n    }\n"
        )
        file_once = apply_fix.transform_file_rename(file_source)
        ongoing_once = apply_fix.transform_ongoing_posts(ongoing_source)
        self.assertEqual(file_once, apply_fix.transform_file_rename(file_once))
        self.assertEqual(ongoing_once, apply_fix.transform_ongoing_posts(ongoing_once))


if __name__ == "__main__":
    unittest.main()
