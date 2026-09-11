"""Юнит-тесты `orchestrator/watch.py` (SPEC 01M1VBEKRN0GA029J98S0K2DAQ) —
регресс REVIEW.md итерации 1, замечание R1-F1: `_emit_alerts` фильтровал
новые алерты по ТЕКУЩЕЙ (пересчитанной в этой же итерации) динамической
выборке `--mine`/`--all`, а не по объединению выборки с уже известными
задачами, которое остальной цикл `cmd_watch` уже применяет для
`steps`/`STATE` (`watch.py:209`). Как только задача выходила из
динамической выборки (становилась терминальной либо меняла владельца),
любой алерт с её `target`, заведённый позже, пропадал из потока навсегда,
хотя `STATE=`/`steps` этой же задачи продолжали печататься. Приёмочные
тесты `tasks/01M1VBEKRN0GA029J98S0K2DAQ/acceptance_tests/test_watch.py`
залочены (T023, планка приёмки уже написана test_author) и этот сценарий
не покрывают — регресс живёт здесь, не там.

Классы `stops`/`ci`, фильтр pre-advance отказов из `refusals`, отказ
пустой выборки и `--exit-on`/`--once` (SPEC 01M290PP4KBTG1KYS1PWKQJH6T) —
тоже здесь, независимо от `tasks/01M290PP4KBTG1KYS1PWKQJH6T/
acceptance_tests/`: та планка — гейт приёмки задачи, не часть `tests/`,
которую CI гоняет на каждый пуш ветки (`.github/workflows/ci.yml`).
"""
import os
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, store, watch  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class _WatchStream:
    """Потокобезопасный приёмник stdout фонового потока `watch`."""

    def __init__(self):
        self._chunks = []
        self._lock = threading.Lock()

    def write(self, s):
        with self._lock:
            self._chunks.append(s)

    def flush(self):
        pass

    def getvalue(self) -> str:
        with self._lock:
            return "".join(self._chunks)


class _WatchThreadTestCase(TmpRootTest):
    """Общая обвязка фонового потока `watch.cmd_watch` — тот же приём,
    что и приёмочная песочница этой задачи (`tasks/
    01M290PP4KBTG1KYS1PWKQJH6T/acceptance_tests/_sandbox.py`), отдельная
    копия: живёт в `tests/`, не в `tasks/<id>/` (залоченная планка не
    трогается, а `tests/` не имеет права зависеть от каталога задачи)."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self._stream = _WatchStream()
        self._thread = None
        self._watch_outcome = {}

    def _insert_task(self, task_id: str, state: str = "in_dev") -> None:
        store.insert_task(
            store.db(), task_id, f"Задача {task_id}", state,
            f"task/{task_id.lower()}", config.DEFAULT_TARGET, 25.0)

    def _set_state(self, task_id: str, new_state: str, expected: str) -> None:
        store.set_state(store.db(), task_id, new_state, "operator",
                        expected_state=expected)

    def _start(self, argv: list) -> None:
        def worker():
            old_stdout = sys.stdout
            sys.stdout = self._stream
            try:
                watch.cmd_watch(argv)
                self._watch_outcome["exit_code"] = 0
                self._watch_outcome["exit_message"] = None
            except SystemExit as exc:
                self._watch_outcome["exit_code"] = 0 if exc.code in (None, 0) else 1
                self._watch_outcome["exit_message"] = exc.code
            except BaseException as exc:  # noqa: BLE001 — диагностика падения
                self._watch_outcome["exception"] = exc
            finally:
                sys.stdout = old_stdout

        self._thread = threading.Thread(target=worker, daemon=True)
        self.addCleanup(self._force_stop)
        self._thread.start()

    def _force_stop(self) -> None:
        thread = self._thread
        if thread is None or not thread.is_alive():
            return
        try:
            conn = store.db()
            conn.execute("UPDATE tasks SET state='killed'")
            conn.commit()
        except Exception:  # noqa: BLE001 — best-effort, тест уже упал
            pass
        thread.join(timeout=3.0)

    def _settle(self, seconds: float = 0.3) -> None:
        time.sleep(seconds)

    def _wait_until(self, predicate, timeout: float = 6.0,
                    interval: float = 0.02) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if "exception" in self._watch_outcome:
                self.fail(f"поток watch упал: {self._watch_outcome['exception']!r}")
            if predicate():
                return
            time.sleep(interval)
        self.fail(
            "условие не выполнено за отведённое время; вывод потока:\n"
            + self._stream.getvalue())

    def _join(self, timeout: float = 8.0) -> None:
        self._thread.join(timeout=timeout)
        self.assertFalse(self._thread.is_alive(),
                         "watch не завершился за отведённое время")


class AlertsSurviveDynamicSelectionDropTest(_WatchThreadTestCase):
    """`--all --events alerts`: задача покидает динамическую выборку
    (переходит в `done`), затем заводится алерт с её `target` — алерт
    обязан появиться в потоке несмотря на то, что задача уже не входит
    в текущую пересчитанную `--all`-выборку."""

    def test_alert_for_task_that_left_selection_still_prints(self):
        """W002 остаётся нетерминальной весь тест — держит цикл `watch`
        живым НА НЕСКОЛЬКО итераций ПОСЛЕ того, как W001 покинула
        `--all`-выборку: без второй незавершённой задачи `_should_stop`
        закрыл бы цикл в ТУ ЖЕ итерацию, где W001 стала `done`, и тест
        зависел бы от гонки «успел ли `_emit_alerts` увидеть алерт до
        выхода из цикла» — не от самого свойства R1-F1 (алерт, заведённый
        уже ПОСЛЕ того, как задача покинула выборку, обязан быть замечен
        на любой из ПОСЛЕДУЮЩИХ итераций, не только в момент ухода)."""
        conn = store.db()
        self._insert_task("W001")
        self._insert_task("W002")

        self._start(["--all", "--events", "alerts", "--interval", "0.3"])
        time.sleep(0.3)  # снимок базового known_alert_id ДО мутаций теста

        # W001 покидает динамическую `--all`-выборку (стала терминальной);
        # W002 остаётся — цикл продолжает опрашивать дальше.
        self._set_state("W001", "done", "in_dev")
        time.sleep(0.6)  # минимум одна полная итерация ПОСЛЕ ухода W001

        # Алерт заведён ПОСЛЕ выхода задачи из выборки — тот самый сценарий
        # R1-F1: без фикса курсор `_emit_alerts` больше никогда не сверял
        # бы `target` этой задачи.
        store.insert_alert(conn, "W001", "incident", "doctor",
                          "алерт-после-выхода-из-выборки")

        self._wait_until(
            lambda: "алерт-после-выхода-из-выборки" in self._stream.getvalue())

        self._set_state("W002", "done", "in_dev")
        self._join(timeout=5.0)
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


class StopsAndCiClassesTest(_WatchThreadTestCase):
    """SPEC 01M290PP4KBTG1KYS1PWKQJH6T, требования 1, AC-1..AC-3 — классы
    `stops`/`ci` независимо от `actor`/причины конкретного `stops`,
    независимо от подтипа `verifying`/`ре-ран` для `ci`, и с фильтром
    вердикта (только «не зелёный»)."""

    def test_stops_prints_regardless_of_actor_and_reason(self):
        conn = store.db()
        self._insert_task("S001")

        self._start(["--tasks", "S001", "--events", "stops", "--interval", "0.3"])
        self._settle()

        store.journal(conn, "S001", "operator", "auto остановлен",
                     "in_dev: причина-1")
        self._wait_until(lambda: "причина-1" in self._stream.getvalue())

        store.journal(conn, "S001", "fsm", "auto остановлен",
                     "review: причина-2")
        self._wait_until(lambda: "причина-2" in self._stream.getvalue())

        self._set_state("S001", "killed", "in_dev")
        self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)

    def test_ci_prints_only_the_non_green_verdict(self):
        conn = store.db()
        self._insert_task("S002")

        self._start(["--tasks", "S002", "--events", "ci", "--interval", "0.3"])
        self._settle()

        store.journal(conn, "S002", "orchestrator", "статус CI ветки (ре-ран)",
                     "CI коммита fff0001 зелёный (2 проверок)")
        store.journal(conn, "S002", "orchestrator", "статус CI ветки (verifying)",
                     "CI коммита fff0002 не зелёный: unit=failure")

        self._wait_until(
            lambda: "CI коммита fff0002 не зелёный" in self._stream.getvalue())
        self.assertNotIn("fff0001", self._stream.getvalue())

        self._set_state("S002", "killed", "in_dev")
        self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


class UnknownEventsMessageListsAllClassesTest(_WatchThreadTestCase):

    def test_unknown_class_message_names_stops_and_ci_among_available(self):
        self._insert_task("S003")
        with self.assertRaises(SystemExit) as cm:
            watch.cmd_watch(["--tasks", "S003", "--events", "made-up"])
        message = str(cm.exception)
        for name in ("stops", "ci", "transitions", "refusals", "gates",
                    "steps", "budget", "alerts"):
            self.assertIn(name, message)


class PreAdvanceRefusalsFilteredTest(_WatchThreadTestCase):
    """SPEC 01M290PP4KBTG1KYS1PWKQJH6T, требование 5, AC-8 — отказы
    `auto._pre_advance_step` («роль ещё не закончила») не печатаются
    классом `refusals`; отказ другого текста — печатается."""

    def test_pre_advance_texts_hidden_other_refusal_visible(self):
        conn = store.db()
        self._insert_task("S004")

        self._start(["--tasks", "S004", "--events", "refusals",
                    "--interval", "0.3"])
        self._settle()

        store.journal(conn, "S004", "fsm",
                     "переход отклонён: замечания ревью не отработаны",
                     "скрыт-1")
        store.journal(conn, "S004", "fsm",
                     "переход отклонён: дерево не на ветке задачи",
                     "скрыт-2")
        store.journal(conn, "S004", "fsm",
                     f"{store.REFUSAL_ACTION_PREFIX}: другое",
                     "виден")

        self._wait_until(lambda: "виден" in self._stream.getvalue())
        out = self._stream.getvalue()
        self.assertNotIn("скрыт-1", out)
        self.assertNotIn("скрыт-2", out)

        self._set_state("S004", "killed", "in_dev")
        self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


class ExitOnAndOnceTest(_WatchThreadTestCase):

    def test_exit_on_stops_immediately_after_matching_class(self):
        conn = store.db()
        self._insert_task("S005")

        self._start(["--tasks", "S005", "--exit-on", "refusals",
                    "--interval", "0.3"])
        self._settle()

        store.journal(conn, "S005", "fsm",
                     f"{store.REFUSAL_ACTION_PREFIX}: причина", "маркер")
        self._join(timeout=3.0)
        self.assertIn("маркер", self._stream.getvalue())
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)

    def test_once_exits_after_first_default_class_line(self):
        conn = store.db()
        self._insert_task("S006")

        self._start(["--tasks", "S006", "--once", "--interval", "0.3"])
        self._settle()

        store.journal(conn, "S006", "runner", "agent run started", "маркер")
        self._join(timeout=3.0)
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)

    def test_without_exit_on_a_printed_line_does_not_terminate(self):
        conn = store.db()
        self._insert_task("S007")

        self._start(["--tasks", "S007", "--interval", "0.3"])
        self._settle()

        store.journal(conn, "S007", "runner", "agent run started", "маркер")
        self._wait_until(lambda: "маркер" in self._stream.getvalue())
        self.assertTrue(self._thread.is_alive())

        self._set_state("S007", "killed", "in_dev")
        self._join()

    def test_once_and_exit_on_together_are_rejected(self):
        self._insert_task("S008")
        with self.assertRaises(SystemExit):
            watch.cmd_watch(["--tasks", "S008", "--once", "--exit-on", "refusals"])


class EmptySelectionRefusesTest(_WatchThreadTestCase):

    def test_empty_mine_refuses_named_and_nonzero(self):
        conn = store.db()
        self._insert_task("S009")
        store.journal(conn, "S009", "lease", "lease взят", "",
                     session_id="чужая-сессия")

        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "моя-сессия"}):
            with self.assertRaises(SystemExit) as cm:
                watch.cmd_watch(["--mine"])
        message = str(cm.exception)
        self.assertTrue(message.startswith(
            "watch --mine: у сессии моя-сессия нет живых задач "
            "(lease взят другой identity: "))
        self.assertIn("чужая-сессия", message)

    def test_unknown_tasks_id_refuses_not_silently(self):
        self._insert_task("S010")
        with self.assertRaises(SystemExit) as cm:
            watch.cmd_watch(["--tasks", "НЕТТАКОЙ"])
        message = str(cm.exception)
        self.assertTrue(message.strip())


if __name__ == "__main__":
    unittest.main()
