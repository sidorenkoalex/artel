"""Юнит-тесты разбора `approve --no-answer`/`answer <id> <файл>` и записи о
снятии эскалации без ответа (SPEC 01M44ENW1B73Z80PR73HP1C9CG) — углы, не
покрытые долгоживущим файлом задачи
`tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`.
"""
import contextlib
import io
import os
import sys
import unittest
from unittest import mock

from orchestrator import artel, config, fsm, store
from tests.sandbox import LightTransitionSandbox

SHA = "a" * 40
TASK_ID = "T001"


class ApproveArgsTest(unittest.TestCase):

    def test_sha_is_kept_next_to_no_answer_flag(self):
        """`approve <id> <sha> --no-answer` и `approve <id> --no-answer <sha>` — sha тот же, флаг распознан.

        Ловит мутацию: `_approve_sha_arg` не пропускает `--no-answer` —
        во второй форме sha становится «--no-answer»; `_approve_no_answer_
        arg` смотрит только на последний аргумент — первая форма с флагом
        не в конце теряет флаг.
        """
        for rest in ([TASK_ID, SHA, "--no-answer"], [TASK_ID, "--no-answer", SHA]):
            with self.subTest(rest=rest):
                self.assertEqual(SHA, artel._approve_sha_arg(rest))
                self.assertTrue(artel._approve_no_answer_arg(rest))

    def test_reason_text_equal_to_flag_is_not_the_flag(self):
        """Основание `--accept-red`, совпавшее с текстом «--no-answer», флагом не считается.

        Ловит мутацию: `_approve_no_answer_arg` — голое `"--no-answer" in
        rest` без пропуска позиций оснований флагов: основание включает
        снятие эскалации без ответа.
        """
        rest = [TASK_ID, "--accept-red", "--no-answer"]
        self.assertFalse(artel._approve_no_answer_arg(rest))
        self.assertIsNone(artel._approve_sha_arg(rest))


class AnswerArgsTest(unittest.TestCase):

    def test_directory_instead_of_file_is_refused(self):
        """`answer <id> <каталог>` — отказ «файла ответа нет» с синтаксисом, как для несуществующего пути.

        Ловит мутацию: проверка файла — `Path.exists()` вместо
        `is_file()`: каталог проходит разбор и падает уже в чтении файла
        под lease.
        """
        with self.assertRaises(SystemExit) as cm:
            artel._answer_args([TASK_ID, os.getcwd()])
        text = str(cm.exception.code)
        self.assertIn("файла ответа нет", text)
        self.assertIn(f"artel.py answer {TASK_ID} <файл-с-ответом>", text)


class NoAnswerFlagOnPlainEscalationTest(LightTransitionSandbox):

    def setUp(self):
        super().setUp()
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        env.start()
        self.addCleanup(env.stop)

    def journal(self, actor: str, action: str, detail: str = "") -> None:
        store.journal(store.db(), self.TASK, actor, action, detail)

    def approve(self, *flags: str) -> str:
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["artel.py", "approve", self.TASK, *flags]), \
                contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            artel.main()
        return buf.getvalue()

    def test_flag_on_escalation_without_marker_writes_no_cleared_record(self):
        """Флаг на эскалации без метки «нужен шаг роли» — прежний возврат без записи «эскалация снята без ответа».

        Ловит мутацию: запись о снятии без ответа пишется на любой
        `approve --no-answer` из `escalated` — журнал утверждает, что
        ответ был нужен, где его не требовалось.
        """
        store.update_task(store.db(), self.TASK, state="escalated",
                          escalated_from="in_dev")
        self.journal("fsm", "state -> escalated", "агент упал после всех попыток")

        out = self.approve(fsm.NO_ANSWER_FLAG)

        self.assertEqual("in_dev", store.get_task(store.db(), self.TASK)["state"], out)
        actions = [r["action"] for r in store.task_steps(store.db(), self.TASK)]
        self.assertNotIn(fsm.ESCALATION_CLEARED_WITHOUT_ANSWER_ACTION, actions)

    def test_marker_detail_is_taken_from_last_escalation(self):
        """`unanswered_role_step_escalation` возвращает detail последней `state -> escalated`, не более ранней.

        Ловит мутацию: функция берёт первую запись эскалации журнала —
        запись о снятии без ответа несёт текст старой эскалации.
        """
        self.journal("fsm", "state -> escalated", "старая эскалация")
        self.journal("operator", "state -> in_dev", "эскалация разрешена, продолжаем")
        self.journal("fsm", "state -> escalated", "новая эскалация")
        self.journal("fsm", fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER, "новая эскалация")

        self.assertEqual("новая эскалация",
                         fsm.unanswered_role_step_escalation(store.db(), self.TASK))


if __name__ == "__main__":
    unittest.main()
