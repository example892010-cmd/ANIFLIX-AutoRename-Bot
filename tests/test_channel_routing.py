import unittest

from plugins.channel_routing import assigned_ongoing_targets, resolve_ongoing_targets


class FakeCollection:
    def __init__(self, document):
        self.document = document

    async def find_one(self, query):
        if query == {"_id": "global"}:
            return self.document
        return None


class FakeDatabase:
    def __init__(self, document):
        self.collection = FakeCollection(document)

    def __getitem__(self, name):
        if name != "ongoing_channel_settings":
            raise KeyError(name)
        return self.collection


class ChannelRoutingTests(unittest.IsolatedAsyncioTestCase):
    def test_assigned_targets_preserve_order_and_remove_duplicates(self):
        self.assertEqual(
            assigned_ongoing_targets({
                "ongoing_channels": ["@AniOne", "@AniTwo", "@AniThree", "@AniOne"],
            }),
            ["@AniOne", "@AniTwo", "@AniThree"],
        )

    def test_legacy_single_target_is_supported(self):
        self.assertEqual(
            assigned_ongoing_targets({"ongoing_channel": "@LegacyChannel"}),
            ["@LegacyChannel"],
        )

    async def test_route_targets_take_precedence_over_global_targets(self):
        database = FakeDatabase({"channels": [{"chat_id": -1002, "active": True}]})
        result = await resolve_ongoing_targets({"ongoing_channels": ["@AnimeRoute"]}, database)
        self.assertEqual(result, ["@AnimeRoute"])

    async def test_global_fallback_ignores_inactive_and_deduplicates(self):
        database = FakeDatabase({"channels": [
            {"chat_id": "-100123", "active": True},
            {"target": -100123, "active": True},
            {"chat_id": "@DisabledChannel", "active": False},
            {"chat_id": "@ActiveChannel"},
        ]})
        result = await resolve_ongoing_targets({}, database)
        self.assertEqual(result, [-100123, "@ActiveChannel"])


if __name__ == "__main__":
    unittest.main()
