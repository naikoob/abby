"""Unit tests for YAML string escaping, unescaping, and comment stripping utilities."""

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from abby.utils.yaml import (
    format_yaml_tag,
    strip_yaml_comment,
    unescape_yaml_string,
)


class TestYAMLUtils(unittest.TestCase):
    """Tests for YAML string formatting and sanitization."""

    def test_unescape_yaml_string_unquoted(self) -> None:
        self.assertEqual(unescape_yaml_string("hello world"), "hello world")
        self.assertEqual(unescape_yaml_string(""), "")

    def test_unescape_yaml_string_double_quotes(self) -> None:
        self.assertEqual(unescape_yaml_string('"hello world"'), "hello world")
        self.assertEqual(unescape_yaml_string(r'"quoted \"inside\""'), 'quoted "inside"')
        self.assertEqual(unescape_yaml_string(r'"escaped \\ backslash"'), "escaped \\ backslash")

    def test_unescape_yaml_string_single_quotes(self) -> None:
        self.assertEqual(unescape_yaml_string("'simple single'"), "simple single")
        self.assertEqual(unescape_yaml_string("'can\\'t'"), "can't")

    def test_strip_yaml_comment_no_comment(self) -> None:
        self.assertEqual(strip_yaml_comment("active"), "active")
        self.assertEqual(strip_yaml_comment('"quoted # value"'), '"quoted # value"')

    def test_strip_yaml_comment_with_comment(self) -> None:
        self.assertEqual(strip_yaml_comment("active # current status"), "active")
        self.assertEqual(strip_yaml_comment('"title # 1" # inline note'), '"title # 1"')
        self.assertEqual(strip_yaml_comment("'title # 2' # inline note"), "'title # 2'")
        self.assertEqual(strip_yaml_comment(r'"path\\" # comment'), r'"path\\"')

    def test_format_yaml_tag_plain(self) -> None:
        self.assertEqual(format_yaml_tag("machine-learning"), "  - machine-learning")
        self.assertEqual(format_yaml_tag("python"), "  - python")

    def test_format_yaml_tag_with_special_characters(self) -> None:
        self.assertEqual(format_yaml_tag("tag with space"), '  - "tag with space"')
        self.assertEqual(format_yaml_tag("tag:colon"), '  - "tag:colon"')
        self.assertEqual(format_yaml_tag('tag"quote'), '  - "tag\\"quote"')


if __name__ == "__main__":
    unittest.main()
