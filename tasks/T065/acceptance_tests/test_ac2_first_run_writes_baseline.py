"""AC-2 (tasks/T065/SPEC.md): прогон `canary`, для которого файла
`.artel/canary/baseline.json` ещё нет, создаёт этот файл с суммарными
метриками набора (стоимость, шаги).

Красен до реализации: команды `canary` нет в таблице `orchestrator/
artel.py::main` — `run_canary` (см. `_sandbox.py`) ловит `SystemExit`
«Неизвестная команда canary», ни одна задача не заводится, и
`baseline.json` не создаётся — первая содержательная проверка
(`baseline_path.exists()`) падает `AssertionError` по отсутствию кода
задачи.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CanarySandbox, summary_metrics  # noqa: E402

from orchestrator import config  # noqa: E402

TZ_TEXTS = {
    "feature.md": "Добавь маленькую синтетическую фичу с тестами.",
    "rudiment.md": "Убери неиспользуемый синтетический модуль.",
}


class FirstRunWritesBaselineTest(CanarySandbox):

    def setUp(self):
        super().setUp()
        self.tz_dir = self.write_tz_files(TZ_TEXTS)
        self.baseline_path = config.ROOT / ".artel" / "canary" / "baseline.json"

    def test_ac2_first_run_with_no_baseline_creates_one(self):
        self.assertFalse(self.baseline_path.exists(),
                         "тест начинается без существующего baseline.json")

        self.run_canary(self.tz_dir)

        self.assertTrue(self.baseline_path.exists(),
                        "первый прогон canary не создал baseline.json")
        data = json.loads(self.baseline_path.read_text(encoding="utf-8"))
        metrics = summary_metrics(data)
        self.assertIsNotNone(
            metrics, f"baseline.json не несёт суммарных стоимости/шагов: {data}")
        self.assertGreaterEqual(metrics["cost_usd"], 0)
        # 2 задачи, у каждой минимум по шагу — суммарно строго больше 0.
        self.assertGreaterEqual(metrics["steps"], 2,
                                f"суммарные шаги по 2 задачам меньше 2: "
                                f"{metrics}")


if __name__ == "__main__":
    unittest.main()
