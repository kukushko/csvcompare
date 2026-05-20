import csv
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "feed_compare.py"


def write_csv(path: Path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        for row in rows:
            writer.writerow(row)


def read_csv(path: Path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class FeedCompareCliTests(unittest.TestCase):
    def run_cli(self, temp_dir: Path, config_data):
        config_path = temp_dir / "config.json"
        config_path.write_text(json.dumps(config_data), encoding="utf-8")

        return subprocess.run(
            [
                "python3",
                str(SCRIPT_PATH),
                "--feed-a",
                str(temp_dir / "feed-a.csv"),
                "--feed-b",
                str(temp_dir / "feed-b.csv"),
                "--conf",
                str(config_path),
                "--out-dir",
                str(temp_dir / "out"),
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_generates_all_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            write_csv(
                temp_dir / "feed-a.csv",
                [
                    ["id", "name", "amount"],
                    ["1", "Alice", "10.0000001"],
                    ["2", "Bob", "20"],
                    ["3", "OnlyA", "30"],
                ],
            )
            write_csv(
                temp_dir / "feed-b.csv",
                [
                    ["id", "name", "amount"],
                    ["1", "alice", "10.0000002"],
                    ["2", "Bobby", "20"],
                    ["4", "OnlyB", "40"],
                ],
            )

            result = self.run_cli(
                temp_dir,
                {
                    "key_fields": ["id"],
                    "fields": {
                        "name": {"type": "string", "case_sensitive": False},
                        "amount": {"type": "number", "tolerance": 1.0e-6},
                    },
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            out_dir = temp_dir / "out"

            self.assertEqual(
                read_csv(out_dir / "feed-a-missing.csv"),
                [{"id": "3", "name": "OnlyA", "amount": "30"}],
            )
            self.assertEqual(
                read_csv(out_dir / "feed-b-missing.csv"),
                [{"id": "4", "name": "OnlyB", "amount": "40"}],
            )
            self.assertEqual(
                read_csv(out_dir / "feed-a-duplicates-ignored.csv"),
                [],
            )
            self.assertEqual(
                read_csv(out_dir / "feed-b-duplicates-ignored.csv"),
                [],
            )
            self.assertEqual(
                read_csv(out_dir / "match.csv"),
                [{"id": "1", "name": "Alice", "amount": "10.0000001"}],
            )
            self.assertEqual(
                read_csv(out_dir / "feed-a-mismatch.csv"),
                [{"id": "2", "name": "Bob", "amount": "20"}],
            )
            self.assertEqual(
                read_csv(out_dir / "feed-b-mismatch.csv"),
                [{"id": "2", "name": "Bobby", "amount": "20"}],
            )
            self.assertEqual(
                read_csv(out_dir / "mismatch-joined.csv"),
                [
                    {
                        "a_id": "2",
                        "a_name": "Bob",
                        "a_amount": "20",
                        "b_id": "2",
                        "b_name": "Bobby",
                        "b_amount": "20",
                    }
                ],
            )

    def test_fails_on_incompatible_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            write_csv(
                temp_dir / "feed-a.csv",
                [["id", "name"], ["1", "Alice"]],
            )
            write_csv(
                temp_dir / "feed-b.csv",
                [["id", "title"], ["1", "Alice"]],
            )

            result = self.run_cli(temp_dir, {"key_fields": ["id"]})

            self.assertEqual(result.returncode, 1)
            self.assertIn("Feed columns are not compatible", result.stderr)

    def test_ignores_duplicate_keys_and_writes_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            write_csv(
                temp_dir / "feed-a.csv",
                [
                    ["id", "name"],
                    ["1", "Alice"],
                    ["1", "Alice2"],
                    ["2", "OnlyA"],
                    ["3", "Shared"],
                ],
            )
            write_csv(
                temp_dir / "feed-b.csv",
                [
                    ["id", "name"],
                    ["3", "Shared"],
                    ["4", "OnlyB"],
                    ["5", "DupB1"],
                    ["5", "DupB2"],
                ],
            )

            result = self.run_cli(temp_dir, {"key_fields": ["id"]})

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            out_dir = temp_dir / "out"

            self.assertEqual(
                read_csv(out_dir / "feed-a-duplicates-ignored.csv"),
                [{"id": "1", "name": "Alice"}, {"id": "1", "name": "Alice2"}],
            )
            self.assertEqual(
                read_csv(out_dir / "feed-b-duplicates-ignored.csv"),
                [{"id": "5", "name": "DupB1"}, {"id": "5", "name": "DupB2"}],
            )
            self.assertEqual(
                read_csv(out_dir / "match.csv"),
                [{"id": "3", "name": "Shared"}],
            )
            self.assertEqual(
                read_csv(out_dir / "feed-a-missing.csv"),
                [{"id": "2", "name": "OnlyA"}],
            )
            self.assertEqual(
                read_csv(out_dir / "feed-b-missing.csv"),
                [{"id": "4", "name": "OnlyB"}],
            )
            self.assertEqual(read_csv(out_dir / "feed-a-mismatch.csv"), [])
            self.assertEqual(read_csv(out_dir / "feed-b-mismatch.csv"), [])
            self.assertEqual(read_csv(out_dir / "mismatch-joined.csv"), [])

    def test_fails_on_invalid_numeric_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            write_csv(
                temp_dir / "feed-a.csv",
                [["id", "amount"], ["1", "oops"]],
            )
            write_csv(
                temp_dir / "feed-b.csv",
                [["id", "amount"], ["1", "1.0"]],
            )

            result = self.run_cli(
                temp_dir,
                {"key_fields": ["id"], "fields": {"amount": {"type": "number"}}},
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("configured as number", result.stderr)

    def test_removes_stale_reports_before_failed_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            out_dir = temp_dir / "out"
            out_dir.mkdir()

            stale_paths = [
                out_dir / "feed-a-missing.csv",
                out_dir / "feed-b-missing.csv",
                out_dir / "feed-a-duplicates-ignored.csv",
                out_dir / "feed-b-duplicates-ignored.csv",
                out_dir / "match.csv",
                out_dir / "feed-a-mismatch.csv",
                out_dir / "feed-b-mismatch.csv",
                out_dir / "mismatch-joined.csv",
            ]
            for path in stale_paths:
                path.write_text("stale\n", encoding="utf-8")

            write_csv(
                temp_dir / "feed-a.csv",
                [["id", "name"], ["1", "Alice"]],
            )
            write_csv(
                temp_dir / "feed-b.csv",
                [["id", "title"], ["1", "Alice"]],
            )

            result = self.run_cli(temp_dir, {"key_fields": ["id"]})

            self.assertEqual(result.returncode, 1)
            self.assertIn("Feed columns are not compatible", result.stderr)
            for path in stale_paths:
                self.assertFalse(path.exists(), msg=f"stale report was not removed: {path}")


if __name__ == "__main__":
    unittest.main()
