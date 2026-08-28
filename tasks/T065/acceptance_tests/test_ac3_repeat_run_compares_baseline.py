"""AC-3 (tasks/T065/SPEC.md): повторный прогон `canary` того же набора
при существующем `baseline.json` сравнивает суммарные метрики текущего
прогона с бейзлайном и печатает предупреждение, если |отклонение| по
стоимости или по шагам превышает порог (дефолт 50%); содержимое
`baseline.json` после прогона не изменилось (перезапись возможна только
явным флагом пересъёма — имя и формат флага SPEC оставляет developer,
поэтому не проверяется здесь, только то, что БЕЗ него файл не трогается).

Второй прогон здесь нарочно раздувает число ревью-раундов
(`SmartAgent.extra_review_rounds_default`, см. `_sandbox.py`) — единственный
рычаг у песочницы, способный сдвинуть суммарные метрики набора без
подмены самого учёта стоимости: `runner.cmd_run` заменён целиком, и
реальный учёт `spend`/`budget` в игру не входит, стоимость остаётся
$0 в обоих прогонах. Раздутие держится ниже `config.LIMIT_REVIEW_ITERS`
(3), чтобы задачи не ушли в escalated вместо штатного цикла.

Красен до реализации: команды `canary` нет в таблице `orchestrator/
artel.py::main` — оба прогона возвращают текст с «Неизвестная команда
canary», `baseline.json` не появляется вовсе, и первая же содержательная
проверка (`baseline_path.exists()`) падает `AssertionError`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CanarySandbox  # noqa: E402

from orchestrator import config  # noqa: E402


class RepeatRunComparesBaselineTest(CanarySandbox):

    def test_ac3_second_run_warns_on_deviation_and_keeps_baseline(self):
        baseline_path = config.ROOT / ".artel" / "canary" / "baseline.json"

        first_dir = self.write_tz_files({
            "feature.md": "Добавь маленькую синтетическую фичу с тестами.",
            "rudiment.md": "Убери неиспользуемый синтетический модуль.",
        })
        self.run_canary(first_dir)
        self.assertTrue(baseline_path.exists(),
                        "первый прогон не создал baseline.json")
        before_bytes = baseline_path.read_bytes()

        # Раздутый ревью-цикл второго прогона -> заметно больше шагов, чем
        # у бейзлайна (см. докстринг модуля) -> гарантированное отклонение
        # выше порога 50% по шагам, независимо от того, как именно
        # developer формулирует «шаг».
        self.agent.extra_review_rounds_default = 2
        second_dir = self.write_tz_files({
            "feature-2.md": "Добавь другую маленькую синтетическую фичу.",
            "rudiment-2.md": "Убери другой неиспользуемый модуль.",
        })

        out = self.run_canary(second_dir)

        after_bytes = baseline_path.read_bytes()
        self.assertEqual(
            before_bytes, after_bytes,
            "повторный прогон изменил baseline.json без явного флага "
            "пересъёма")
        self.assertTrue(
            "внимание" in out.lower() or "отклонени" in out.lower(),
            f"предупреждение об отклонении от бейзлайна не напечатано в "
            f"stdout:\n{out}")


if __name__ == "__main__":
    unittest.main()
