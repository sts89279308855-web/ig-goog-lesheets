"""Offline regression checks. All network entry points are patched."""
import datetime as dt
import json
import unittest
from unittest.mock import Mock, patch
import cloud_pipeline as publisher

class CarouselSafety(unittest.TestCase):
    def setUp(self):
        self.images = [f"https://example.invalid/{i:02}.jpg" for i in range(1, 8)]
        self.entry = dict(id="rita-ig01", date="2026-11-22", status="ready",
                          format="carousel", image_urls=self.images,
                          caption="Approved caption", first_comment="Approved comment")
        self.media = dict(id="published", caption=self.entry["caption"],
                          timestamp="2026-11-22T15:41:00+0000",
                          permalink="https://example.invalid/post")
        self.client = Mock()
        self.next_child = 0
        self.client.tool.side_effect = self.execute
        patches = [
            patch.object(publisher, "connection", return_value=self.client),
            patch.object(publisher, "queue", return_value=[self.entry]),
            patch.object(publisher, "now", return_value=dt.datetime(2026, 11, 22, 20, 40, tzinfo=publisher.TZ)),
            patch.object(publisher, "read_file", return_value=(None, None)),
            patch.object(publisher, "recent", return_value=[]),
            patch.object(publisher, "save_json"),
            patch.object(publisher, "finish"),
            patch.object(publisher, "status"),
            patch.object(publisher.time, "sleep"),
            patch.object(publisher, "gh", side_effect=AssertionError("Unexpected live GitHub call")),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def execute(self, name, args):
        if name == "INSTAGRAM_POST_IG_USER_MEDIA":
            if args.get("is_carousel_item"):
                self.next_child += 1
                return {"id": f"child-{self.next_child}"}
            if args.get("media_type") == "CAROUSEL":
                return {"id": "parent"}
            return {"id": "reel"}
        if name == "INSTAGRAM_GET_POST_STATUS":
            return {"status_code": "FINISHED"}
        if name == "INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH":
            return {"id": "published"}
        if name == "INSTAGRAM_GET_IG_MEDIA":
            return self.media
        if name == "INSTAGRAM_POST_IG_MEDIA_COMMENTS":
            return {"id": "comment"}
        raise AssertionError(name)

    def test_seven_children_then_status_checks_then_parent_then_single_publish(self):
        publisher.publish()
        calls = self.client.tool.call_args_list
        self.assertEqual([c.args[1]["image_url"] for c in calls[:7]], self.images)
        self.assertTrue(all(c.args[1]["is_carousel_item"] for c in calls[:7]))
        self.assertTrue(all(c.args[0] == "INSTAGRAM_GET_POST_STATUS" for c in calls[7:14]))
        self.assertEqual(calls[14].args[1], dict(
            ig_user_id=publisher.IG_USER, media_type="CAROUSEL",
            children=[f"child-{i}" for i in range(1, 8)], caption="Approved caption"))
        self.assertEqual(calls[15].args[1]["creation_id"], "parent")
        self.assertEqual(sum(c.args[0] == "INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH" for c in calls), 1)
        self.assertEqual(calls[-1].args[1]["message"], "Approved comment")

    def test_original_reel_arguments_preserved(self):
        entry = dict(self.entry, format="short", video_raw_url="https://example.invalid/reel.mp4",
                     thumb_offset=9000, hashtags="#example")
        entry.pop("first_comment")
        with patch.object(publisher, "queue", return_value=[entry]):
            publisher.publish()
        self.assertEqual(self.client.tool.call_args_list[0].args[1], dict(
            ig_user_id=publisher.IG_USER, media_type="REELS",
            video_url=entry["video_raw_url"], caption=entry["caption"],
            thumb_offset=9000, share_to_feed=True))
        self.assertEqual(self.client.tool.call_args_list[-1].args[1]["message"], "#example")

    def test_partial_children_resume_in_order(self):
        state = dict(status="preparing", reel_id=self.entry["id"],
                     image_urls=self.images, child_ids=["child-1", "child-2"])
        self.next_child = 2
        with patch.object(publisher, "read_file", side_effect=[(None, None), (json.dumps(state), "sha")]):
            publisher.publish()
        calls = self.client.tool.call_args_list
        created = [c.args[1]["image_url"] for c in calls if c.args[1].get("is_carousel_item")]
        self.assertEqual(created, self.images[2:])
        parent = next(c for c in calls if c.args[1].get("media_type") == "CAROUSEL")
        self.assertEqual(parent.args[1]["children"], [f"child-{i}" for i in range(1, 8)])

    def test_failed_child_blocks_parent_and_publication(self):
        def fail_child(name, args):
            if name == "INSTAGRAM_GET_POST_STATUS":
                return {"status_code": "ERROR"}
            return self.execute(name, args)
        self.client.tool.side_effect = fail_child
        with self.assertRaisesRegex(RuntimeError, "not usable"):
            publisher.publish()
        self.assertFalse(any(c.args[1].get("media_type") == "CAROUSEL" for c in self.client.tool.call_args_list))
        self.assertFalse(any(c.args[0] == "INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH" for c in self.client.tool.call_args_list))

    def test_unknown_publish_response_never_republished(self):
        def uncertain(name, args):
            if name == "INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH":
                raise TimeoutError()
            return self.execute(name, args)
        self.client.tool.side_effect = uncertain
        with self.assertRaisesRegex(RuntimeError, "Uncertain"):
            publisher.publish()
        self.assertEqual(publisher.save_json.call_args.args[1]["status"], "unknown")
        self.assertEqual(sum(c.args[0] == "INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH"
                             for c in self.client.tool.call_args_list), 1)

    def test_today_already_published_skips_carousel(self):
        with patch.object(publisher, "recent", return_value=[dict(self.media, caption="Other")]):
            publisher.publish()
        self.client.tool.assert_not_called()

    def test_invalid_image_count_fails_before_provider_calls(self):
        with patch.object(publisher, "queue", return_value=[dict(self.entry, image_urls=self.images[:1])]):
            with self.assertRaisesRegex(ValueError, "2–10"):
                publisher.publish()
        self.client.tool.assert_not_called()

    def test_saved_parent_is_reused(self):
        state = dict(status="created", reel_id=self.entry["id"], container_id="saved-parent")
        with patch.object(publisher, "read_file", side_effect=[(None, None), (json.dumps(state), "sha")]):
            publisher.publish()
        self.assertEqual(self.client.tool.call_args_list[0].args[0], "INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH")
        self.assertEqual(self.client.tool.call_args_list[0].args[1]["creation_id"], "saved-parent")

if __name__ == "__main__":
    unittest.main()
