import unittest
import os
import tempfile
import datetime
from utils.stats import (
    build_overview_markdown,
    build_source_stats_markdown,
    apply_readme_updates,
    update_readme_all,
)


class TestStats(unittest.TestCase):
    def setUp(self):
        self.sample_readme = (
            "# Project\n\n"
            "<!-- STATS_BADGE_START -->\nold_badges\n<!-- STATS_BADGE_END -->\n\n"
            "<!-- STATS_TABLE_START -->\nold_table\n<!-- STATS_TABLE_END -->\n\n"
            "<!-- SOURCE_STATS_TABLE_START -->\nold_sources\n<!-- SOURCE_STATS_TABLE_END -->\n"
        )
        self.gen_stats = {
            'total_nodes': 100,
            'region_nodes': {'HK': ['node1', 'node2'], 'US': ['node3']},
            'others': ['node4'],
            'timestamp': '2026-10-08 12:00:00',
            'source_count': 5,
            'raw_count': 200,
            'elapsed_time': 3.14,
        }
        self.source_results = [
            {'name': 'Source A', 'valid_count': 80},
            {'name': 'Source B', 'valid_count': 20},
        ]

    def test_apply_readme_updates_both(self):
        updated = apply_readme_updates(
            self.sample_readme,
            gen_stats=self.gen_stats,
            source_results=self.source_results,
            now=datetime.datetime(2026, 10, 8, 12, 0, 0),
        )

        self.assertNotIn("old_badges", updated)
        self.assertNotIn("old_table", updated)
        self.assertNotIn("old_sources", updated)

        self.assertIn("Valid_Nodes-100", updated)
        self.assertIn("香港", updated)
        self.assertIn("美国", updated)
        self.assertIn("Source A", updated)
        self.assertIn("80.00%", updated)

    def test_update_readme_all_file_io(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "README.md")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.sample_readme)

            update_readme_all(
                self.gen_stats,
                self.source_results,
                now=datetime.datetime(2026, 10, 8, 12, 0, 0),
                readme_path=file_path,
            )

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("Valid_Nodes-100", content)
            self.assertIn("Source A", content)

    def test_update_readme_all_missing_file_noop(self):
        # Should not raise exception if file doesn't exist
        update_readme_all(
            self.gen_stats,
            self.source_results,
            readme_path="/nonexistent/path/README.md",
        )


if __name__ == "__main__":
    unittest.main()
