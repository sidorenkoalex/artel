"""AC-5 — 01M2DC6SQVSANMECXPDZJDP75D: `PLAN.md` несёт таблицу переносов
и описывает откат одним revert merge-коммита.

Источник — SPEC.md, «Критерии приёмки»:

AC-5. `PLAN.md` несёт таблицу переносов (файл/строка исходного
`setUp`/помощника/`PATCHED_ATTRS` → базовый класс `tests/sandbox.py`
или принятое решение по подмножеству) и описывает откат — revert
одного merge-коммита ветки задачи.

Критерий про СОДЕРЖАНИЕ документа: полнота и корректность самой таблицы
переносов (действительно ли КАЖДАЯ из групп дублей AC-1/подмножеств AC-2
в ней перечислена и правильно закрыта) — содержательное чтение диффа,
предмет ревью (тот же класс, что и `tasks/01M283NC4JJXK7QS68Y9ET8TBK/
acceptance_tests/test_ac6_coding_standards_skill_update.py` — формулировка
текста, не формализуемый факт). Механически проверяемая часть — САМ ФАКТ
присутствия таблицы и описания отката: их отсутствие в `PLAN.md` —
конкретный, воспроизводимый регресс (роль developer забыла или не
собиралась вовсе описывать перенос/откат), который эта планка ловит
без ревью по существу.

Красен до реализации: `tasks/<id>/PLAN.md` ещё не существует (создаёт
роль developer) — оба теста ниже падают на `assertIsNotNone(plan_text)`.
Стаб корректной реализации: временный `tasks/<id>/PLAN.md` на диске с
таблицей `|Откуда|Куда|` и фразой «Revert одного merge-коммита ветки
задачи в main» позеленил оба теста; версия без таблицы и без слов
revert/merge рядом красила оба теста обратно; стаб удалён без коммита.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402

TASK_ID = "01M2DC6SQVSANMECXPDZJDP75D"
PLAN_PATH = _util.REPO_ROOT / "tasks" / TASK_ID / "PLAN.md"

# Строка-разделитель markdown-таблицы: `|---|---|...|` (с опциональными
# `:` выравнивания) — надёжный признак «здесь таблица», не полагается на
# конкретные имена столбцов (их формулировка — свобода роли developer).
_TABLE_SEPARATOR_RE = re.compile(r"^\|(?:\s*:?-+:?\s*\|)+\s*$", re.MULTILINE)

# «Откат — revert одного merge-коммита»: слова «revert» и «merge»
# (регистронезависимо) в одном окне текста — не требует конкретной
# формулировки предложения.
_REVERT_RE = re.compile(r"revert", re.IGNORECASE)
_MERGE_RE = re.compile(r"merge", re.IGNORECASE)
_WINDOW = 200


class PlanCarriesTransferTableTest(unittest.TestCase):

    def test_ac5_plan_contains_a_markdown_table(self):
        """`PLAN.md` содержит хотя бы одну markdown-таблицу (строку
        `|---|...|`-разделителя).

        Ловит мутацию: роль developer пишет `PLAN.md` текстом без единой
        таблицы (например, списком буллетов вместо таблицы переносов) —
        `_TABLE_SEPARATOR_RE` не находит совпадений, `assertIsNotNone`
        красит тест.
        """
        text = _util.plan_text(TASK_ID)
        self.assertIsNotNone(
            text, f"{PLAN_PATH} ещё не создан ни в артефактной ветке, "
                  f"ни на диске — таблица переносов AC-5 — обязанность "
                  f"роли developer")
        match = _TABLE_SEPARATOR_RE.search(text)
        self.assertIsNotNone(
            match,
            f"{PLAN_PATH} не содержит markdown-таблицы (строки-разделителя "
            f"вида '|---|...|') — AC-5 требует таблицу переносов")


class PlanDescribesSingleMergeRevertRollbackTest(unittest.TestCase):

    def test_ac5_plan_describes_rollback_as_a_single_merge_commit_revert(self):
        """`PLAN.md` упоминает откат через revert merge-коммита — слова
        «revert» и «merge» встречаются в одном окне текста (не обязательно
        рядом дословно, но не в разных, никак не связанных разделах).

        Ловит мутацию: роль developer описывает откат КАК-ТО ИНАЧЕ (или
        не описывает вовсе) — либо слово «revert», либо слово «merge» не
        находится совсем, либо оба находятся, но ни разу не в одном
        окне — `assertTrue` красит тест.
        """
        text = _util.plan_text(TASK_ID)
        self.assertIsNotNone(
            text, f"{PLAN_PATH} ещё не создан ни в артефактной ветке, "
                  f"ни на диске — описание отката AC-5 — обязанность "
                  f"роли developer")

        found = False
        for m in _REVERT_RE.finditer(text):
            window = text[max(0, m.start() - _WINDOW): m.end() + _WINDOW]
            if _MERGE_RE.search(window):
                found = True
                break

        self.assertTrue(
            found,
            f"{PLAN_PATH} не описывает откат как revert merge-коммита — "
            f"AC-5 требует упоминания и 'revert', и 'merge' в одном месте "
            f"документа")


if __name__ == "__main__":
    unittest.main()
