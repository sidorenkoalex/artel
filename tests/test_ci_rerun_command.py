"""Юнит-тесты команды `ci-rerun` (`orchestrator/fsm.py`, SPEC
01M3F7C2DVYCEANQ8CF1FCSD87).

Приёмочная планка задачи разыгрывает двенадцать критериев на живом
`ci.verifying_status`/`ci.trigger_rerun` с подменённым `gh`. Здесь — углы,
которых планка не касается, и три чистых узла команды по отдельности:

- разбор журнала (`_last_red_status_sha`, `_last_ci_rerun_reason`): какая
  именно запись читается, когда их в журнале несколько;
- таблица исходов ожидания (`_ci_rerun_outcome`) — все четыре ветки, в том
  числе «проверки идут», которой в планке нет;
- отказ на НЕПРОЧИТАННЫХ проверках ГОЛОВЫ ВЕТКИ (планка проверяет только
  сторону главной ветки) и отказ при отсутствии записи о красном CI вовсе.

Ни git, ни `gh`: `ci.*` подменены целиком.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import ci, fsm, store  # noqa: E402
from tests import sandbox  # noqa: E402

HEAD = "1111aaaa" + "0" * 32
OLD_HEAD = "9999cccc" + "0" * 32
MAIN_SHA = "2222bbbb" + "0" * 32
RUN_ID = "4242"
REASON = "флейк test_command_writes_nothing на прогоне push"


def red_note(sha: str) -> str:
    """`note` красного исхода в той форме, в которой её пишет
    `ci.verifying_status` (`short = sha[:8]`)."""
    return f"CI коммита {sha[:8]} не зелёный: python=failure"


class JournalReadsTest(unittest.TestCase):
    """`_last_red_status_sha`/`_last_ci_rerun_reason`: какую запись журнала
    читают требования 4 и 10. `store.task_steps` подменён списком словарей —
    доступ к полям у обеих функций строго по ключу, как у `sqlite3.Row`."""

    def steps(self, rows: list):
        return mock.patch.object(store, "task_steps", lambda conn, tid: rows)

    def test_last_red_status_record_wins_over_earlier_ones(self):
        """Берётся sha ПОСЛЕДНЕЙ красной записи, не первой.

        Ловит мутацию: журнал обходится с начала (или берётся первая
        найденная красная запись) — тогда после второго красного статуса на
        новой голове ветки сверка требования 4 сравнивала бы её с sha
        ПРОШЛОГО красного прогона и отказывала бы штатному повтору.
        """
        rows = [
            {"action": fsm.VERIFYING_STATUS_ACTION, "detail": red_note(OLD_HEAD)},
            {"action": "state -> in_dev", "detail": "возврат из verifying"},
            {"action": fsm.VERIFYING_STATUS_ACTION, "detail": red_note(HEAD)},
        ]
        with self.steps(rows):
            self.assertEqual(fsm._last_red_status_sha(None, "T001"), HEAD[:8])

    def test_non_red_status_records_are_skipped(self):
        """Зелёные/идущие записи того же action не считаются красными.

        Ловит мутацию: фильтр `ci.verifying_is_red` убран и берётся
        последняя запись статуса любого исхода — тогда после зелёного или
        ещё идущего опроса команда сверяла бы голову с коммитом, краснота
        которого не подтверждена, и повторяла бы прогон без основания.
        """
        rows = [
            {"action": fsm.VERIFYING_STATUS_ACTION, "detail": red_note(HEAD)},
            {"action": fsm.VERIFYING_STATUS_ACTION,
             "detail": f"CI коммита {OLD_HEAD[:8]} ещё идёт: python"},
        ]
        with self.steps(rows):
            self.assertEqual(fsm._last_red_status_sha(None, "T001"), HEAD[:8])

    def test_no_red_record_at_all_is_an_empty_sha(self):
        """Красной записи нет вовсе — пустой sha, не выдуманный.

        Ловит мутацию: отсутствие записи подменяется текущей головой ветки
        («сравним сам с собой») — сверка требования 4 превращалась бы в
        тавтологию и пропускала повтор по неактуальному статусу.
        """
        rows = [{"action": "state -> verifying", "detail": ""}]
        with self.steps(rows):
            self.assertEqual(fsm._last_red_status_sha(None, "T001"), "")

    def test_multiline_reason_is_recovered_verbatim(self):
        """Многострочное основание достаётся из записи дословно.

        Ловит мутацию: основание разбирается «первой строкой» detail —
        тогда многострочное основание сравнивалось бы обрезанным, и
        повторный вызов с ДРУГИМ продолжением того же первого абзаца
        ошибочно отказывал бы (или наоборот проходил бы с тем же).
        """
        reason = "флейк сети:\n  job python, шаг pip install\n  второй абзац"
        rows = [{"action": fsm.CI_RERUN_ACTION,
                 "detail": f"ре-ран прогона {RUN_ID} запущен; исход ожидания: "
                           f"нечто; {fsm.CI_RERUN_REASON_MARKER}{reason}"}]
        with self.steps(rows):
            self.assertEqual(fsm._last_ci_rerun_reason(None, "T001"), reason)

    def test_refusal_records_are_not_read_as_performed_reruns(self):
        """Запись ОТКАЗА основанием прошлого повтора не считается.

        Ловит мутацию: сверка требования 10 читает любую запись со словом
        `ci-rerun` (в том числе `CI_RERUN_REFUSED_ACTION`) — тогда отказ,
        случившийся с тем же основанием, навсегда блокировал бы повтор,
        который ни разу не состоялся.
        """
        rows = [{"action": fsm.CI_RERUN_REFUSED_ACTION,
                 "detail": f"задача в состоянии in_dev; "
                           f"{fsm.CI_RERUN_REASON_MARKER}{REASON}"}]
        with self.steps(rows):
            self.assertIsNone(fsm._last_ci_rerun_reason(None, "T001"))


class OutcomeTableTest(unittest.TestCase):
    """`_ci_rerun_outcome` — три исхода ожидания требования 8 и то, как
    команда узнаёт «повтор не запускался вовсе»."""

    def status(self, outcome: str, note: str):
        return mock.patch.object(ci, "verifying_status",
                                 lambda branch: (outcome, note))

    def test_not_started_rerun_never_reads_the_status(self):
        """Повтор не запущен — статус не перечитывается вовсе.

        Ловит мутацию: исход определяется перечитанным статусом без
        оглядки на `ci.rerun_started` — тогда «повтор не запущен» при
        по-прежнему красном CI журналировалось бы как «снова красный», то
        есть как состоявшаяся, но неудачная попытка.
        """
        calls = []

        def spy(branch):
            calls.append(branch)
            return ci.VERIFYING_RED, red_note(HEAD)

        with mock.patch.object(ci, "verifying_status", spy):
            text, answered = fsm._ci_rerun_outcome(
                "task/t001-x", f"ре-ран прогона {RUN_ID} не запущен: boom")

        self.assertEqual(calls, [])
        self.assertFalse(answered)
        self.assertIn(fsm.CI_RERUN_OUTCOME_UNKNOWN, text)

    def test_green_status_after_rerun_is_the_green_outcome(self):
        """Зелёный статус после повтора — исход «стал зелёным».

        Ловит мутацию: зелёный и красный исходы описаны одним текстом
        («повтор запущен») — Оператор не отличил бы в журнале погашенный
        флейк от повторного падения.
        """
        note = f"CI коммита {HEAD[:8]} зелёный (2 проверок)"
        with self.status(ci.VERIFYING_GREEN, note):
            text, answered = fsm._ci_rerun_outcome(
                "task/t001-x", f"ре-ран прогона {RUN_ID} запущен, ожидание")

        self.assertTrue(answered)
        self.assertIn(fsm.CI_RERUN_OUTCOME_GREEN, text)
        self.assertIn(note, text)

    def test_red_status_after_rerun_is_the_red_again_outcome(self):
        """Красный статус после повтора — исход «снова красный».

        Ловит мутацию: не-зелёный исход сворачивается в «`gh` не ответил» —
        подтверждённое повторное падение читалось бы как молчание CI, и
        Оператор ждал бы результата, который уже есть.
        """
        with self.status(ci.VERIFYING_RED, red_note(HEAD)):
            text, answered = fsm._ci_rerun_outcome(
                "task/t001-x", f"ре-ран прогона {RUN_ID} запущен, ожидание")

        self.assertTrue(answered)
        self.assertIn(fsm.CI_RERUN_OUTCOME_RED, text)

    def test_unknown_and_running_statuses_are_both_unanswered(self):
        """«Проверок нет» и «проверки идут» — исход неизвестен, не зелёный.

        Ловит мутацию: всё, что не красное, считается зелёным исходом —
        тогда молчание CI после повтора уходило бы в журнал успехом
        (нарушение инварианта 19 на новой поверхности).
        """
        for outcome in (ci.VERIFYING_NONE, ci.VERIFYING_RUNNING):
            with self.subTest(outcome=outcome):
                with self.status(outcome, "что-то неопределённое"):
                    text, answered = fsm._ci_rerun_outcome(
                        "task/t001-x",
                        f"ре-ран прогона {RUN_ID} запущен, ожидание")

                self.assertFalse(answered)
                self.assertIn(fsm.CI_RERUN_OUTCOME_UNKNOWN, text)


class CommandRefusalTest(sandbox.TaskSeededTmpRootTest):
    """Отказы команды на живой БД песочницы: `ci.*` подменены, состояние
    задачи и факт вызова `ci.trigger_rerun` наблюдаются напрямую."""

    BRANCH = "task/t001-zadacha"

    def setUp(self):
        super().setUp()
        conn = store.db()
        conn.execute("UPDATE tasks SET state='verifying' WHERE id=?",
                     (self.TASK,))
        conn.commit()

        self.trigger_calls: list = []
        self.branch_failed: tuple = ({"python"}, "")
        self.main_failed: tuple = ({"guard"}, "")

        def trigger(branch):
            self.trigger_calls.append(branch)
            return f"ре-ран прогона {RUN_ID} запущен, ожидание завершения: ок"

        def failed_names(sha):
            return self.branch_failed if sha == HEAD else self.main_failed

        for target, value in (
                ("verifying_status", lambda branch: (ci.VERIFYING_RED,
                                                     red_note(HEAD))),
                ("head_sha", lambda branch, repo=None: (HEAD, "")),
                ("failed_check_names", failed_names),
                ("trigger_rerun", trigger)):
            patcher = mock.patch.object(ci, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(fsm, "_origin_main_sha",
                                   lambda *a, **kw: MAIN_SHA)
        patcher.start()
        self.addCleanup(patcher.stop)

    def journal_red_status(self, sha: str = HEAD) -> None:
        store.journal(store.db(), self.TASK, "orchestrator",
                      fsm.VERIFYING_STATUS_ACTION, red_note(sha))

    def state(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]

    def run_command(self, reason: str = REASON) -> str:
        """Всё, что команда сказала: stdout/stderr плюс текст именованного
        отказа. Любое другое исключение проходит наружу и валит тест."""
        try:
            return self.capture(fsm.cmd_ci_rerun, self.TASK, reason)
        except SystemExit as exc:
            return str(exc)

    def test_missing_red_status_record_refuses_instead_of_rerunning(self):
        """Записи о красном CI в журнале нет — отказ, не повтор.

        Живой сценарий: задачу поставили в `verifying` без прошедшего
        опроса CI (ручной `advance` ещё не был). Сверять голову ветки не с
        чем, и повторять нечего.

        Ловит мутацию: отсутствие записи трактуется как «сверка пройдена»
        (пустой sha сравнивается с головой как совпадение) — команда
        перезапускала бы прогон, красноту которого пульт не наблюдал.
        """
        text = self.run_command()

        self.assertEqual(self.trigger_calls, [])
        self.assertIn(fsm.VERIFYING_STATUS_ACTION, text)
        self.assertEqual(self.state(), "verifying")

    def test_unreadable_branch_job_names_refuse_instead_of_rerunning(self):
        """Имена упавших заданий ГОЛОВЫ ВЕТКИ не прочитаны — отказ.

        Ловит мутацию: непрочитанные проверки головы ветки подменяются
        пустым множеством имён — пересечение с главной веткой оказалось бы
        пустым всегда, и сверка требования 5 пропускала бы повтор поверх
        дефекта main (планка проверяет только сторону главной ветки).
        """
        self.journal_red_status()
        self.branch_failed = (None, "gh не ответил: HTTP 503")

        text = self.run_command()

        self.assertEqual(self.trigger_calls, [])
        self.assertIn("HTTP 503", text)
        self.assertEqual(self.state(), "verifying")

    def test_happy_path_journals_reason_run_id_and_outcome_once(self):
        """Штатный путь: один повтор и одна запись с тремя величинами.

        Ловит мутацию: запись журнала собирается без основания либо без id
        прогона (или пишется под тем же action, что отказ) — Оператор не
        восстановил бы по журналу ни причину повтора, ни то, какой прогон
        перезапущен, а сверка требования 10 читала бы чужую запись.
        """
        self.journal_red_status()
        before = len(store.task_steps(store.db(), self.TASK))

        self.run_command()

        rows = store.task_steps(store.db(), self.TASK)[before:]
        records = [r for r in rows if r["action"] == fsm.CI_RERUN_ACTION]
        self.assertEqual(self.trigger_calls, [self.BRANCH])
        self.assertEqual(len(records), 1)
        self.assertIn(REASON, records[0]["detail"])
        self.assertIn(RUN_ID, records[0]["detail"])
        self.assertIn(fsm.CI_RERUN_OUTCOME_RED, records[0]["detail"])
        self.assertEqual(self.state(), "verifying")

    def test_second_rerun_with_the_same_reason_never_touches_gh(self):
        """Повтор с тем же основанием отказывает ДО обращения к `ci`.

        Ловит мутацию: сверка требования 10 стоит после опроса статуса и
        повтора — команда успевала бы перезапустить прогон второй раз по
        уже исполненному решению Оператора, то есть стать кнопкой «жать до
        зелёного».
        """
        self.journal_red_status()
        self.run_command()
        self.assertEqual(self.trigger_calls, [self.BRANCH])

        with mock.patch.object(
                ci, "verifying_status",
                mock.Mock(side_effect=AssertionError("статус CI не должен "
                                                     "опрашиваться"))):
            text = self.run_command()

        self.assertEqual(self.trigger_calls, [self.BRANCH])
        self.assertIn("основание", text)
        self.assertEqual(self.state(), "verifying")


if __name__ == "__main__":
    unittest.main()
