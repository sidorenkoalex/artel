"""AC-8: таблица мутаций в PLAN.md по одной на разбиваемый метод; после мутаций `orchestrator/` чист.

Группа: разовый
Красен до реализации: PLAN.md с таблицей мутаций ещё нет; чистота `orchestrator/` зелена на базе и держит откат мутаций. Таблица PLAN стабом не проверяется: `artifact_text` читает ревизию ссылки документов.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _split as S  # noqa: E402
from _pult import changed_paths  # noqa: E402


def mutation_section(plan: str) -> str:
    """Текст разделов PLAN, заголовок которых говорит о мутациях."""
    out, inside = [], False
    for line in plan.splitlines():
        if line.startswith("#"):
            inside = bool(re.search(r"(?i)мутац", line))
        if inside:
            out.append(line)
    return "\n".join(out)


class MutationsTest(unittest.TestCase):

    def test_ac8_orchestrator_clean_after_mutations(self):
        """`git status --porcelain orchestrator/` рабочей копии пуст, в диффе задачи нет путей `orchestrator/`.

        Сценарий: после мутаций кода пульта в worktree задачи статус
        `orchestrator/` пуст, а пути задачи (`_pult.changed_paths`) не
        содержат `orchestrator/`.

        Ловит мутацию: мутация из таблицы не откачена — правка
        `orchestrator/…` в статусе рабочей копии или в коммите задачи.
        """
        status = subprocess.run(
            ["git", "-C", str(S.ROOT), "status", "--porcelain", "orchestrator/"],
            capture_output=True, text=True, encoding="utf-8", check=True).stdout
        self.assertEqual(status.strip(), "")
        self.assertEqual([p for p in changed_paths() if p.startswith("orchestrator/")], [])

    def test_ac8_plan_mutation_table_per_split_method(self):
        """Раздел мутаций PLAN.md несёт строку таблицы на каждый разбиваемый метод и команду проверки чистоты.

        Сценарий: в разделе PLAN.md, заголовок которого говорит о мутациях,
        есть строки таблицы (`|`), называющие каждый из двенадцати
        разбиваемых методов; PLAN называет `git status --porcelain
        orchestrator/`.

        Ловит мутацию: таблица мутаций покрывает только методы outcome_gate
        — методов `test_ac10_*` в ней нет.
        """
        plan = S.plan_text()
        section = mutation_section(plan)
        rows = "\n".join(line for line in section.splitlines()
                         if line.lstrip().startswith("|"))
        for _rel, old in S.ALL_SPLIT:
            with self.subTest(method=old):
                self.assertIn(old.split(S.SEP)[-1], rows)
        self.assertIn("git status --porcelain orchestrator/", plan)


if __name__ == "__main__":
    unittest.main()
