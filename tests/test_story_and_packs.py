import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from cs2career.career import Career
from cs2career.content.loader import PackRegistry


class StoryAndPackTests(unittest.TestCase):
    def test_story_choice_validation_and_duplicate_ack(self):
        career = Career()
        career.save = Mock()
        career.story_queue = [{'id': 'decision', 'choices': [{'id': 'accept'}]}]
        with self.assertRaises(ValueError):
            career.ack_story('decision', 'refuse')
        self.assertEqual(1, len(career.story_queue))
        career.save.assert_not_called()
        career.ack_story('decision', 'accept')
        career.ack_story('decision', 'accept')
        career.ack_story('unknown')
        career.save.assert_called_once()
        self.assertEqual(['decision'], career.seen_stories)

    def test_malformed_pack_cannot_crash_registry(self):
        for invalid in (None, 12, 'text', {}, [12], [{'text': {}}]):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                pack = root / 'test-pack'
                (pack / 'stories').mkdir(parents=True)
                (pack / 'pack.json').write_text(json.dumps({'id': 'test-pack', 'schema_version': 1, 'types': ['stories']}))
                (pack / 'stories' / 'bad.json').write_text(json.dumps({'stories': invalid}))
                registry = PackRegistry(root)
                self.assertEqual('rejected', registry.packs[0].status)
                self.assertEqual([], registry.payloads('stories'))
