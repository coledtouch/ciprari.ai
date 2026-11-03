"""Offline regression checks for staged publication recovery."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import apply_staged as staged

REAL_VALIDATE = staged.writer.validate


class StagedPublishingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.catalog = self.root / 'posts_b.py'
        self.catalog.write_text('original catalog', encoding='utf-8')
        self.patches = [
            patch.object(staged, 'TOKEN', 'test-only'),
            patch.object(staged, 'JOURNAL', self.root / 'journal.json'),
            patch.object(staged, 'RECEIPT', self.root / 'receipt.json'),
            patch.object(staged.writer, 'POSTS_B_PATH', str(self.catalog)),
            patch.object(staged, 'refresh_catalog'),
            patch.object(staged.writer, 'validate', return_value=[]),
            patch.object(staged.writer, 'next_version', return_value='1.0'),
            patch.object(staged.writer, 'compose_entry', return_value=('test-post', 'entry')),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_prepare_never_acknowledges_queue(self):
        with patch.object(staged, 'call', return_value={'posts':[{'id':42} ]}) as call, \
             patch.object(staged.writer, 'append_post'), \
             patch.object(staged.writer, 'try_build', return_value=(True,'')):
            staged.main()
        call.assert_called_once_with('/pending-posts')
        self.assertEqual(json.loads(staged.RECEIPT.read_text()), {'ids':[42]})

    def test_ack_failure_retry_does_not_append_again(self):
        staged.JOURNAL.write_text(json.dumps({'42':'test-post'}))
        with patch.object(staged, 'call', return_value={'posts':[{'id':42} ]}), \
             patch.object(staged.writer, 'append_post') as append, \
             patch.object(staged.writer, 'try_build', return_value=(True,'')):
            staged.main()
        append.assert_not_called()
        self.assertEqual(json.loads(staged.RECEIPT.read_text()), {'ids':[42]})

    def test_off_palette_art_is_repaired_not_refused(self):
        stub = staged.writer.STUB
        art = (stub['svg_inner'].replace(staged.writer.G, '#ff4444') + "<rect fill='white' stroke='rgb(255, 0, 0)'/>"
               "<line x='1' y='1' x2='9' y2='1' stroke='#33ff66'/><text x='10' y='20' fill='#33ff66'>DISK FILL: 92%</text>")
        staged_post = dict({k: stub[k] for k in staged.writer.REQUIRED}, id=43, svg_inner=art)
        self.assertTrue(REAL_VALIDATE(dict(staged_post), 'post'))  # as staged, it fails
        with patch.object(staged, 'call', return_value={'posts':[staged_post]}), \
             patch.object(staged.writer, 'validate', side_effect=REAL_VALIDATE), \
             patch.object(staged.writer, 'append_post'), \
             patch.object(staged.writer, 'try_build', return_value=(True,'')):
            staged.main()
        posted = staged.writer.compose_entry.call_args[0][0]
        self.assertEqual(REAL_VALIDATE(posted, 'post'), [])
        self.assertNotIn('#ff4444', posted['svg_inner'])
        self.assertIn('>DISK FILL: 92%</text>', posted['svg_inner'])
        self.assertEqual(json.loads(staged.RECEIPT.read_text()), {'ids':[43]})

    def test_build_failure_restores_catalog_and_keeps_queue(self):
        with patch.object(staged, 'call', return_value={'posts':[{'id':42} ]}) as call, \
             patch.object(staged.writer, 'append_post', side_effect=lambda _:self.catalog.write_text('changed')), \
             patch.object(staged.writer, 'try_build', return_value=(False,'failed')):
            with self.assertRaises(SystemExit):
                staged.main()
        call.assert_called_once_with('/pending-posts')
        self.assertEqual(self.catalog.read_text(), 'original catalog')
        self.assertFalse(staged.RECEIPT.exists())
        self.assertFalse(staged.JOURNAL.exists())


if __name__ == '__main__':
    unittest.main()
