"""Приёмочный тест AC-3 задачи 01M1TQ0X14Y5B3C87WC0Q31PK2: при следующем
автокоммите той же задачи, если предыдущий push не прошёл, пульт
пробует push снова и журналирует исход повторной попытки.

Красен до реализации: `checkpoint._commit_external_step_artifacts`
сегодня зовёт `artifact_branch.push(task_id)` и отбрасывает булев
результат (`orchestrator/checkpoint.py:628`) — push технически
вызывается на каждом автокоммите уже сейчас (значит «повтор» физически
происходит), но НИЧЕГО не журналируется ни при первом отказе, ни при
успехе второй попытки: тест краснеет на первой же проверке — списке
записей журнала после первого автокоммита пуст там, где ожидается ровно
одна запись «push артефактной ветки FAILED».

Песочница — `PultOriginSandbox` (`_sandbox.py` рядом): первый автокоммит
идёт без `origin` (отказ «нет origin»), затем `origin` подключается
(`add_origin()`) — второй автокоммит обязан домести локальный ref до
origin и записать исход в журнал.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import artifact_branch, checkpoint, gitcmd, store  # noqa: E402
from _sandbox import PultOriginSandbox  # noqa: E402

FAILED_ACTION = "push артефактной ветки FAILED"


class RetryPushOnNextAutocommitTest(PultOriginSandbox):

    def setUp(self):
        super().setUp()
        self.TASK = "01ACPUSHRETRY000001"
        self.task_dir = self.new_external_task(self.TASK)
        self.branch = artifact_branch.branch_name(self.TASK)

    def _push_related_rows(self):
        rows = self.journal_rows(self.TASK)
        return [r for r in rows
               if "push" in r["action"].lower()
               or "push" in (r["detail"] or "").lower()]

    def test_ac3_second_autocommit_retries_and_journals_the_new_outcome(self):
        """Первый автокоммит без `origin` отказывает и журналируется
        (AC-1); `origin` затем становится доступен (симулирует «сеть
        восстановилась»/«Оператор подключил origin»); второй автокоммит
        той же задачи обязан САМ попробовать push снова — без ручного
        вмешательства — и в итоге домести артефактную ветку до origin, с
        новой записью в журнале про исход этой попытки.

        Ловит мутацию: реализация запоминает «push этой задачи уже
        проваливался» и БОЛЬШЕ НЕ ПРОБУЕТ push на последующих автокоммитах
        (over-engineered экономия вызовов git, которую SPEC явно не
        просит) — тогда после появления `origin` `origin_branch_sha`
        останется пустым, и вторая проверка теста упадёт.
        """
        self.assertTrue(gitcmd.has_no_remote(self.root))
        self.push_dir(self.task_dir, self.TASK, "PLAN.md", "план\n")
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")

        first_failed = [r for r in self.journal_rows(self.TASK)
                        if r["action"] == FAILED_ACTION]
        self.assertEqual(len(first_failed), 1,
                         "предусловие теста: первый push обязан отказать "
                         "и попасть в журнал (AC-1) — без этого сценарий "
                         "«повтор после отказа» не воспроизведён")
        rows_before_retry = self._push_related_rows()

        self.add_origin()
        self.task_dir.mkdir(parents=True)
        self.push_dir(self.task_dir, self.TASK, "REVIEW.md", "ревью\n")
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "reviewer")

        local_sha = gitcmd.branch_head_sha(self.branch)
        self.assertTrue(local_sha)
        self.assertEqual(
            self.origin_branch_sha(self.branch), local_sha,
            "AC-3: повторная попытка push обязана домести артефактную "
            "ветку до origin — без ручного вмешательства")

        rows_after_retry = self._push_related_rows()
        self.assertGreater(
            len(rows_after_retry), len(rows_before_retry),
            "AC-3: исход повторной попытки (успех) обязан журналироваться "
            "отдельной записью — не молчать так же, как молчал бы сегодняшний "
            "код")


if __name__ == "__main__":
    unittest.main()
