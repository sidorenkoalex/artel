"""AC-4, AC-5: подсчёт группы процессов в `test_liveness` под нагрузкой и
поведение `orchestrator/liveness.py::_group_member_count` при сбое `ps`.

Группа: разовый
Красен до реализации: под нагрузкой метод `test_counts_members_exactly_when_ps_is_not_on_path` в main падает «1 != 2» уже на первом-втором из пяти прогонов (plank-run 11.10, macOS, 14 ядер) — подсчёт идёт в гонке с выходом потомка, спящего 5 с; остальные тесты файла (мутация «`ps` только по PATH», AC-5) зелены с рождения: в main они уже держат своё свойство.

Валидация стабом (11.10): метод с `_spawn_group_with_child(sleep_sec=60)`
и `print(c.pid, flush=True)` в скрипте лидера — все четыре теста зелёные.
Одного `sleep_sec` стабу не хватило: лидер печатает pid потомка в канал без
сброса буфера, и `leader.stdout.readline()` возвращается только при выходе
лидера через `sleep_sec` — подсчёт при любом `sleep_sec` идёт в момент выхода
группы (с `sleep_sec=60` прогон упирается в предел 20 с на `readline`).

Метод `test_liveness` гоняется отдельно от остального файла: прочие методы
файла идут последовательно и на исход этого метода не влияют, а пять
прогонов всего файла под нагрузкой (~16 с без нагрузки каждый) не
укладываются в предел теста планки. Мутация AC-4 вносится подменой
`liveness._ps_executable` в интерпретаторе прогона до pytest (функция
названа в SPEC, «Материалы»): `ps` берётся голым именем — только по PATH
вызывающего.
"""
import ast
import os
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402

if str(_util.ROOT) not in sys.path:
    sys.path.insert(0, str(_util.ROOT))

from orchestrator import liveness  # noqa: E402

RUNS = 5
RUN_TIMEOUT = 20
NODE = f"{_util.LIVENESS_FILE}::{'::'.join(_util.LIVENESS_METHOD)}"
PATH_ONLY_MUTANT = ("from orchestrator import liveness\n"
                    "liveness._ps_executable = lambda: 'ps'")
PS_TIMEOUT_CEILING = 15


def _asserts_exactly_two(node) -> bool:
    for sub in ast.walk(node):
        if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "assertEqual"
                and any(isinstance(arg, ast.Constant) and arg.value == 2
                        and type(arg.value) is int for arg in sub.args)):
            return True
    return False


class GroupCountUnderLoadTest(unittest.TestCase):

    def test_ac4_counts_exactly_two_five_runs_in_a_row_under_load(self):
        """Под нагрузкой пять прогонов подряд метода — зелёные, «ровно 2».

        Сценарий: метод ветки несёт утверждение `assertEqual(…, 2)`; при
        запущенном нагрузочном процессе (по числу ядер `while 1: pass`) метод
        гоняется pytest пять раз подряд, каждый прогон обязан вернуть код 0.

        Ловит мутацию: правка задачи оставила потомку короткий срок жизни
        (`sleep_sec`, истекающий раньше подсчёта под нагрузкой) или
        ослабила утверждение до `assertGreaterEqual(count, 1)` — подсчёт
        приходит после выхода потомка (1 != 2) либо утверждения «ровно 2»
        в методе нет, тест покраснеет.
        """
        cls, name = _util.LIVENESS_METHOD
        node = _util.method_node(_util.branch_text(_util.LIVENESS_FILE), cls,
                                 name)
        self.assertIsNotNone(node, f"метода {cls}.{name} нет")
        self.assertTrue(_asserts_exactly_two(node),
                        "в методе нет утверждения assertEqual(..., 2)")
        argv = _util.pytest_argv(NODE, RUN_TIMEOUT)
        with _util.cpu_load() as procs:
            for run in range(1, RUNS + 1):
                code, out, seconds = _util.run(argv, _util.ROOT,
                                               RUN_TIMEOUT + 5)
                self.assertEqual(code, 0, f"прогон {run} из {RUNS} под "
                                 f"нагрузкой ({procs} процессов) не зелёный "
                                 f"за {seconds:.1f} с:\n{_util.tail(out)}")

    def test_ac4_path_only_ps_mutation_reddens_the_method(self):
        """Мутация «`ps` только по PATH вызывающего» краснит метод.

        Сценарий: в интерпретаторе прогона до pytest
        `liveness._ps_executable` заменён на голое имя `ps` (без запасных
        `/bin`, `/usr/bin`); метод ветки гоняется в этом интерпретаторе и
        обязан упасть на утверждении о подсчёте.

        Ловит мутацию: правка задачи перестала очищать PATH в методе (или
        подсчёт делает не `_group_member_count`) — голый `ps` находится,
        мутант зелен, тест покраснеет.
        """
        argv = _util.pytest_argv(NODE, RUN_TIMEOUT, prelude=PATH_ONLY_MUTANT)
        code, out, _ = _util.run(argv, _util.ROOT, RUN_TIMEOUT + 10)
        self.assertNotIn(code, (0, None), f"мутант зелен или завис:\n"
                         f"{_util.tail(out)}")
        self.assertIn("1 failed", out, _util.tail(out))
        self.assertIn("AssertionError", out, _util.tail(out))


def _spawn_live_group() -> subprocess.Popen:
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                            start_new_session=True, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            if os.getpgid(proc.pid) == proc.pid:
                break
        except ProcessLookupError:
            break
        time.sleep(0.02)
    return proc


class PsFailureTest(unittest.TestCase):

    def setUp(self):
        self.proc = _spawn_live_group()
        self.addCleanup(self.proc.wait)
        self.addCleanup(self._kill)

    def _kill(self):
        try:
            os.killpg(self.proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    def test_ac5_live_group_is_not_zero_when_ps_fails(self):
        """Сбой `ps` на живой группе не даёт 0.

        Сценарий: живая группа (лидер своей сессии); вызов `ps` подменён
        тремя сбоями — не запустился (`FileNotFoundError`), не ответил в
        срок (`TimeoutExpired`), ненулевой код; на каждом
        `_group_member_count` группы не равен 0.

        Ловит мутацию: сбой `ps` выдаётся за пустую группу — ветка
        исключения или ненулевого кода возвращает 0 без сверки
        `os.killpg(pgid, 0)` — подсчёт 0, тест покраснеет с именем сбоя.
        """
        real_run = subprocess.run

        def failing(kind):
            def fake(argv, *args, **kwargs):
                if kind == "не запустился":
                    raise FileNotFoundError(2, "ps")
                if kind == "не ответил в срок":
                    raise subprocess.TimeoutExpired(argv, kwargs.get("timeout")
                                                    or 1)
                if kwargs.get("check"):
                    raise subprocess.CalledProcessError(1, argv, "", "")
                return subprocess.CompletedProcess(argv, 1, "", "")
            return fake

        for kind in ("не запустился", "не ответил в срок", "ненулевой код"):
            with self.subTest(kind):
                with mock.patch.object(subprocess, "run", failing(kind)):
                    count = liveness._group_member_count(self.proc.pid)
                self.assertNotEqual(count, 0, f"сбой ps «{kind}»: живая "
                                    f"группа посчитана пустой")
        self.assertIs(subprocess.run, real_run)

    def test_ac5_ps_timeout_is_at_most_15_seconds(self):
        """Таймаут `ps` в подсчёте задан и не больше 15 с.

        Сценарий: вызов `subprocess.run` записывается (и исполняется
        настоящим); подсчёт живой группы зовёт `ps` хотя бы раз, у каждого
        такого вызова `timeout` задан и не больше 15.

        Ловит мутацию: таймаут `ps` поднят до 30 с или снят вовсе
        (`timeout=None`) — записанный таймаут вне рамки, тест покраснеет.
        """
        real_run = subprocess.run
        calls = []

        def recording(argv, *args, **kwargs):
            calls.append((list(argv), kwargs.get("timeout")))
            return real_run(argv, *args, **kwargs)

        with mock.patch.object(subprocess, "run", recording):
            count = liveness._group_member_count(self.proc.pid)
        ps_calls = [(argv, timeout) for argv, timeout in calls
                    if argv and os.path.basename(str(argv[0])) == "ps"]
        self.assertTrue(ps_calls, f"подсчёт не вызвал ps: {calls}")
        for argv, timeout in ps_calls:
            self.assertIsNotNone(timeout, f"у вызова {argv} нет таймаута")
            self.assertLessEqual(timeout, PS_TIMEOUT_CEILING,
                                 f"таймаут ps {timeout} с > 15 с ({argv})")
        self.assertGreaterEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
