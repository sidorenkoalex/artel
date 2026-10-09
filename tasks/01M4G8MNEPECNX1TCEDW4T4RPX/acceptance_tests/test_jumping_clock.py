"""AC-6 — два теста требования 3 проходят на «замедленной машине»: часы идут скачком, настоящего ожидания по часам нет.

«Замедленная машина» разыгрывается подменой часов во всех процессах pytest
прогона: плагин `artel_jumping_clock` (текст ниже, кладётся во временный
каталог и подключается через `PYTHONPATH` + `PYTEST_ADDOPTS=-p …`)
подменяет `time.monotonic` и `time.time` так, что каждый вызов сдвигает
часы вперёд на скачок S секунд (S — от зерна, 30–300 с): любое ожидание до
срока по этим часам истекает на первой же проверке, как на машине, где
между двумя строками теста прошли минуты. Стандартные модули, у которых
своя ссылка на часы (`subprocess`, `threading`, `queue`, `selectors`,
`socket`, `asyncio`, `sqlite3`), импортируются плагином ДО подмены — их
таймауты-страховки идут по настоящим часам. `PYTEST_ADDOPTS` наследуют
дочерние pytest (пробник набора, который запускает `suite-run`), а не
`artel.py` — код пульта в дочерних процессах часы не подменяет.

«Без настоящего ожидания по часам»: плагин записывает каждый вызов
`time.sleep` с ненулевой паузой и каждое `threading.Event.wait(timeout)`,
истёкшее по сроку (событие не пришло), сделанные кодом файла из `tests/`
(кроме помощников песочницы `tests/sandbox.py`); таких записей быть не
должно. Страховочный срок ожидания события, до которого событие пришло,
не записывается. Прежние утверждения обоих тестов — предмет гейта неослабления
пульта (SPEC, «Не входит»); здесь тесты гоняются по их прежним адресам.

Группа: разовый
Красен до реализации: `wait_until` теста дозора ждёт `while time.monotonic() < deadline` и `hold` спит `time.sleep(1.2)` — под скачущими часами ожидание истекает на первой проверке, тест падает «не дождались»; пробник `SuiteRunProfileLimitTest` держится `while time.time() < deadline` — под скачком отпускает прогон сразу, отчёта «не уложился» нет.
"""
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT  # noqa: E402

RUN_TIMEOUT_SEC = 110
PLUGIN = "artel_jumping_clock"
WATCH_NODE = ("tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py::"
              "Ac6NoCommitWarningTest::"
              "test_ac6_warning_once_per_step_and_again_for_new_step")
SUITE_NODE = ("tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py::"
              "SuiteRunProfileLimitTest::"
              "test_ac5_suite_run_cuts_at_profile_limit_and_reports_it")

PLUGIN_TEXT = r'''"""Скачущие часы для планки AC-6: каждый вызов сдвигает часы на скачок."""
import atexit
import json
import os
import sys
import threading

# Своя ссылка на часы у этих модулей берётся при импорте: импорт до подмены
# оставляет их таймауты-страховки на настоящих часах.
import asyncio  # noqa: F401
import concurrent.futures  # noqa: F401
import queue  # noqa: F401
import selectors  # noqa: F401
import socket  # noqa: F401
import sqlite3  # noqa: F401
import subprocess  # noqa: F401
import time

_STEP = float(os.environ["ARTEL_JUMP_STEP_SEC"])
_TESTS = os.path.realpath(os.environ["ARTEL_JUMP_TESTS_DIR"])
_SANDBOX = os.path.join(_TESTS, "sandbox.py")
_REPORT = os.environ["ARTEL_JUMP_REPORT_DIR"]
_real_monotonic = time.monotonic
_real_time = time.time
_real_sleep = time.sleep
_lock = threading.Lock()
_offset = [0.0]
_sleeps = []


def _jump():
    with _lock:
        _offset[0] += _STEP
        return _offset[0]


def monotonic():
    return _real_monotonic() + _jump()


def wall():
    return _real_time() + _jump()


def _note_wait(kind, seconds):
    frame = sys._getframe(2)
    path = os.path.realpath(frame.f_code.co_filename)
    if path.startswith(_TESTS + os.sep) and path != _SANDBOX:
        _sleeps.append({"kind": kind, "file": path, "line": frame.f_lineno,
                        "seconds": seconds})


def sleep(seconds):
    if seconds and seconds > 0:
        _note_wait("time.sleep", seconds)
    _real_sleep(seconds)


_real_event_wait = threading.Event.wait


def event_wait(self, timeout=None):
    """Ожидание события, истёкшее по сроку, — то же ожидание по часам;
    страховочный срок, до которого событие пришло, не записывается."""
    happened = _real_event_wait(self, timeout)
    if not happened and timeout and timeout > 0:
        _note_wait("Event.wait истёк", timeout)
    return happened


time.monotonic = monotonic
time.time = wall
time.sleep = sleep
threading.Event.wait = event_wait


@atexit.register
def _report():
    with open(os.path.join(_REPORT, f"{os.getpid()}.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"sleeps": _sleeps, "jumps": _offset[0] / _STEP}, fh)
'''


class JumpingClockTest(unittest.TestCase):

    def setUp(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.step = random.Random(self.seed).randint(30, 300)
        self.tmp = tempfile.TemporaryDirectory(prefix="jumping-clock-plank-")
        self.addCleanup(self.tmp.cleanup)
        self.plugin_dir = Path(self.tmp.name) / "plugin"
        self.plugin_dir.mkdir()
        (self.plugin_dir / f"{PLUGIN}.py").write_text(PLUGIN_TEXT,
                                                      encoding="utf-8")
        self.report_dir = Path(self.tmp.name) / "report"
        self.report_dir.mkdir()

    def run_node(self, node: str) -> tuple:
        """(код выхода, вывод, записи плагина процесса pytest) прогона
        `node` под скачущими часами."""
        env = {k: v for k, v in os.environ.items() if k != "PYTEST_ADDOPTS"}
        env.update(
            PYTHONPATH=os.pathsep.join(
                [str(self.plugin_dir)]
                + [p for p in [env.get("PYTHONPATH")] if p]),
            PYTEST_ADDOPTS=f"-p {PLUGIN}",
            ARTEL_JUMP_STEP_SEC=str(self.step),
            ARTEL_JUMP_TESTS_DIR=str(Path(CODE_ROOT) / "tests"),
            ARTEL_JUMP_REPORT_DIR=str(self.report_dir),
            PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.Popen(
            [sys.executable, "-m", "pytest", node, "-q", "-p",
             "no:cacheprovider", "-o", "addopts="],
            cwd=str(CODE_ROOT), env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, start_new_session=True)
        try:
            out, _ = proc.communicate(timeout=RUN_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, 9)
            out, _ = proc.communicate()
            self.fail(self.note(f"{node} не завершился за {RUN_TIMEOUT_SEC} с "
                                f"под скачущими часами:\n{out[-3000:]}"))
        report_path = self.report_dir / f"{proc.pid}.json"
        report = (json.loads(report_path.read_text(encoding="utf-8"))
                  if report_path.exists() else None)
        return proc.returncode, out, report

    def note(self, text: str) -> str:
        return f"{text}\nзерно: {self.seed}, скачок часов: {self.step} с"

    def assert_passes_on_jumping_clock(self, node: str) -> None:
        code, out, report = self.run_node(node)
        self.assertIsNotNone(report, self.note(
            f"плагин скачущих часов не загрузился в pytest:\n{out[-3000:]}"))
        self.assertEqual(code, 0, self.note(
            f"{node} красен под скачущими часами:\n{out[-5000:]}"))
        self.assertRegex(out, r"\b1 passed\b", self.note(
            f"{node} не исполнился:\n{out[-3000:]}"))
        self.assertEqual(report["sleeps"], [], self.note(
            f"{node}: код tests/ ждал по настоящим часам (time.sleep с "
            f"ненулевой паузой вне tests/sandbox.py)"))

    def test_ac6_watch_no_commit_warning_passes_on_jumping_clock(self):
        """`Ac6NoCommitWarningTest::test_ac6_warning_once_per_step_and_again_for_new_step` зелен при скачущих часах и не спит.

        Сценарий: тест дозора гоняется отдельным pytest с плагином скачущих
        часов (каждый вызов `time.monotonic`/`time.time` — плюс S секунд);
        код выхода 0, исполнен один тест, вызовов `time.sleep` с ненулевой
        паузой из кода `tests/` (кроме `tests/sandbox.py`) нет.

        Ловит мутацию: `wait_until` оставлен циклом до срока по
        `time.monotonic()` — под скачком истекает на первой проверке,
        «не дождались»; ожидание переведено на подменённое время, но
        `hold` по-прежнему `time.sleep(1.2)` — запись паузы в отчёте
        плагина.
        """
        self.assert_passes_on_jumping_clock(WATCH_NODE)

    def test_ac6_suite_run_profile_limit_passes_on_jumping_clock(self):
        """`SuiteRunProfileLimitTest::test_ac5_suite_run_cuts_at_profile_limit_and_reports_it` зелен при скачущих часах и не спит.

        Сценарий: тот же плагин в процессе теста и в дочернем pytest
        пробника (через `PYTEST_ADDOPTS`); `suite-run` по-прежнему обрывает
        прогон по пределу профиля и называет его — код выхода 0, исполнен
        один тест, пауз `time.sleep` из кода `tests/` нет.

        Ловит мутацию: пробник держится `while time.time() < deadline`
        (прежний вид) — под скачком отпускает прогон сразу, отчёта «не
        уложился» нет, тест красен; пробник держится сроком от
        `time.monotonic()` вместо `time.time()` — то же: прогон отпущен
        сразу, отчёта о таймауте нет.
        """
        self.assert_passes_on_jumping_clock(SUITE_NODE)


if __name__ == "__main__":
    unittest.main()
