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
"""
import sys
import threading
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import store, watch  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class _WatchStream:
    """Потокобезопасный приёмник stdout фонового потока `watch` — тот же
    приём, что `_Stream` приёмочных тестов этой задачи."""

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


class AlertsSurviveDynamicSelectionDropTest(TmpRootTest):
    """`--all --events alerts`: задача покидает динамическую выборку
    (переходит в `done`), затем заводится алерт с её `target` — алерт
    обязан появиться в потоке несмотря на то, что задача уже не входит
    в текущую пересчитанную `--all`-выборку."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self._stream = _WatchStream()
        self._thread = None
        # `_watch_outcome`, не `_outcome` — `unittest.TestCase` несёт СВОЙ
        # внутренний атрибут `self._watch_outcome` (Python 3.11+, `case.py`);
        # переопределение тем же именем ломает `doCleanups` неясным
        # `AttributeError: 'dict' object has no attribute 'testPartExecutor'`.
        self._watch_outcome = {}

    def _insert_task(self, task_id: str) -> None:
        from orchestrator import config
        store.insert_task(
            store.db(), task_id, f"Задача {task_id}", "in_dev",
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
        self._thread.join(timeout=5.0)
        self.assertFalse(self._thread.is_alive(),
                         "watch не завершился после того, как все задачи "
                         "выборки стали терминальны")
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


if __name__ == "__main__":
    unittest.main()
