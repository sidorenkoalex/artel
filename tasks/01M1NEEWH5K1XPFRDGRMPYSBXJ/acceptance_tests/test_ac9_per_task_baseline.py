"""AC-9 (SPEC.md): бейзлайн канарейки вычисляется и сохраняется
per-task (по каждой задаче пула отдельно), а не суммой метрик по
набору.

Контраст — явно с v1 (`orchestrator/canary.py::_write_baseline`,
`tasks/T065/SPEC.md` требование 5): там бейзлайн — ОДНО суммарное
число (`_summary`: `sum(cost)`, `sum(steps)` по всему набору), и
отклонение одной-единственной задачи тонет в сумме остальных. Два
прогона ОДНОГО и ТОГО ЖЕ пула (стабильные заголовки шаблонов — то, по
чему бейзлайн обязан сравниваться МЕЖДУ прогонами со свежими task_id
каждый раз, ULID) с раздутым числом ревью-раундов ровно у ОДНОЙ из
двух задач второго прогона: если бейзлайн per-task, отчёт второго
прогона называет расхождением именно раздутую задачу и не называет
вторую; если бы бейзлайн остался суммой (v1-регресс), самое большее,
что можно было бы утверждать, — расхождение НАБОРА в целом, без
указания какая из двух задач его вызвала (эта более слабая гарантия
здесь не проверяется отдельно — SPEC называет как раз обратное:
которая из задач должна быть, а которая не должна быть названа).

Красен до реализации: `canary --k` падает на разборе аргументов уже на
первом прогоне — второй прогон и сверка вообще не достигаются, первая
содержательная проверка (успешное завершение первого прогона) падает.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CanarySandbox, _EphemeralDirTracker  # noqa: E402

TITLE_PROSTAYA = "prostaya-tipovaya-pravka"
TITLE_TRUDNAYA = "trudnaya-tipovaya-pravka"

POOL_TEMPLATES = {
    f"{TITLE_PROSTAYA}.md": "Синтетическая простая типовая правка.",
    f"{TITLE_TRUDNAYA}.md": "Синтетическая типовая правка со сложным ревью.",
}


class PerTaskBaselineTest(CanarySandbox):

    def setUp(self):
        super().setUp()
        self.write_pool_templates(POOL_TEMPLATES)

    def _title_to_task_id(self, tracker: _EphemeralDirTracker) -> dict:
        mapping = {}
        for snap in tracker.git_like_snapshots():
            for t in snap.get("tasks", []):
                mapping[t["title"]] = t["id"]
        return mapping

    def test_ac9_second_run_flags_only_the_task_whose_own_metrics_deviated(self):
        """Первый прогон (k=2, обе задачи «дёшевы» — 0 лишних
        ревью-раундов) пишет бейзлайн. Второй прогон того же пула
        раздувает ревью ТОЛЬКО у `trudnaya-tipovaya-pravka`
        (`config.LIMIT_REVIEW_ITERS` = 3 — держим раздутие ниже
        потолка, 2 лишних раунда, чтобы задача не ушла в escalated
        вместо штатного цикла до merge_gate/killed, тот же приём, что
        `tasks/T065/acceptance_tests/test_ac3_repeat_run_compares_
        baseline.py`). Отчёт второго прогона обязан назвать
        расхождением именно её и не называть `prostaya-tipovaya-pravka`.

        Ловит мутацию: бейзлайн/сравнение остаются суммой по набору
        (буквальный перенос v1 `_summary`/`_baseline_warnings`,
        `orchestrator/canary.py`) — тогда отчёт либо не отличает задачи
        друг от друга вовсе (расхождение видно только « по набору», без
        привязки к конкретному task_id), либо считает суммарный сдвиг
        недостаточным для срабатывания и не называет НИКОГО — в обоих
        случаях `assertTrue` по `trudnaya` не находит расхождения рядом
        с её task_id.
        """
        tracker1 = _EphemeralDirTracker()
        tracker1.start(self, deep=True)
        out1 = self.run_canary_pool(2)
        self.assertNotIn("[SystemExit]", out1, out1)
        tracker1.stop()

        tracker2 = _EphemeralDirTracker()
        tracker2.start(self, deep=True)
        self.agent.extra_review_rounds_by_title[TITLE_TRUDNAYA] = 2
        out2 = self.run_canary_pool(2)
        self.assertNotIn("[SystemExit]", out2, out2)
        tracker2.stop()

        title_to_id = self._title_to_task_id(tracker2)
        trudnaya_id = title_to_id.get(TITLE_TRUDNAYA)
        prostaya_id = title_to_id.get(TITLE_PROSTAYA)
        self.assertIsNotNone(trudnaya_id, title_to_id)
        self.assertIsNotNone(prostaya_id, title_to_id)

        deviation_words = ("отклонени", "внимание", "расхожд")

        def _nearby_flags_deviation(out: str, task_id: str) -> bool:
            idx = out.find(task_id)
            if idx == -1:
                return False
            window = out[max(0, idx - 200):idx + 200].lower()
            return any(w in window for w in deviation_words)

        self.assertTrue(
            _nearby_flags_deviation(out2, trudnaya_id),
            f"второй прогон не отметил отклонение у раздутой задачи "
            f"{trudnaya_id} ({TITLE_TRUDNAYA}):\n{out2}")
        self.assertFalse(
            _nearby_flags_deviation(out2, prostaya_id),
            f"второй прогон ошибочно отметил отклонение у НЕраздутой "
            f"задачи {prostaya_id} ({TITLE_PROSTAYA}):\n{out2}")


if __name__ == "__main__":
    unittest.main()
