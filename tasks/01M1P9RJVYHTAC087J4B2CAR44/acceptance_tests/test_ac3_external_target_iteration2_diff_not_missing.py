"""AC-3 (tasks/01M1P9RJVYHTAC087J4B2CAR44/SPEC.md): у задачи НЕ-default
target на итерации 2 diff, собранный `review.review_package` от этой же
базы (sha кодовой ветки предыдущего вердикта), непустой — пакет не несёт
пометку «diff не собран». Требование 1 SPEC: поле `код=` записи «sha
зафиксирован» НЕ-default target несёт уже сегодня (`orchestrator/
store.py::record_fixation`) — этот AC проверяет, что `review.py`
корректно им пользуется, тем же кодом, что и для default target (AC-2).

Красен до реализации: тот же класс сбоя, что и у AC-2 — `previous_verdict_
sha` сегодня берёт базой `sha=` (фиксационный sha артефактного репозитория
target'а), не `код=`. `sha=` этого теста — заведомо НЕ существующий в
репозитории объект (`_sandbox.FOREIGN_FIXATION_SHA`) — `git diff` от него
падает, пакет несёт пометку «diff не собран».
"""
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import review  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import IncrementalDiffSandbox, TASK  # noqa: E402

EXTERNAL_TARGET = "sled"


class ExternalTargetIterationTwoDiffTest(IncrementalDiffSandbox):

    BRANCH = "task/t001-external-target"

    def setUp(self):
        super().setUp()
        self.checkout(self.BRANCH, create=True)

    def test_ac3_diff_between_iterations_is_not_reported_as_uncollected(self):
        """Тот же сценарий, что AC-2 (коммит A — код на момент вердикта
        итерации 1, коммит B — правка по замечаниям), но с записью
        журнала НЕ-default target (`target=sled`) — той формой detail,
        которую `record_fixation` несёт для внешнего target уже сегодня.

        Ловит мутацию: база берётся из `sha=` вместо `код=` — `git diff`
        от заведомо чужого объекта падает, `not_collected` непустой.
        """
        sha_a = self.write_and_commit("module.py", "v1\n", "код v1")
        self.fixate(EXTERNAL_TARGET, code_sha=sha_a)  # in_dev->review, итерация 1
        self.fixate(EXTERNAL_TARGET, code_sha=sha_a)  # review->in_dev, вердикт итерации 1 — база
        sha_b = self.write_and_commit("module.py", "v2 — правка по замечаниям\n",
                                      "код v2 после замечаний")
        self.fixate(EXTERNAL_TARGET, code_sha=sha_b)  # in_dev->review, итерация 2 (текущий)
        self.checkout("main")

        prev_sha = review.previous_verdict_sha(self.conn, TASK)
        self.assertEqual(prev_sha, sha_a, "предпоследняя запись журнала — верная база")

        package = review.review_package(self.conn, TASK, "Внешний target",
                                        self.BRANCH, iteration=2, prev_sha=prev_sha)

        self.assertEqual(package["not_collected"], "",
                         f"пакет: {package['text'][-500:]}")
        self.assertGreater(package["diff_lines"], 0)
        self.assertNotIn("diff не собран", package["text"])


if __name__ == "__main__":
    unittest.main()
