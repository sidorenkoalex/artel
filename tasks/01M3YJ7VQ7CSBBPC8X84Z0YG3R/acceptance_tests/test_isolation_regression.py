"""AC-5, AC-6 — регрессионный тест `tests/test_merge_gate_clock_isolation.py`
зелёный на изоляции часов и краснеет при возврате глобальной подмены
`time.sleep`.

Группа: разовый
Красен до реализации: файла tests/test_merge_gate_clock_isolation.py в кодовой ветке задачи ещё нет.

Регрессионный тест гоняется в отдельном интерпретаторе драйвером
`DRIVER` (корень кода под проверкой — рабочий каталог): драйвер замеряет
время жизни каждого дочернего процесса (`subprocess.Popen` от создания до
сбора статуса) и, в режиме мутации, возвращает глобальную подмену
`time.sleep`: всякий раз, когда тест подставляет свои часы вместо
`fsm_merge_gate.time`, `time.sleep` модуля `time` получает тот же `sleep`
часов (и восстанавливается, когда на место возвращается модуль `time`) —
ровно мутация «вернуть `mock.patch.object(time, "sleep", …)`» без правки
самого теста.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402

CLAIM = "Ловит мутацию:"
MIN_CHILD_SEC = 0.3
MUTATED_RUNS = 3
MARK = "ACC-RESULT "

DRIVER = r'''
import json, subprocess, sys, time, types, unittest
root, mutate = sys.argv[1], sys.argv[2] == "1"
sys.path.insert(0, root)
from orchestrator import fsm_merge_gate

REAL_SLEEP = time.sleep
lifetimes = []
_orig_init = subprocess.Popen.__init__
_orig_handle = subprocess.Popen._handle_exitstatus


def _init(self, *a, **k):
    self._acc_t0 = time.perf_counter()
    _orig_init(self, *a, **k)


def _handle(self, *a, **k):
    _orig_handle(self, *a, **k)
    t0 = self.__dict__.pop("_acc_t0", None)
    if t0 is not None:
        lifetimes.append(time.perf_counter() - t0)


subprocess.Popen.__init__ = _init
subprocess.Popen._handle_exitstatus = _handle
hooked = []

if mutate:
    class _Hook(types.ModuleType):
        def __setattr__(self, name, value):
            super().__setattr__(name, value)
            if name == "time":
                if value is time:
                    time.sleep = REAL_SLEEP
                else:
                    hooked.append(repr(value))
                    time.sleep = value.sleep

    fsm_merge_gate.__class__ = _Hook

suite = unittest.defaultTestLoader.loadTestsFromName(
    "tests.test_merge_gate_clock_isolation")
result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(suite)
time.sleep = REAL_SLEEP
print("ACC-RESULT " + json.dumps({
    "run": result.testsRun,
    "failures": len(result.failures),
    "errors": len(result.errors),
    "skipped": len(result.skipped),
    "ok": result.wasSuccessful(),
    "lifetimes": lifetimes,
    "hooked": len(hooked),
}))
'''


def run_driver(case: unittest.TestCase, mutate: bool) -> tuple[dict, str]:
    """(итог прогона регрессионного теста, вывод для текста провала)."""
    res = subprocess.run(
        [sys.executable, "-c", DRIVER, str(_util.REPO), "1" if mutate else "0"],
        cwd=_util.REPO, capture_output=True, text=True, timeout=300)
    log = f"код {res.returncode}\n{res.stdout[-3000:]}\n{res.stderr[-6000:]}"
    lines = [ln for ln in res.stdout.splitlines() if ln.startswith(MARK)]
    case.assertTrue(lines, f"драйвер не дошёл до итога:\n{log}")
    return json.loads(lines[-1][len(MARK):]), log


class IsolationRegressionTest(unittest.TestCase):

    def test_ac5_regression_test_green_with_long_lived_child(self):
        """`tests/test_merge_gate_clock_isolation.py` есть, несёт «Ловит
        мутацию:», сверяет `sleep_calls` и `monotonic`, зелёный, и за его
        прогон хотя бы один дочерний процесс прожил не меньше 0.3 с.

        Ловит мутацию: дочерний процесс регрессионного теста — короткая
        команда (`true`, `python -c pass`), успевающая выйти до первой
        паузы `Popen._wait`, — наибольшее время жизни дочернего процесса
        меньше 0.3 с; либо утверждение на показание `monotonic` не
        заведено — в тексте файла нет `monotonic`; либо тест красный под
        изоляцией часов (часы ставятся в модуль `time`).
        """
        source = _util.current_source(self, _util.ISOLATION_FILE)
        self.assertIn(CLAIM, source, f"в {_util.ISOLATION_FILE} нет «{CLAIM}»")
        for needle in ("sleep_calls", "monotonic"):
            self.assertIn(needle, source,
                          f"{_util.ISOLATION_FILE} не сверяет {needle}")
        result, log = run_driver(self, mutate=False)
        self.assertGreaterEqual(result["run"], 1, f"тестов не найдено:\n{log}")
        self.assertTrue(result["ok"], f"регрессионный тест красный:\n{log}")
        self.assertEqual(result["skipped"], 0, f"тест пропущен:\n{log}")
        longest = max(result["lifetimes"], default=0.0)
        self.assertGreaterEqual(
            longest, MIN_CHILD_SEC,
            f"ни один дочерний процесс не прожил {MIN_CHILD_SEC} с "
            f"(времена жизни {result['lifetimes']}):\n{log}")

    def test_ac6_regression_test_red_under_global_sleep_patch(self):
        """При возвращённой глобальной подмене `time.sleep` часами теста
        регрессионный тест краснеет провалом утверждения — в каждом из
        нескольких прогонов подряд.

        Ловит мутацию: регрессионный тест подменяет часы, но не сверяет
        `sleep_calls == []` / показание `monotonic` (или сверяет до
        запуска дочернего процесса) — при глобальной подмене он остаётся
        зелёным; либо дочерний процесс выходит раньше первой паузы
        `Popen._wait` — краснота зависит от скорости машины и пропадает
        хотя бы в одном прогоне.
        """
        for attempt in range(1, MUTATED_RUNS + 1):
            result, log = run_driver(self, mutate=True)
            self.assertGreaterEqual(result["run"], 1,
                                    f"тестов не найдено:\n{log}")
            self.assertGreaterEqual(
                result["hooked"], 1,
                f"тест не подставлял часы вместо fsm_merge_gate.time — "
                f"мутации некуда встать:\n{log}")
            self.assertGreaterEqual(
                result["failures"], 1,
                f"прогон {attempt}/{MUTATED_RUNS}: под мутацией "
                f"регрессионный тест не покраснел провалом:\n{log}")


if __name__ == "__main__":
    unittest.main()
