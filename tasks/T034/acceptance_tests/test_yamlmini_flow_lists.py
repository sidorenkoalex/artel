"""Приёмочные тесты T034: AC-1, AC-2 — потоковые списки yamlmini.

Источник — tasks/T034/SPEC.md, «Критерии приёмки», требование 1
(ревью T017): хвостовой комментарий, содержащий `]`, не должен ни
попадать в элементы списка, ни ломать корректный разбор (AC-1); а
вложенный потоковый список должен отказывать `YamlError`, а не
разбираться молча элементом-строкой (AC-2).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from orchestrator import yamlmini  # noqa: E402


class Ac1TrailingCommentWithBracketTest(unittest.TestCase):
    """AC-1: `]` внутри хвостового комментария не входит в разбор списка."""

    def test_ac1_bracket_inside_trailing_comment_is_not_parsed_as_list_content(self):
        text = "key: [a, b]  # см. функцию foo()]\n"

        result = yamlmini.mapping(text)

        self.assertEqual(result, {"key": ["a", "b"]})

    def test_ac1_well_formed_list_without_a_trailing_comment_still_parses(self):
        """Список без хвостового комментария разбирается, как и раньше."""
        text = "key: [a, b]\n"

        result = yamlmini.mapping(text)

        self.assertEqual(result, {"key": ["a", "b"]})


class Ac2NestedFlowListTest(unittest.TestCase):
    """AC-2: вложенный потоковый список — отказ `YamlError`, не строка."""

    def test_ac2_nested_flow_list_raises_yaml_error_not_a_string_element(self):
        text = "a: 1\nkey: [a, [b]]\n"

        with self.assertRaises(yamlmini.YamlError) as ctx:
            yamlmini.mapping(text)

        # Не должен был получиться словарь со строкой "[b]" элементом.
        self.assertNotIn("[b]", str(ctx.exception))

    def test_ac2_error_names_the_line_number(self):
        text = "a: 1\nkey: [a, [b]]\n"

        with self.assertRaises(yamlmini.YamlError) as ctx:
            yamlmini.mapping(text)

        self.assertIn("строка 2", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
