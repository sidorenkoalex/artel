"""AC-2 (tasks/01M1P9RJVYHTAC087J4B2CAR44/SPEC.md): у задачи target по
умолчанию (`config.DEFAULT_TARGET`) на итерации 2 diff, собранный
`review.review_package` от базы «sha кодовой ветки предыдущего вердикта»
(`review.previous_verdict_sha`), непустой, когда между итерациями были
правки кода — пакет не несёт пометку «diff не собран».

Красен до реализации: `review.previous_verdict_sha` сегодня берёт базой
поле `sha=` записи журнала (фиксационный sha артефактного/фиксационного
репозитория target'а — требование 4 SPEC называет его НЕПРАВИЛЬНОЙ
базой), не `код=` (sha кодовой ветки). `sha=` этого теста — синтаксически
валидный, но заведомо НЕ существующий в репозитории объект (см.
`_sandbox.FOREIGN_FIXATION_SHA`, воспроизводит реальный класс сбоя из
SPEC «Контекст»: sha ЧУЖОГО репозитория, `git diff` отвечает «bad
revision»/«Invalid symmetric difference expression»). Пока
`previous_verdict_sha` подставляет его как базу — `git diff` в РЕАЛЬНОМ
репозитории песочницы падает, и пакет несёт пометку «diff не собран».
"""
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import config, review  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import IncrementalDiffSandbox, TASK  # noqa: E402


class DefaultTargetIterationTwoDiffTest(IncrementalDiffSandbox):

    BRANCH = "task/t001-default-target"

    def setUp(self):
        super().setUp()
        self.checkout(self.BRANCH, create=True)

    def test_ac2_diff_between_iterations_is_not_reported_as_uncollected(self):
        """Кодовая ветка задачи (default target) получает коммит A (код
        на момент вердикта итерации 1), затем коммит B (правка по
        замечаниям, итерация 2) — `review.review_package` итерации 2
        обязан собрать diff между A и B: непустой, без пометки «diff не
        собран».

        Ловит мутацию: база берётся из поля `sha=` (фиксационный sha
        артефактного репозитория, заведомо чужой объект в этом
        репозитории) — `git diff` падает, `not_collected` непустой,
        `diff_lines == 0`.
        """
        sha_a = self.write_and_commit("module.py", "v1\n", "код v1")
        self.fixate(config.DEFAULT_TARGET, code_sha=sha_a)  # in_dev->review, итерация 1
        self.fixate(config.DEFAULT_TARGET, code_sha=sha_a)  # review->in_dev, вердикт итерации 1 — искомая база
        sha_b = self.write_and_commit("module.py", "v2 — правка по замечаниям\n",
                                      "код v2 после замечаний")
        self.fixate(config.DEFAULT_TARGET, code_sha=sha_b)  # in_dev->review, итерация 2 (текущий)
        self.checkout(config.MAIN_BRANCH)

        prev_sha = review.previous_verdict_sha(self.conn, TASK)
        self.assertEqual(prev_sha, sha_a, "предпоследняя запись журнала — верная база")

        package = review.review_package(self.conn, TASK, "Дефолт-target",
                                        self.BRANCH, iteration=2, prev_sha=prev_sha)

        self.assertEqual(package["not_collected"], "",
                         f"пакет: {package['text'][-500:]}")
        self.assertGreater(package["diff_lines"], 0)
        self.assertNotIn("diff не собран", package["text"])


if __name__ == "__main__":
    unittest.main()
