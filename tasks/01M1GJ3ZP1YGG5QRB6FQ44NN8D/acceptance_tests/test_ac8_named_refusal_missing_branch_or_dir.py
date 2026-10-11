"""AC-8 (tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D/SPEC.md): «Ветки задачи нет,
либо на ней нет каталога acceptance_tests/ — команда завершается
именованным отказом, называющим отсутствующее (ветку либо каталог), а
не пустой/нулевой сводкой.»

Красен до реализации: `_sandbox.discover_dry_run_command_name()` падает
`AssertionError` — новой команды в таблице диспетчера ещё нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402

from _sandbox import DryRunSandbox  # noqa: E402

SPEC_ONLY = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: фикстура без acceptance_tests

## Критерии приёмки

AC-1. Критерий фикстуры.
"""

MISSING_BRANCH = "task/t900-does-not-exist-at-all"


class NamedRefusalTest(DryRunSandbox):

    def test_ac8_missing_branch_names_the_branch_not_an_empty_summary(self):
        """Задача зарегистрирована в БД с веткой, которая физически не
        существует в git (никогда не создавалась) — отказ обязан назвать
        отсутствующую ВЕТКУ, не выглядеть как «0 тестов, 0 маркеров».

        Ловит мутацию: код читает `git ls-tree`/`git show` на
        несуществующей ветке, получает пустой/None ответ и молча трактует
        его как «тестов нет» (тот же вырожденный случай, что легитимен у
        `acceptance.materialize_from_branch` для ДРУГОГО, гейтового
        сценария) — вместо честного отказа печатает сводку с нулями,
        неотличимую от задачи, где ветка ЕСТЬ, но acceptance_tests/ на
        ней действительно пуст.
        """
        self.seed_task(branch=MISSING_BRANCH)

        out = self.run_dry_run()

        self.assertIn(
            MISSING_BRANCH, out,
            "отказ не называет отсутствующую ветку по имени")

    def test_ac8_missing_directory_names_the_directory_not_an_empty_summary(self):
        """Ветка задачи существует и несёт SPEC.md, но НЕ несёт каталог
        acceptance_tests/ вовсе — отказ обязан назвать отсутствующий
        КАТАЛОГ, а не выглядеть как пройденная (пустая) трассируемость.
        """
        self._commit_spec_only(self.TASK, self.BRANCH)
        self.seed_task()

        out = self.run_dry_run()

        self.assertIn(
            "acceptance_tests", out,
            "отказ не называет отсутствующий каталог acceptance_tests/")

    def test_ac8_the_two_refusals_are_named_differently(self):
        """Отказ «нет ветки» и отказ «нет каталога на существующей
        ветке» — два РАЗНЫХ сценария из формулировки критерия («ветки
        задачи нет, ЛИБО на ней нет каталога») — обязаны давать разные,
        конкретно именующие проблему сообщения, не один общий шаблон
        «что-то не так» на оба случая.

        Ловит мутацию: обработчик сворачивает оба сценария (нет ветки /
        есть ветка без каталога) в одну общую ветку кода с одним и тем
        же текстом («приёмочные тесты не найдены») — тест сравнивает два
        сообщения по разным задачам и падает, если они совпали.
        """
        task_missing_branch = "T900"
        task_missing_dir = "T901"
        branch_missing_dir = "task/t901-no-acceptance-tests-dir"

        self.seed_task(task_id=task_missing_branch, branch=MISSING_BRANCH)
        self._commit_spec_only(task_missing_dir, branch_missing_dir)
        self.seed_task(task_id=task_missing_dir, branch=branch_missing_dir)

        refusal_no_branch = self.run_dry_run(task_id=task_missing_branch)
        refusal_no_dir = self.run_dry_run(task_id=task_missing_dir)

        self.assertNotEqual(
            refusal_no_branch, refusal_no_dir,
            "отказ «нет ветки» и отказ «нет каталога» дословно совпали — "
            "команда не различает, чего именно не хватает")

    def _commit_spec_only(self, task_id: str, branch: str) -> None:
        self.checkout(branch, create=not self._branch_exists_locally(branch))
        d = self.root / "tasks" / task_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "SPEC.md").write_text(SPEC_ONLY.format(task=task_id),
                                   encoding="utf-8")
        # `add "tasks/<id>"`, не `-A` — см. _sandbox.py::commit_fixture:
        # `-A` унесло бы untracked `.artel/state.db` в коммит фикстурной
        # ветки, и возврат на main удалил бы файл БД с диска.
        self.git("add", f"tasks/{task_id}")
        self.git("commit", "-q", "-m", "SPEC без acceptance_tests")
        self.checkout(config.MAIN_BRANCH)


if __name__ == "__main__":
    unittest.main()
