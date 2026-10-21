"""Тексты действий гейта неослабления по исходам на мерже — один источник `refusal_classes`.

Группа: долгоживущий

Красен до реализации: в `refusal_classes` нет `OUTCOME_MERGE_PREPARE_ACTION` (AC-11 и AC-12 падают на атрибуте), а `outcome_integrity.py` держит оба текста действий своими литералами (AC-12); отсутствие импортов пакета в `refusal_classes` — существующее свойство.

Свойство — константы модулей и текст их исходников: без песочницы, git и
сети. Текст модуля читается по `__file__` импортированного модуля,
строковые константы — разбором `ast` (смежные литералы, разбитые по
строкам, `ast` склеивает в одну константу).
"""
import ast
import unittest
from pathlib import Path

from orchestrator.advance_gates import outcome_integrity, refusal_classes

PREPARE_TEXT = "merge отклонён: гейт неослабления по исходам — подготовка"


def source(module) -> str:
    return Path(module.__file__).read_text(encoding="utf-8")


def string_constants(text: str) -> list:
    return [node.value for node in ast.walk(ast.parse(text))
            if isinstance(node, ast.Constant) and isinstance(node.value, str)]


class OutcomeMergeActionTextsTest(unittest.TestCase):

    def test_ac11_prepare_action_is_operator_class(self):
        """`refusal_classes.OUTCOME_MERGE_PREPARE_ACTION` — текст действия подготовки гейта на мерже, его класс в `REFUSAL_CLASSES` — «чинит Оператор».

        Сценарий: константа равна тексту критерия; запись перечня по этому
        ключу — `OPERATOR_FIXES` («чинит Оператор»).

        Ловит мутацию: отказ подготовки отнесён к «чинит роль» — цикл
        `auto` жжёт шаг роли на сбое окружения; ключ записан иным текстом
        (без «— подготовка», с другим тире) и перечень его не узнаёт.
        """
        self.assertEqual(refusal_classes.OUTCOME_MERGE_PREPARE_ACTION,
                         PREPARE_TEXT)
        self.assertEqual(refusal_classes.REFUSAL_CLASSES[
            refusal_classes.OUTCOME_MERGE_PREPARE_ACTION],
            refusal_classes.OPERATOR_FIXES)
        self.assertEqual(refusal_classes.OPERATOR_FIXES, "чинит Оператор")

    def test_ac12_outcome_integrity_takes_texts_from_refusal_classes(self):
        """Действия мержа `outcome_integrity` равны константам `refusal_classes`, литералов обоих текстов в `outcome_integrity.py` нет, `refusal_classes` без импортов пакета.

        Сценарий: `MERGE_REFUSAL_ACTION`/`MERGE_PREPARE_ACTION` равны
        `OUTCOME_MERGE_REFUSAL_ACTION`/`OUTCOME_MERGE_PREPARE_ACTION`;
        ни одна строка текста `outcome_integrity.py` и ни одна его
        строковая константа не несут ни одного из двух текстов; в
        `refusal_classes.py` нет ни относительного импорта, ни импорта
        модуля `orchestrator…`.

        Ловит мутацию: `outcome_integrity` оставил свою копию литерала
        (тексты разойдутся при правке одного из них, класс отказа мержа
        потеряется); литерал разбит на две строки исходника (текстовая
        сверка его не видит, `ast` видит); `refusal_classes` импортирует
        `outcome_integrity` ради текста — модуль перестаёт быть листом
        графа импортов (`brief`/`watch` получают цикл).
        """
        self.assertEqual(outcome_integrity.MERGE_REFUSAL_ACTION,
                         refusal_classes.OUTCOME_MERGE_REFUSAL_ACTION)
        self.assertEqual(outcome_integrity.MERGE_PREPARE_ACTION,
                         refusal_classes.OUTCOME_MERGE_PREPARE_ACTION)
        text = source(outcome_integrity)
        for literal in (refusal_classes.OUTCOME_MERGE_REFUSAL_ACTION,
                        PREPARE_TEXT):
            with self.subTest(literal=literal):
                lines = [n for n, line in enumerate(text.splitlines(), 1)
                         if literal in line]
                self.assertEqual(lines, [], "литерал в тексте модуля")
                self.assertEqual([s for s in string_constants(text)
                                  if literal in s], [],
                                 "литерал — строковая константа модуля")
        imports = []
        for node in ast.walk(ast.parse(source(refusal_classes))):
            if isinstance(node, ast.ImportFrom) and (
                    node.level or (node.module or "").split(".")[0]
                    == "orchestrator"):
                imports.append(ast.dump(node))
            elif isinstance(node, ast.Import) and any(
                    alias.name.split(".")[0] == "orchestrator"
                    for alias in node.names):
                imports.append(ast.dump(node))
        self.assertEqual(imports, [], "refusal_classes импортирует пакет")


if __name__ == "__main__":
    unittest.main()
