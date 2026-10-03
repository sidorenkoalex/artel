"""AC-5 (вторая половина): кодовая ветка задачи меняет только `docs/codebase-map.md`.

Группа: разовый
Зелёный с рождения: ветка задачи на старте не отличается от базы — свойство «ничего, кроме карты» держится, пока разработчик не тронет что-то вне неё.

Дифф ветки считается от точки расхождения с `origin/<основная ветка>`
(`gitcmd.diff_base`), вместе с незакоммиченными и неотслеживаемыми
файлами рабочей копии; выкладка самой планки (`tasks/<id>/`, её кладёт
прогон) в дифф не входит.
"""
import unittest

from orchestrator import gitcmd

TASK_ID = "01M41VH0Z3CQ0WY039SV1ERGMB"
ALLOWED = {"docs/codebase-map.md"}


class BranchScopeTest(unittest.TestCase):

    def test_ac5_branch_changes_nothing_but_codebase_map(self):
        """Ветка задачи относительно базы меняет не больше чем карту кода.

        Сценарий: база — `gitcmd.diff_base("HEAD")`; собираются пути,
        отличающиеся в рабочей копии от базы (`git diff --name-only`), и
        неотслеживаемые файлы; выкладка планки `tasks/<id>/` исключается;
        всё остальное обязано входить в {`docs/codebase-map.md`}.

        Ловит мутацию: разработчик вместо приложения правит
        `skills/spec-authoring.md` прямо в ветке или добавляет сторож
        отдельным файлом `tests/` — путь появляется в диффе ветки.
        """
        base = gitcmd.diff_base("HEAD")
        self.assertIsNotNone(base, "git не назвал базу ветки задачи")
        changed = gitcmd.git("diff", "--name-only", base)
        self.assertEqual(0, changed.returncode, changed.stderr)
        untracked = gitcmd.git("ls-files", "--others", "--exclude-standard")
        self.assertEqual(0, untracked.returncode, untracked.stderr)
        paths = set(changed.stdout.split()) | set(untracked.stdout.split())
        own = f"tasks/{TASK_ID}/"
        extra = sorted(p for p in paths
                       if p not in ALLOWED and not p.startswith(own))
        self.assertEqual([], extra,
                         f"ветка задачи меняет пути вне {sorted(ALLOWED)} "
                         f"(база {base}): {extra}")


if __name__ == "__main__":
    unittest.main()
