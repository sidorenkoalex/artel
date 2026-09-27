"""AC-5 — 01M3H3T8RKTVKTJJYEAGW19BPS: PLAN.md несёт таблицу переноса
шести функций с полями «имя», «откуда», «куда», «число строк» и
результаты смока до/после для вызовов `artel.py ci-rerun` без аргументов
и с несуществующим id.

PLAN.md читается ТОЛЬКО из артефактной ветки задачи
(`gitcmd.show(artifact_branch.branch_name(...), …)`): на прогоне планки
пультом рабочая копия несёт лишь `acceptance_tests/`, и чтение с диска
дало бы зелёный у автора и красный на гейте (скил test-authoring, класс
12.09).

Сами смоки здесь не переигрываются: `artel.py` отказывает инвариантом
T056 любому запуску из git-worktree (`_refuse_if_worktree`), то есть в
среде прогона планки — и в рабочем каталоге роли, и в каталоге гейта —
до разбора команды `ci-rerun` дело не доходит. Критерий и говорит о
СОДЕРЖИМОМ PLAN.md: результаты смока приводит тот, кто гонял его из
главной копии.

Красен до реализации: PLAN.md задачи ещё не существует (его пишет роль
developer) — `gitcmd.show` вернёт `None`, и оба метода падают на этом.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from orchestrator import artifact_branch, gitcmd  # noqa: E402

#: Поля таблицы переноса, названные критерием.
TABLE_FIELDS = ("имя", "откуда", "куда", "строк")
#: Приметы смока до/после, названные критерием.
SMOKE_MARKS = ("смок", "без аргументов", "несуществующ", "код выхода")


def _plan_text():
    """Текст PLAN.md задачи из артефактной ветки; `None` — файла там нет."""
    text, _reason = gitcmd.show(artifact_branch.branch_name(_util.TASK_ID),
                                f"tasks/{_util.TASK_ID}/PLAN.md")
    return text


def _table_rows(text: str) -> list:
    """Строки markdown-таблицы, чья шапка несёт все поля переноса."""
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        low = line.lower()
        if "|" not in low or not all(f in low for f in TABLE_FIELDS):
            continue
        rows = []
        for following in lines[idx + 1:]:
            if not following.strip().startswith("|"):
                break
            rows.append(following)
        return rows
    return []


class PlanCarriesTransferTableAndSmokeTest(unittest.TestCase):

    def setUp(self):
        self.plan = _plan_text()
        self.assertIsNotNone(
            self.plan,
            f"PLAN.md задачи не найден в артефактной ветке "
            f"{artifact_branch.branch_name(_util.TASK_ID)} — таблицу "
            f"переноса и смок пишет роль developer (AC-5)")

    def test_ac5_plan_holds_transfer_table_for_all_six_functions(self):
        """В PLAN.md есть таблица с полями «имя», «откуда», «куда»,
        «число строк», и в её строках названы все шесть перенесённых
        функций.

        Ловит мутацию: таблица приведена, но описывает только публичную
        `cmd_ci_rerun` (закрытые «и так понятно») — ревьюеру нечем
        сверить объём переноса; имя недостающей функции назовёт отказ.
        """
        rows = _table_rows(self.plan)
        self.assertTrue(
            rows,
            f"в PLAN.md нет таблицы переноса с полями {TABLE_FIELDS} "
            f"(AC-5)")
        body = "\n".join(rows)
        for name in _util.MOVED_FUNCTIONS:
            with self.subTest(name=name):
                self.assertIn(
                    name, body,
                    f"строка о функции {name} в таблице переноса PLAN.md "
                    f"отсутствует (AC-5)")

    def test_ac5_plan_reports_both_smoke_invocations_before_and_after(self):
        """PLAN.md называет оба смок-вызова (`ci-rerun` без аргументов и
        с несуществующим id) и их результат — вывод и код выхода до и
        после переноса.

        Ловит мутацию: смок сведён к одной строке «поведение не
        изменилось» без самих вызовов и кодов выхода — проверить
        утверждение по PLAN.md стало бы нечем; отсутствующая примета
        будет названа в отказе.
        """
        low = self.plan.lower()
        for mark in SMOKE_MARKS:
            with self.subTest(mark=mark):
                self.assertIn(
                    mark, low,
                    f"PLAN.md не говорит про «{mark}» — AC-5 требует "
                    f"результаты смока до/после для обоих вызовов")
        self.assertTrue(
            re.search(r"\bдо\b", low) and re.search(r"\bпосле\b", low),
            "PLAN.md не различает результаты смока «до» и «после» (AC-5)")


if __name__ == "__main__":
    unittest.main()
