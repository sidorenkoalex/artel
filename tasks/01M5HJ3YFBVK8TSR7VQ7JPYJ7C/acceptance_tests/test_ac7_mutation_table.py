"""PLAN.md несёт таблицу «мутация → красные тесты» по М1–М8, каждая мутация отмечена прогнанной, код пульта в рабочей копии после откатов чист (AC-7).

Группа: разовый
Красен до реализации: PLAN.md пишет разработчик — до его шага `artifact_text("PLAN.md")` даёт `None`, таблицы мутаций нет.

PLAN.md читается из ссылки документов помощником пульта
(`artifact_text`), чистота кода — `git status --porcelain orchestrator/
scripts/` в корне рабочей копии. Ожидаемые красные тесты строк — по
требованию 6 SPEC: п. 1 (а) — AC-1, п. 1 (б)–(е) — AC-2, п. 2 — AC-3,
п. 3 — AC-4, п. 4 — AC-5 (методы `test_ac<n>_…` нового файла).
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, artifact_text  # noqa: E402

# Мутация → номер критерия, чьи тесты она обязана красить.
EXPECTED = {1: 2, 2: 2, 3: 3, 4: 4, 5: 5, 6: 2, 7: 3, 8: 1}
DONE = re.compile(r"прогнан|✓|✅|\bда\b", re.I)
NOT_DONE = re.compile(r"не\s+прогнан", re.I)


def mutation_rows(text: str) -> dict[int, list[str]]:
    """Строки таблиц Markdown, первая ячейка которых — `М<n>` (кириллица
    или латиница), по номеру мутации."""
    rows: dict[int, list[str]] = {}
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        m = re.match(r"^\**`?[МM](\d)\b", cells[0]) if cells else None
        if m:
            rows.setdefault(int(m.group(1)), []).append(line)
    return rows


class Ac7MutationTableTest(unittest.TestCase):

    def test_ac7_plan_has_run_mutation_table(self):
        """В PLAN.md строка таблицы на каждую мутацию М1–М8: названы красные тесты нужного критерия, мутация отмечена прогнанной.

        Сценарий: PLAN.md из ссылки документов; для каждой М<n> есть строка
        таблицы, начинающаяся ячейкой `М<n>`; в ней есть метод
        `test_ac<k>_…` критерия, который мутация обязана красить
        (требование 6), и отметка прогона («прогнана», «✓», «да»).

        Ловит мутацию: таблица без строки М6–М8 (мутации «выведены из кода»
        и не прогнаны); строка с красными тестами не того критерия; строка
        без отметки прогона.
        """
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md нет в ссылке документов")
        rows = mutation_rows(plan)
        for n, ac in sorted(EXPECTED.items()):
            with self.subTest(mutation=f"М{n}"):
                lines = rows.get(n, [])
                self.assertTrue(lines, f"нет строки таблицы М{n}")
                joined = "\n".join(lines)
                self.assertRegex(joined, rf"test_ac{ac}_\w+",
                                 f"М{n}: не названы тесты AC-{ac}: {joined}")
                self.assertRegex(joined, DONE, f"М{n} не отмечена прогнанной")
                self.assertNotRegex(joined, NOT_DONE, f"М{n} отмечена непрогнанной")

    def test_ac7_pult_code_clean_after_mutations(self):
        """После откатов мутаций `git status --porcelain orchestrator/ scripts/` в рабочей копии задачи пуст.

        Сценарий: `git status --porcelain orchestrator/ scripts/` в корне
        рабочей копии кода; вывод пуст. Вместе с таблицей PLAN.md тест
        краснеет до шага разработчика.

        Ловит мутацию: мутация не откачена — правка `orchestrator/amend.py`
        или `orchestrator/fsm.py` остаётся в рабочей копии.
        """
        self.assertIsNotNone(artifact_text("PLAN.md"),
                             "PLAN.md нет — мутации не прогонялись")
        res = subprocess.run(["git", "-C", CODE_ROOT, "status", "--porcelain",
                              "--", "orchestrator/", "scripts/"],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "", res.stdout)


if __name__ == "__main__":
    unittest.main()
