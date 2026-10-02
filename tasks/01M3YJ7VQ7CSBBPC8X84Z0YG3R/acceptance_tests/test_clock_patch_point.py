"""AC-1, AC-3 — часы тестов гейта мержа подменяются в пространстве имён
`orchestrator/fsm_merge_gate.py`, а не в модуле `time`.

Группа: разовый
Красен до реализации: оба файла ещё подменяют `time.sleep`/`time.monotonic` модуля `time` целиком — пауза `time.sleep` вне пульта попадает в часы теста, а статическая сверка находит `mock.patch.object(time, …)`.

Наблюдение ведётся настоящими `setUp` классов `MergeGateCiWaitUnitTest` и
`NonRedStatusSkipsRerunTest` кода под проверкой: probe-метод подкласса
под их часами зовёт `time.sleep` модуля `time` (код вне пульта) и
`fsm_merge_gate.time.sleep` (пауза пульта) и сверяет показания часов.
"""
import ast
import random
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402

from orchestrator import fsm_merge_gate  # noqa: E402


def _observe(test, pult_pause: float) -> dict:
    """Показания часов `test.clock` до/после пауз вне пульта и пульта."""
    clock = test.clock
    calls = getattr(clock, "sleep_calls", None)
    obs = {"value0": clock.value,
           "calls0": list(calls) if calls is not None else None}
    time.sleep(0.01)
    obs["value_after_std"] = clock.value
    obs["calls_after_std"] = list(calls) if calls is not None else None
    obs["pult_mono0"] = fsm_merge_gate.time.monotonic()
    fsm_merge_gate.time.sleep(pult_pause)
    obs["pult_mono1"] = fsm_merge_gate.time.monotonic()
    obs["value_after_pult"] = clock.value
    obs["calls_after_pult"] = list(calls) if calls is not None else None
    return obs


class ClockPatchPointTest(unittest.TestCase):

    def setUp(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        rnd = random.Random(self.seed)
        self.pult_pause = round(rnd.uniform(1.0, 500.0), 3)

    def test_ac1_std_sleep_ignored_pult_sleep_counted(self):
        """Под часами `MergeGateCiWaitUnitTest` пауза `time.sleep(0.01)` из
        кода вне пульта не трогает часы, а `fsm_merge_gate.time.sleep(x)`
        добавляет `x` в `sleep_calls` и сдвигает `monotonic()` пульта на `x`.

        Ловит мутацию: в `setUp` оставлена (или добавлена рядом с новой)
        подмена `mock.patch.object(time, "sleep", clock.sleep)` — пауза
        вне пульта попадёт в `sleep_calls` и сдвинет `clock.value`; либо
        подмена `fsm_merge_gate.time` отдаёт настоящий `sleep`/чужие часы
        — `x` не появится в `sleep_calls`, `monotonic()` не сдвинется.
        """
        obs = _util.run_probe(self, "tests.test_merge_gate_ci_wait",
                              "MergeGateCiWaitUnitTest",
                              lambda t: _observe(t, self.pult_pause))
        msg = f"зерно {self.seed}, наблюдения {obs}"
        self.assertEqual(obs["calls_after_std"], obs["calls0"],
                         f"пауза вне пульта попала в sleep_calls; {msg}")
        self.assertEqual(obs["value_after_std"], obs["value0"],
                         f"пауза вне пульта сдвинула clock.value; {msg}")
        self.assertEqual(obs["calls_after_pult"],
                         obs["calls0"] + [self.pult_pause],
                         f"пауза пульта не записана в sleep_calls; {msg}")
        self.assertAlmostEqual(obs["pult_mono1"] - obs["pult_mono0"],
                               self.pult_pause, places=6, msg=msg)
        self.assertAlmostEqual(obs["value_after_pult"] - obs["value0"],
                               self.pult_pause, places=6, msg=msg)

    def test_ac1_no_global_time_patch_in_file(self):
        """В `tests/test_merge_gate_ci_wait.py` нет подмены `sleep`/
        `monotonic` модуля `time` целиком.

        Ловит мутацию: точка подмены перенесена в `fsm_merge_gate.time`, но
        прежние `mock.patch.object(time, "sleep"/"monotonic", …)` в
        `setUp` не удалены — строка с ними в тексте провала.
        """
        found = _util.global_time_patches(
            _util.current_source(self, _util.CI_WAIT_FILE))
        self.assertEqual(found, [], f"{_util.CI_WAIT_FILE} подменяет часы "
                                    f"модуля time")

    def test_ac3_kind_gate_clock_patched_in_pult_namespace(self):
        """Под часами `NonRedStatusSkipsRerunTest` пауза `time.sleep(0.01)`
        вне пульта не сдвигает `clock.value`, а `fsm_merge_gate.time.
        sleep(x)` сдвигает его и `monotonic()` пульта на `x`; файл не
        подменяет часы модуля `time`.

        Ловит мутацию: `tests/test_ci_status_kind_gate.py` оставлен на
        `mock.patch.object(time, "sleep", …)` — пауза вне пульта сдвинет
        `clock.value`, статическая сверка назовёт строку подмены; либо
        `fsm_merge_gate.time` не подменён — `monotonic()` пульта не
        сдвинется на `x`.
        """
        obs = _util.run_probe(self, "tests.test_ci_status_kind_gate",
                              "NonRedStatusSkipsRerunTest",
                              lambda t: _observe(t, self.pult_pause))
        msg = f"зерно {self.seed}, наблюдения {obs}"
        self.assertEqual(obs["value_after_std"], obs["value0"],
                         f"пауза вне пульта сдвинула clock.value; {msg}")
        self.assertAlmostEqual(obs["pult_mono1"] - obs["pult_mono0"],
                               self.pult_pause, places=6, msg=msg)
        self.assertAlmostEqual(obs["value_after_pult"] - obs["value0"],
                               self.pult_pause, places=6, msg=msg)
        found = _util.global_time_patches(
            _util.current_source(self, _util.KIND_GATE_FILE))
        self.assertEqual(found, [], f"{_util.KIND_GATE_FILE} подменяет часы "
                                    f"модуля time")

    def test_ac3_kind_gate_methods_and_assertions_kept_and_green(self):
        """Все тестовые методы `tests/test_ci_status_kind_gate.py` из базы
        ветки на месте, их утверждения сохранены, файл зелёный.

        Ловит мутацию: при переводе часов удалён или переименован тестовый
        метод либо снято/ослаблено утверждение (например,
        `assertGreater(mocked.call_count, 1, …)` превращено в
        `assertGreaterEqual(…, 1)`) — метод и утверждение в тексте провала;
        новая подмена часов не доходит до пульта, и цикл ожидания реально
        спит — прогон файла упадёт по таймауту/красноте.
        """
        base = _util.base_source(self, _util.KIND_GATE_FILE)
        now = _util.current_source(self, _util.KIND_GATE_FILE)
        missing_methods = sorted(set(_util.test_methods(base))
                                 - set(_util.test_methods(now)))
        self.assertEqual(missing_methods, [], "пропали тестовые методы")
        missing = []
        after = _util.test_methods(now)
        for key, node in _util.test_methods(base).items():
            left = _unparse_asserts(after[key])
            for text in _unparse_asserts(node):
                if text in left:
                    left.remove(text)
                else:
                    missing.append(f"{key}: {text}")
        self.assertEqual(missing, [], "утверждения сняты или изменены")
        _util.run_pytest_file(self, _util.KIND_GATE_FILE)


def _unparse_asserts(node) -> list[str]:
    """Нормализованные тексты всех `self.assert*(…)` метода."""
    return [ast.unparse(sub) for sub in ast.walk(node)
            if isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Attribute)
            and sub.func.attr.startswith("assert")]


if __name__ == "__main__":
    unittest.main()
