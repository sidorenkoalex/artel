"""AC-5: Заведение НОВОЙ задачи артели (`cmd_new` без `target` или с
`target=artel`) идёт тем же путём, что заведение задачи любого объявленного
target — прежний однобраншевый flow заведения (`_new_dogfood`) для новых
задач больше не вызывается.

Красен до реализации: `orchestrator/catalog.py::cmd_new` несёт буквально
`if target == config.DEFAULT_TARGET: _new_dogfood(...) else:
_new_external_artifact_branch(...)` (строки ~143-146) — `target=None`
дефолтится в `config.DEFAULT_TARGET` (строка 135, «artel»), поэтому
`cmd_new(title)` без `target=` сегодня ВСЕГДА идёт в `_new_dogfood`.
Тесты ниже заводят задачу без `target=` и с `target="artel"` и падают
именно потому, что сегодня обе заводят `tasks/<id>/` прямо в новой
кодовой ветке `task/<id>-slug` (однобраншевый флоу), а не в отдельной
артефактной ветке пульта `artifact/<id>` (`orchestrator/
artifact_branch.py::branch_name`), которую заводит generic-путь.
"""
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import artifact_branch, catalog, config, gitcmd, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

ARTEL_TARGETS_YAML = """targets:
  artel:
    forge: github
    url: https://example.invalid/artel
    base: main
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


class NewArtelTaskGoesThroughGenericFlowTest(RealGitSandbox):
    """`cmd_new` для артели (явно или по умолчанию) заводит `tasks/<id>/`
    в артефактной ветке пульта, не в новой кодовой ветке."""

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(ARTEL_TARGETS_YAML, encoding="utf-8")

    def branches_before(self) -> set:
        return set(gitcmd.list_branches() or [])

    def test_ac5_default_target_task_lands_on_artifact_branch_not_a_new_code_branch(self):
        """`cmd_new("Заголовок")` без `target=` (историческое умолчание —
        self/догфуд, `config.DEFAULT_TARGET`) кладёт `tasks/<id>/SPEC.md`
        в артефактную ветку `artifact/<id>`, а НЕ в новую кодовую ветку
        `task/<id>-...` (которую до этой задачи создавал `_new_dogfood`
        через `workspace.ensure`).

        Ловит мутацию: `target = target or config.DEFAULT_TARGET` в паре
        с непеределанным условием `if target ==
        config.DEFAULT_TARGET: _new_dogfood(...)` — тогда `tasks/<id>/`
        снова окажется в новой кодовой ветке, а `artifact/<id>` не
        появится вовсе.
        """
        before = self.branches_before()

        task_id = catalog.cmd_new("Задача артели по умолчанию")

        after = set(gitcmd.list_branches() or [])
        new_branches = after - before
        self.assertIn(artifact_branch.branch_name(task_id), new_branches,
                      f"артефактная ветка не заведена; новые ветки: {new_branches}")
        code_branch_candidates = [b for b in new_branches
                                  if b != artifact_branch.branch_name(task_id)]
        self.assertEqual(code_branch_candidates, [],
                         f"cmd_new не должна заводить кодовую ветку сама: "
                         f"{code_branch_candidates}")
        artifact_files = gitcmd.ls_tree_files(
            artifact_branch.branch_name(task_id), f"tasks/{task_id}") or []
        self.assertTrue(any(f.endswith("SPEC.md") for f in artifact_files),
                        f"SPEC.md не найден в артефактной ветке: {artifact_files}")

    def test_ac5_explicit_target_artel_lands_on_artifact_branch_too(self):
        """`cmd_new("Заголовок", target="artel")` (явное имя, не умолчание)
        — та же генерик-логика, тот же исход, что и вызов без `target=`
        вовсе: явное указание не должно давать иной результат, чем
        умолчание, раз оба означают одно и то же target-имя.
        """
        before = self.branches_before()

        task_id = catalog.cmd_new("Задача артели явным target",
                                  target=config.DEFAULT_TARGET)

        after = set(gitcmd.list_branches() or [])
        new_branches = after - before
        self.assertEqual(new_branches, {artifact_branch.branch_name(task_id)})

    def test_ac5_root_worktree_stays_on_main_and_unchanged(self):
        """Заведение задачи артели не трогает рабочее дерево `config.ROOT`
        (по-прежнему на `main`, без новых файлов) — свойство generic-пути
        (`_new_external_artifact_branch`, требование 4 SPEC), которое
        `_new_dogfood` сегодня НЕ соблюдает (создаёт и чекаутит worktree
        новой кодовой ветки).

        Ловит мутацию: любую реализацию, которая для артели по-прежнему
        зовёт `workspace.ensure`/чекаутит новую ветку в рабочем дереве
        пульта — тогда список файлов `git status --porcelain` внутри
        `self.root` перестанет быть пустым, либо появится untracked
        worktree-каталог.
        """
        before_branch = self.git("rev-parse", "--abbrev-ref", "HEAD").strip()
        before_status = self.git("status", "--porcelain")

        catalog.cmd_new("Задача не трогает main")

        after_branch = self.git("rev-parse", "--abbrev-ref", "HEAD").strip()
        after_status = self.git("status", "--porcelain")
        self.assertEqual(before_branch, after_branch)
        self.assertEqual(before_status, after_status)

    def test_ac5_task_row_target_column_is_still_artel(self):
        """Контроль: строка БД заведённой задачи по-прежнему несёт
        `target="artel"` (`config.DEFAULT_TARGET`) — generic-путь не
        меняет ЗНАЧЕНИЕ target в БД, только КОД, которым заводится
        задача (требование 2 SPEC, дефолт схемы `store.py` не меняется —
        AC-6)."""
        task_id = catalog.cmd_new("Задача, target в БД")

        row = store.get_task(store.db(), task_id)

        self.assertEqual(row["target"], config.DEFAULT_TARGET)


if __name__ == "__main__":
    unittest.main()
