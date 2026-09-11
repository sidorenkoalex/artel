"""Приёмочный тест AC-4 — 01M283NC4JJXK7QS68Y9ET8TBK.

Источник — tasks/01M283NC4JJXK7QS68Y9ET8TBK/SPEC.md, «Критерии приёмки»:

AC-4. Шаг роли `developer` с `rc=0` и чистым рабочим деревом (вне
`tasks/<id>/` изменений нет) — ни коммита этим механизмом, ни записи
журнала не появляется.

«Чистое» — вне `tasks/<id>/`: `role_cwd` материализует `PLAN.md`/
`REVIEW.md` в `tasks/<id>/` на КАЖДОМ шаге (`enter_in_dev`/`run_faked`),
и это неизбежное, легитимное содержимое каталога задачи не в счёт (оно
переносится в артефактную ветку отдельным механизмом, `commit_step_
artifacts`, не этой задачей) — сценарий ниже не пишет ничего вне
`tasks/<id>/` вообще.

Зелёный с рождения: до этой задачи новый механизм не существует —
`worktree_head()` не может измениться механизмом, которого нет, и
журнала действия «код закоммичен пультом за роль» тоже нет ни при каком
сценарии. Тест фиксирует это отсутствие эффекта как КРИТЕРИЙ (AC-4), а
не проверяет побочный продукт реализации AC-1 — он останется зелёным и
после реализации AC-1/AC-2/AC-3 ровно потому, что для чистого дерева
новый механизм обязан остаться no-op.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DeveloperWipCommitSandbox  # noqa: E402


class CleanTreeNoCommitNoJournalTest(DeveloperWipCommitSandbox):

    def test_ac4_clean_tree_outside_task_dir_makes_no_commit_and_no_journal(self):
        """Шаг `developer` завершается `rc=0`, вне `tasks/<id>/` роль
        ничего не меняла — код-ветка задачи не сдвигается новым
        механизмом, и запись журнала «код закоммичен пультом за роль»
        не появляется.

        Ловит мутацию: `_commit_worktree_change`/её аналог вызывается без
        предварительной проверки «реально есть что коммитить»
        (`git diff --cached --quiet`) — тогда `git commit` завёл бы
        ПУСТОЙ коммит только из-за материализованных `tasks/<id>/`
        артефактов (которые всё равно исключаются `exclude`), и HEAD
        кодовой ветки сдвинулся бы там, где AC-4 требует no-op.
        """
        self.enter_in_dev()
        self.ensure_worktree()
        before_sha = self.worktree_head()

        self.run_faked()

        self.assertEqual(
            self.worktree_head(), before_sha,
            "AC-4: чистое (вне tasks/<id>/) рабочее дерево не должно "
            "порождать код-коммит пульта")
        self.assertEqual(
            self.code_commit_journal_entries(), [],
            "AC-4: чистое рабочее дерево не должно оставлять запись "
            "журнала «код закоммичен пультом за роль»")


if __name__ == "__main__":
    import unittest
    unittest.main()
