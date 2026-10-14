import csv
import tempfile
import unittest
from pathlib import Path

import collector


class CollectorTests(unittest.TestCase):
    def test_parsing_preserves_rank_and_removes_duplicates(self):
        self.assertEqual(collector.parse_response('["seed", [" eins ", "eins", "zwei", ""]]'), [(1, "eins"), (3, "zwei")])

    def test_unexpected_response_is_rejected(self):
        for raw in ('{}', '["seed", [42]]', '<html>blocked</html>'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                collector.parse_response(raw)

    def test_query_deduplication(self):
        self.assertEqual(list(collector.make_queries(["MANSTORE", " MANSTORE ", "# comment", ""], False)), ["MANSTORE"])

    def test_persistence_provenance_errors_and_excel_export(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
            path = Path(directory)
            db = collector.open_database(path / "test.sqlite3")
            with db:
                run = db.execute("INSERT INTO runs(started_at, status) VALUES (?, 'running')", (collector.now(),)).lastrowid
            collector.record_fetch(db, run, "first", [(1, "größe"), (2, "=formula")])
            collector.record_fetch(db, run, "second", [(3, "größe")])
            collector.record_fetch(db, run, "blocked", status="error", http_status=429, error="rate limited")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM suggestions").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM observations").fetchone()[0], 3)
            self.assertEqual(db.execute("SELECT http_status FROM fetches WHERE status='error'").fetchone()[0], 429)
            output = path / "out.csv"
            collector.export_csv(db, output)
            self.assertTrue(output.read_bytes().startswith(b'\xef\xbb\xbf'))
            with output.open(encoding="utf-8-sig", newline="") as source:
                rows = list(csv.DictReader(source, delimiter=";"))
            self.assertEqual(len(rows), 3)
            self.assertEqual({row['source_query'] for row in rows if row['query'] == 'größe'}, {'first', 'second'})
            self.assertIn("'=formula", [row['query'] for row in rows])
            db.close()
            db = collector.open_database(path / "test.sqlite3")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM observations").fetchone()[0], 3)
            db.close()


if __name__ == "__main__":
    unittest.main()
