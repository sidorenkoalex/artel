"""AC-1 (tasks/T065/SPEC.md): запуск `canary <каталог>` на каталоге из
двух тестовых ТЗ-файлов заводит по задаче на каждый файл, проводит обе
через `spec_gate` и `acceptance` автоматически с пометкой `canary` в
журнале, на `merge_gate` каждую убивает (`kill`) с пометкой; sha `main`
до и после прогона идентичен; итоговый отчёт (stdout и файл
`.artel/canary/<timestamp>.json`) содержит метрики (шаги, стоимость,
итерации ревью, эскалации, исход) по обеим задачам.

Красен до реализации: команды `canary` нет в таблице `orchestrator/
artel.py::main` — `run_canary` (см. `_sandbox.py`) ловит `SystemExit`
«Неизвестная команда canary» и пишет его в возвращаемый текст, после
чего задач не заводится ни одной, и первая же содержательная проверка
(`len(task_ids) == 2`) падает `AssertionError` по отсутствию кода
задачи, а не по случайной ошибке песочницы (проверено самим прогоном
файла: см. коммит этой задачи — `python3 -m unittest discover` красит
именно этот тест этой причиной).
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CanarySandbox, task_metrics  # noqa: E402

from orchestrator import config  # noqa: E402

TZ_TEXTS = {
    "malaya-ficha.md": "Добавь маленькую синтетическую фичу X с тестами.",
    "udalenie-rudimenta.md": "Убери неиспользуемый синтетический модуль Y.",
}


class ReportAndGateFlowTest(CanarySandbox):

    def setUp(self):
        super().setUp()
        self.tz_dir = self.write_tz_files(TZ_TEXTS)

    def test_ac1_two_files_go_through_gates_and_are_killed_with_a_report(self):
        sha_before = self.main_sha()

        out = self.run_canary(self.tz_dir)

        sha_after = self.main_sha()
        self.assertEqual(sha_before, sha_after,
                         "sha main изменился за время прогона canary")

        task_ids = self.task_ids()
        self.assertEqual(len(task_ids), 2,
                         f"по 2 ТЗ-файлам заведено задач: {len(task_ids)} "
                         f"({task_ids})")

        for task_id in task_ids:
            with self.subTest(задача=task_id):
                row = self.task_row(task_id)
                self.assertEqual(row["state"], "killed",
                                 f"{task_id} не убита на merge_gate "
                                 f"(состояние: {row['state']})")
                marks = self.journal_text(task_id).lower().count("canary")
                self.assertGreaterEqual(
                    marks, 2,
                    f"{task_id}: журнал несёт меньше двух пометок canary "
                    f"(ожидались минимум spec_gate + acceptance/merge_gate):"
                    f"\n{self.journal_text(task_id)}")

        canary_dir = config.ROOT / ".artel" / "canary"
        self.assertTrue(canary_dir.is_dir(),
                        f"{canary_dir} не создан")
        reports = sorted(p for p in canary_dir.glob("*.json")
                         if p.name != "baseline.json")
        self.assertEqual(len(reports), 1,
                         f"ожидался один файл отчёта прогона, найдено: "
                         f"{reports}")
        data = json.loads(reports[0].read_text(encoding="utf-8"))

        for task_id in task_ids:
            with self.subTest(задача=task_id):
                metrics = task_metrics(data, task_id)
                self.assertIsNotNone(
                    metrics, f"в отчёте нет записи по {task_id}: {data}")
                for key in ("steps", "cost_usd", "review_iterations",
                           "escalations", "outcome"):
                    self.assertIn(key, metrics,
                                 f"{task_id}: в отчёте нет поля '{key}': "
                                 f"{metrics}")
                self.assertGreaterEqual(metrics["steps"], 1,
                                        f"{task_id}: 0 шагов — задача не "
                                        f"выполнялась")
                self.assertGreaterEqual(metrics["cost_usd"], 0)
                self.assertGreaterEqual(metrics["review_iterations"], 0)
                self.assertIsInstance(metrics["escalations"], list)
                self.assertIn("kill", str(metrics["outcome"]).lower(),
                             f"{task_id}: исход не назван 'killed'-подобным "
                             f"словом: {metrics['outcome']!r}")

        for task_id in task_ids:
            self.assertIn(task_id, out,
                         f"{task_id} не упомянута в stdout-отчёте:\n{out}")


if __name__ == "__main__":
    unittest.main()
