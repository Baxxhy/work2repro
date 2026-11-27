import unittest

from solution import unescape


class UnescapeTests(unittest.TestCase):
    def test_each_listed_metacharacter_loses_its_backslash(self):
        for char in "{}()+-.*?^$[]\\":
            with self.subTest(char=char):
                self.assertEqual(unescape("A\\" + char + "B"), "A" + char + "B")

    def test_escaped_whitespace_keeps_the_whitespace_character(self):
        for char in (" ", "\t", "\n", "\r", "\f", "\v", "\u00a0", "\u2003"):
            with self.subTest(char=char):
                self.assertEqual(unescape("A\\" + char + "B"), "A" + char + "B")

    def test_unescaped_text_is_preserved(self):
        for text in ("", "plain text", "{}()+-.*?^$[]", "甲\t乙\n丙"):
            with self.subTest(text=text):
                self.assertEqual(unescape(text), text)

    def test_unlisted_escapes_are_preserved(self):
        self.assertEqual(unescape(r"\d\w\|\#\/"), r"\d\w\|\#\/")

    def test_trailing_backslash_is_preserved(self):
        self.assertEqual(unescape("\\"), "\\")
        self.assertEqual(unescape("end\\"), "end\\")

    def test_adjacent_escaped_and_unescaped_characters(self):
        self.assertEqual(unescape(r"^\(a\+b\)\.\d$"), r"^(a+b).\d$")

    def test_backslash_pairs_are_consumed_once(self):
        self.assertEqual(unescape(r"\\\."), r"\.")
        self.assertEqual(unescape(r"\\\\"), "\\\\")


if __name__ == "__main__":
    unittest.main()
