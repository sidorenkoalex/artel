"""Общая песочница приёмочных тестов 01M290PP4KBTG1KYS1PWKQJH6T (дозор
`watch` — классы `stops`/`ci`, identity сессии через файл, отказ пустой
`--mine`, `--exit-on`/`--once`).

Не копия `tasks/01M1VBEKRN0GA029J98S0K2DAQ/acceptance_tests/test_watch.py`
(планка предыдущей SPEC того же модуля, залоченная под другой задачей) —
тот же приём фонового потока и `TmpRootTest`, но `_worker` здесь
дополнительно сохраняет СЫРОЙ аргумент `sys.exit(...)` (`exit_message`),
не только числовой код: AC-6 этой задачи требует сверки ИМЕННО текста
отказа на «stderr» (аргумент `sys.exit`), которого прежняя песочница не
несла вовсе.
"""
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402
from orchestrator import watch  # noqa: E402


def _exit_status(code) -> int:
    """Код возврата процесса, который дал бы `sys.exit(code)` — воспроизводит
    поведение самого Python (`None` -> 0, `int` -> он сам по модулю 256,
    любой другой объект, включая строку сообщения, -> 1)."""
    if code is None:
        return 0
    if isinstance(code, int):
        return code % 256
    return 1


class _Stream:
    """Потокобезопасный приёмник stdout фонового потока `watch`."""

    def __init__(self):
        self._chunks = []
        self._lock = threading.Lock()
        self.flush_calls = 0

    def write(self, s):
        with self._lock:
            self._chunks.append(s)

    def flush(self):
        with self._lock:
            self.flush_calls += 1

    def getvalue(self) -> str:
        with self._lock:
            return "".join(self._chunks)


class WatchTestCase(TmpRootTest):
    """Общая песочница: схема БД без `cmd_init` (watch не трогает git и
    роли), `config` патчен во временный каталог (`TmpRootTest`)."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self._stream = None
        self._thread = None
        self._watch_outcome = None

    def _insert_task(self, task_id: str, state: str = "in_dev",
                     target: str = None) -> None:
        store.insert_task(
            store.db(), task_id, f"Задача {task_id}", state,
            f"task/{task_id.lower()}", target or config.DEFAULT_TARGET, 25.0)

    def _set_state(self, task_id: str, new_state: str, expected: str) -> None:
        store.set_state(store.db(), task_id, new_state, "operator",
                        expected_state=expected)

    def _start(self, argv: list) -> threading.Thread:
        self._stream = _Stream()
        self._watch_outcome = {}
        thread = threading.Thread(target=self._worker, args=(argv,),
                                  daemon=True)
        self._thread = thread
        self.addCleanup(self._force_stop)
        thread.start()
        return thread

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

    def _worker(self, argv: list) -> None:
        old_stdout = sys.stdout
        sys.stdout = self._stream
        try:
            watch.cmd_watch(argv)
            self._watch_outcome["exit_code"] = 0
            self._watch_outcome["exit_message"] = None
        except SystemExit as exc:
            self._watch_outcome["exit_code"] = _exit_status(exc.code)
            self._watch_outcome["exit_message"] = exc.code
        except BaseException as exc:  # noqa: BLE001 — диагностика падения потока
            self._watch_outcome["exception"] = exc
        finally:
            sys.stdout = old_stdout

    def _settle(self, seconds: float = 0.3) -> None:
        time.sleep(seconds)

    def _wait_until(self, predicate, timeout: float = 6.0,
                    interval: float = 0.02) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._watch_outcome and "exception" in self._watch_outcome:
                exc = self._watch_outcome["exception"]
                self.fail(f"поток watch упал: {exc!r}")
            if predicate():
                return
            time.sleep(interval)
        self.fail(
            "условие не выполнено за отведённое время; вывод потока:\n"
            + (self._stream.getvalue() if self._stream else "<нет>"))

    def _join(self, timeout: float = 8.0) -> None:
        self._thread.join(timeout=timeout)
        self.assertFalse(self._thread.is_alive(),
                         "watch не завершился за отведённое время")
        if self._watch_outcome and "exception" in self._watch_outcome:
            raise self._watch_outcome["exception"]
