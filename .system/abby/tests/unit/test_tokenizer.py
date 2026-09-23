"""Unit tests for the OKF Frontmatter Tokenizer (abby.models.okf)."""

import unittest
from abby.models.okf import ParsedFrontmatter
from abby.services.okf_parser import tokenize_frontmatter


class TestOKFTokenizer(unittest.TestCase):
    """Test suite verifying robust, non-destructive OKF frontmatter tokenization."""

    def test_standard_frontmatter_tokenization(self):
        text = (
            "---\n"
            'title: "Architecture Guide"\n'
            'created: "2026-09-17T12:00:00"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n"
            "  - system\n"
            "  - architecture\n"
            "---\n"
            "\n"
            "# Architecture Guide\n"
            "\n"
            "Core architectural tenets and design principles.\n"
        )
        parsed = tokenize_frontmatter(text)

        self.assertTrue(parsed.has_frontmatter)
        self.assertTrue(parsed.is_closed)
        self.assertEqual(parsed.closing_line_number, 9)
        self.assertIn("title", parsed.fields)
        self.assertEqual(parsed.fields["title"][0], '"Architecture Guide"')
        self.assertEqual(parsed.fields["title"][1], 2)
        self.assertEqual(parsed.fields["created"][0], '"2026-09-17T12:00:00"')
        self.assertEqual(parsed.fields["created"][1], 3)
        self.assertEqual(parsed.fields["type"][0], "resource-note")
        self.assertEqual(parsed.fields["status"][0], "evergreen")

        self.assertFalse(parsed.tags_is_scalar)
        self.assertEqual(parsed.tags_line, 6)
        self.assertEqual(len(parsed.tags), 2)
        self.assertEqual(parsed.tags[0], ("system", 7))
        self.assertEqual(parsed.tags[1], ("architecture", 8))

        self.assertEqual(
            parsed.body_content,
            "\n# Architecture Guide\n\nCore architectural tenets and design principles.\n",
        )

    def test_no_frontmatter(self):
        text = "# Plain Note\n\nJust a note with no metadata header.\n"
        parsed = tokenize_frontmatter(text)

        self.assertFalse(parsed.has_frontmatter)
        self.assertFalse(parsed.is_closed)
        self.assertEqual(parsed.closing_line_number, -1)
        self.assertEqual(parsed.raw_frontmatter, "")
        self.assertEqual(parsed.fields, {})
        self.assertEqual(parsed.tags, [])
        self.assertEqual(parsed.tags_line, -1)
        self.assertFalse(parsed.tags_is_scalar)
        self.assertEqual(parsed.body_content, text)

    def test_unclosed_frontmatter(self):
        text = '---\ntitle: "Dangling Note"\ntype: inbox\n# Body begins without closing delimiter\nSome text'
        parsed = tokenize_frontmatter(text)

        self.assertTrue(parsed.has_frontmatter)
        self.assertFalse(parsed.is_closed)
        self.assertEqual(parsed.closing_line_number, -1)
        self.assertIn("title", parsed.fields)
        self.assertEqual(parsed.fields["title"][0], '"Dangling Note"')

    def test_tags_inline_list(self):
        text = (
            "---\n"
            'title: "Inline Tags"\n'
            "tags: [tag-a, \"tag b\", 'tag-c']\n"
            "---\n"
            "Body\n"
        )
        parsed = tokenize_frontmatter(text)

        self.assertTrue(parsed.has_frontmatter)
        self.assertTrue(parsed.is_closed)
        self.assertFalse(parsed.tags_is_scalar)
        self.assertEqual(parsed.tags_line, 3)
        tag_values = [t[0] for t in parsed.tags]
        self.assertEqual(tag_values, ["tag-a", "tag b", "tag-c"])

    def test_tags_scalar_comma_separated(self):
        text = (
            "---\n"
            'title: "Scalar Tags"\n'
            "tags: apple, banana, cherry\n"
            "---\n"
            "Body\n"
        )
        parsed = tokenize_frontmatter(text)

        self.assertTrue(parsed.has_frontmatter)
        self.assertTrue(parsed.is_closed)
        self.assertTrue(parsed.tags_is_scalar)
        self.assertEqual(parsed.tags_line, 3)
        tag_values = [t[0] for t in parsed.tags]
        self.assertEqual(tag_values, ["apple", "banana", "cherry"])

    def test_empty_tags(self):
        text_brackets = '---\ntitle: "Empty"\ntags: []\n---\n'
        parsed_brackets = tokenize_frontmatter(text_brackets)
        self.assertFalse(parsed_brackets.tags_is_scalar)
        self.assertEqual(parsed_brackets.tags, [])

        text_bare = '---\ntitle: "Empty Bare"\ntags:\n---\n'
        parsed_bare = tokenize_frontmatter(text_bare)
        self.assertFalse(parsed_bare.tags_is_scalar)
        self.assertEqual(parsed_bare.tags, [])

    def test_escaped_quotes_and_yaml_comments(self):
        text = (
            "---\n"
            "# This is a header comment\n"
            'title: "Note with \\"Escaped\\" Quotes and \\\\ Backslashes"\n'
            "# Another comment\n"
            "type: project-note # inline comment\n"
            "---\n"
            "Content with ^d8b1a4\n"
        )
        parsed = tokenize_frontmatter(text)

        self.assertTrue(parsed.has_frontmatter)
        self.assertIn("title", parsed.fields)
        self.assertEqual(
            parsed.fields["title"][0],
            '"Note with \\"Escaped\\" Quotes and \\\\ Backslashes"',
        )
        self.assertEqual(parsed.fields["title"][1], 3)
        self.assertIn("type", parsed.fields)
        self.assertEqual(parsed.fields["type"][0], "project-note")
        self.assertEqual(parsed.body_content, "Content with ^d8b1a4\n")

    def test_closing_delimiter_dots(self):
        text = "---\n" 'title: "Document"\n' "...\n" "Body after dots\n"
        parsed = tokenize_frontmatter(text)

        self.assertTrue(parsed.has_frontmatter)
        self.assertTrue(parsed.is_closed)
        self.assertEqual(parsed.closing_line_number, 3)
        self.assertEqual(parsed.body_content, "Body after dots\n")

    def test_crlf_normalization(self):
        text = (
            '---\r\ntitle: "CRLF Note"\r\nstatus: active\r\n---\r\nLine 1\r\nLine 2\r\n'
        )
        parsed = tokenize_frontmatter(text)

        self.assertTrue(parsed.has_frontmatter)
        self.assertTrue(parsed.is_closed)
        self.assertEqual(parsed.closing_line_number, 4)
        self.assertEqual(parsed.fields["title"][0], '"CRLF Note"')
        self.assertEqual(parsed.body_content, "Line 1\nLine 2\n")

    def test_from_markdown(self):
        from abby.models.okf import OKFFrontmatter

        text = (
            "---\n"
            'title: "Markdown Note"\n'
            'created: "2026-09-17T10:00:00"\n'
            "type: project-note\n"
            "status: active\n"
            "tags:\n"
            "  - work\n"
            "  - dev\n"
            "---\n"
            "# Content\n"
        )
        fm = OKFFrontmatter.from_markdown(text)
        self.assertEqual(fm.title, "Markdown Note")
        self.assertEqual(fm.created, "2026-09-17T10:00:00")
        self.assertEqual(fm.type, "project-note")
        self.assertEqual(fm.status, "active")
        self.assertEqual(fm.tags, ["work", "dev"])

        no_fm = OKFFrontmatter.from_markdown(
            "Just body", default_title="Fallback Title"
        )
        self.assertEqual(no_fm.title, "Fallback Title")
        self.assertEqual(no_fm.type, "inbox")
        self.assertEqual(no_fm.status, "unprocessed")


if __name__ == "__main__":
    unittest.main()
