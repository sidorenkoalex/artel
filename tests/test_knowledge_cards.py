"""Карточки знаний: свойства сверх долгоживущих файлов задачи
01M4S0JVB85W9TY1ESGNBH97FP — строка отказа для вывода `doc-commit`,
отступ глубже поля, допуск пути `doc-commit`.
"""
import unittest

from orchestrator import knowledge_cards as kc
from orchestrator import notes


class RefusalTextTest(unittest.TestCase):

    def test_refusal_text_names_place_code_and_detail(self):
        """Строка отказа называет файл, карточку, поле, строку, код и
        подробность — её печатает `doc-commit`, где поля записи не видны.

        Ловит мутацию: `refusal_text` теряет номер строки или поле — в
        строке нет «строка 4» либо «поле rule».
        """
        text = "cards:\n  a:\n    where: [a.py]\n    rule: \"\"\n    why: w\n"
        refusal = kc.check_text(text, "knowledge/x.yaml", kc.SYSTEM)
        self.assertIsInstance(refusal, kc.Refusal)
        line = kc.refusal_text(refusal)
        for part in ("knowledge/x.yaml", "карточка a", "поле rule",
                     "строка 4", kc.FIELD_FORM, refusal.detail):
            self.assertIn(part, line)


class DeepIndentTest(unittest.TestCase):

    def test_indent_deeper_than_field_refused(self):
        """Строка на отступе 6 (вложенное отображение под полем) — отказ
        «поле не по форме» с подробностью «отступ» и номером строки.

        Ловит мутацию: проход принимает любой отступ больше 4 как
        продолжение поля — вложенное отображение `where` уходит в проверку
        значения и отказ называет не отступ.
        """
        text = ("cards:\n  a:\n    where:\n      x: a.py\n    rule: r\n"
                "    why: w\n")
        refusal = kc.check_text(text, "f.yaml", kc.PROJECT)
        self.assertIsInstance(refusal, kc.Refusal)
        self.assertEqual(refusal.code, kc.FIELD_FORM)
        self.assertIn("отступ", refusal.detail)
        self.assertEqual(refusal.line, 4)


class DocCommitPathTest(unittest.TestCase):

    def test_knowledge_path_admitted_with_own_prefix(self):
        """`knowledge/<имя>.yaml` проходит допуск пути `doc-commit` с
        префиксом `knowledge`; скрытое имя, вложенный уровень и иной
        суффикс — отказ «код и артефакты».

        Ловит мутацию: допуск — префикс `knowledge/` без формы имени
        (`knowledge/.yaml` или `knowledge/a/b.yaml` принят) либо префикс
        коммита `config` для карточек.
        """
        self.assertIsNone(notes._doc_commit_path_refusal("knowledge/system.yaml"))
        self.assertEqual(notes._doc_commit_prefix("knowledge/system.yaml"),
                         "knowledge")
        for rel in ("knowledge/.yaml", "knowledge/a/b.yaml", "knowledge/x.yml",
                    "knowledge/", "knowledge"):
            refusal = notes._doc_commit_path_refusal(rel)
            self.assertIsNotNone(refusal, rel)
            self.assertIn(notes.DOC_COMMIT_FOREIGN_REFUSAL, refusal, rel)


if __name__ == "__main__":
    unittest.main()
