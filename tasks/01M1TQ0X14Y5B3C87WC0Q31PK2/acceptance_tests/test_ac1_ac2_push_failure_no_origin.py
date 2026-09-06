"""Приёмочные тесты AC-1/AC-2 задачи 01M1TQ0X14Y5B3C87WC0Q31PK2: отказ push
артефактной ветки без `origin` пишет в журнал задачи классифицированную
запись «push артефактной ветки FAILED» на каждом реальном месте вызова
(автокоммит шага роли — `checkpoint.commit_step_artifacts`; `cmd_new`;
`answer.cmd_answer`), и для `cmd_new` это остаётся best-effort — заведение
задачи не отказывает.

Красен до реализации: `artifact_branch.push` сегодня (docstring
`orchestrator/artifact_branch.py`) возвращает `bool` без единой записи
журнала — три места вызова из четырёх, названных SPEC требованием 1
(автокоммит, `cmd_new`, ANSWER), не пишут вообще ничего при отказе push;
`answer.py::_cmd_answer` до этой задачи push не зовёт вовсе. Ни одна из
трёх проверок ниже не находит записи «push артефактной ветки FAILED» в
журнале — падают на `assertEqual(len(failed), 1, ...)` с пустым списком.

Песочница — `PultOriginSandbox` (`tests/01M1TQ0X14Y5B3C87WC0Q31PK2/
acceptance_tests/_sandbox.py`): пульт — настоящий git-репозиторий БЕЗ
`origin` (не вызываем `add_origin()`) — тот же вырожденный случай, что
уже опирается на него `catalog._new_external_artifact_branch`
(«Push best-effort... отказ не прерывает заведение задачи»).
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import answer, catalog, checkpoint, config, gitcmd, store  # noqa: E402
from tests.sandbox import capture_new_task_id  # noqa: E402
from _sandbox import PultOriginSandbox  # noqa: E402

FAILED_ACTION = "push артефактной ветки FAILED"


class CheckpointAutocommitPushFailureTest(PultOriginSandbox):
    """AC-1, место вызова «автокоммит шага» (`checkpoint.commit_step_
    artifacts`, используется и таймаут-/аварийным-/pause-чекпоинтами
    через общий `_commit_external_step_artifacts`)."""

    def setUp(self):
        super().setUp()
        self.TASK = "01ACPUSHCKPTNOORG01"
        self.task_dir = self.new_external_task(self.TASK)
        self.push_dir(self.task_dir, self.TASK, "PLAN.md", "план\n")

    def test_ac1_autocommit_journals_push_failure_classified_as_no_origin(self):
        """Автокоммит шага роли без `origin` пульта обязан оставить в
        журнале задачи РОВНО одну запись «push артефактной ветки FAILED»
        с причиной, классифицированной как «нет origin».

        Ловит мутацию: `checkpoint._commit_external_step_artifacts`
        продолжает звать `artifact_branch.push(task_id)` и игнорировать
        булев результат (сегодняшний код, `orchestrator/checkpoint.py:628`)
        — тест краснеет на пустом списке `failed`.
        """
        self.assertTrue(gitcmd.has_no_remote(self.root),
                        "проверка бессмысленна с настроенным origin")
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")

        rows = self.journal_rows(self.TASK)
        failed = [r for r in rows if r["action"] == FAILED_ACTION]
        self.assertEqual(len(failed), 1,
                         f"записи журнала задачи: {[dict(r) for r in rows]}")
        self.assertIn("нет origin", failed[0]["detail"])


class AnswerPushFailureTest(PultOriginSandbox):
    """AC-1, место вызова ANSWER Оператора (`answer.cmd_answer`)."""

    def setUp(self):
        super().setUp()
        self.TASK = "01ACPUSHANSWERNOOR1"
        store.insert_task(store.db(), self.TASK, "Задача на эскалации",
                          "escalated", f"task/{self.TASK.lower()}-x",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)

    def _answer_file(self, text: str) -> str:
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False,
                                        encoding="utf-8")
        self.addCleanup(lambda: Path(f.name).unlink(missing_ok=True))
        f.write(text)
        f.close()
        return f.name

    def test_ac1_answer_journals_push_failure_classified_as_no_origin(self):
        """`answer <id> <файл>` без `origin` пульта обязан оставить в
        журнале задачи запись «push артефактной ветки FAILED» с причиной
        «нет origin» — тем же принципом, что автокоммит шага.

        Ловит мутацию: `answer._cmd_answer` продолжает коммитить
        `ANSWER-n.md` (`orchestrator/answer.py:90`) и завершаться, вовсе
        не вызывая push — тест краснеет и на отсутствующей записи, и,
        отдельно, до этой задачи так и есть (не только гипотетическая
        мутация, а сегодняшнее поведение)."""
        answer.cmd_answer(self.TASK, self._answer_file("Ответ Оператора.\n"))

        rows = self.journal_rows(self.TASK)
        failed = [r for r in rows if r["action"] == FAILED_ACTION]
        self.assertEqual(len(failed), 1,
                         f"записи журнала задачи: {[dict(r) for r in rows]}")
        self.assertIn("нет origin", failed[0]["detail"])


class CmdNewPushFailureIsBestEffortTest(PultOriginSandbox):
    """AC-2: `cmd_new` без origin остаётся best-effort — заведение не
    отказывает, но запись в журнал по AC-1 всё равно делается."""

    def test_ac2_cmd_new_without_origin_creates_the_task_and_journals_the_failure(self):
        """`cmd_new` пульта без `origin` обязан (а) завести задачу как
        обычно и (б) записать в журнал «push артефактной ветки FAILED» с
        причиной «нет origin» — не тихий `return False`, как сегодня.

        Ловит мутацию: `catalog._new_external_artifact_branch` продолжает
        звать `artifact_branch.push(task_id)` и отбрасывать результат
        (`orchestrator/catalog.py:183`) — тест краснеет на пустом списке
        `failed`, при этом само заведение задачи (первая часть теста)
        уже сегодня проходит и просело бы отдельно, если бы мутация вместо
        этого сделала push блокирующим.
        """
        _out, task_id = capture_new_task_id(
            catalog.cmd_new, "Задача без origin пульта")

        task = store.get_task(store.db(), task_id)
        self.assertIsNotNone(
            task, "AC-2: отказ push не имеет права отменить заведение задачи")

        rows = self.journal_rows(task_id)
        failed = [r for r in rows if r["action"] == FAILED_ACTION]
        self.assertEqual(len(failed), 1,
                         f"записи журнала задачи: {[dict(r) for r in rows]}")
        self.assertIn("нет origin", failed[0]["detail"])


if __name__ == "__main__":
    unittest.main()
