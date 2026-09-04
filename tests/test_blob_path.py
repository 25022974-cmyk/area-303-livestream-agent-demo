"""Unit tests for BlobPath using mocked vercel.blob SDK calls."""
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.blob_path import BlobPath, BlobStat


class TestBlobPath(unittest.TestCase):
    def test_path_join_and_name(self):
        p = BlobPath("shops") / "123" / "config.json"
        self.assertEqual(str(p), "shops/123/config.json")
        self.assertEqual(p.name, "config.json")

    @patch("vercel.blob.get")
    @patch("vercel.blob.put")
    def test_write_and_read_text(self, mock_put, mock_get):
        mock_get.return_value = MagicMock(content=b'{"k": 1}')
        p = BlobPath("shops/123/config.json")
        p.write_text('{"k": 1}')
        mock_put.assert_called_once()
        self.assertEqual(p.read_text(), '{"k": 1}')

    @patch("vercel.blob.head")
    def test_exists_true(self, mock_head):
        mock_head.return_value = MagicMock(size=10)
        self.assertTrue(BlobPath("shops/123/f.json").exists())

    @patch("vercel.blob.list_objects")
    @patch("vercel.blob.head")
    def test_exists_false(self, mock_head, ml):
        from vercel.blob.errors import BlobNotFoundError
        mock_head.side_effect = Exception("not found")
        ml.return_value = MagicMock(blobs=[])
        self.assertFalse(BlobPath("shops/123/missing.json").exists())

    @patch("vercel.blob.delete")
    def test_unlink_calls_delete(self, mock_del):
        BlobPath("shops/123/orders.json").unlink()
        mock_del.assert_called_once_with("shops/123/orders.json")

    @patch("vercel.blob.head")
    def test_stat_returns_blobstat(self, mock_head):
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        mock_head.return_value = MagicMock(size=999, uploaded_at=ts)
        s = BlobPath("shops/123/orders.json").stat()
        self.assertIsInstance(s, BlobStat)
        self.assertEqual(s.st_size, 999)
        self.assertEqual(s.st_mtime, ts.timestamp())

    @patch("vercel.blob.iter_objects")
    def test_glob_filters_by_pattern(self, mock_iter):
        mock_iter.return_value = iter([
            MagicMock(pathname="shops/123/playbooks/playbook_20260101.json"),
            MagicMock(pathname="shops/123/playbooks/other_file.txt"),
        ])
        results = list(BlobPath("shops/123/playbooks").glob("playbook_*.json"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "playbook_20260101.json")

if __name__ == "__main__":
    unittest.main()
