"""Итог задания CI полного набора `ci.job_full_suite` (SPEC
01M5XZSKK8GZTECA2KWAFHE029, требование 2; ANSWER-1, пп. 1-3): свойства,
которых не держат долгоживущие файлы задачи."""
import unittest
from unittest import mock

from orchestrator import ci, forge

SHA = "a" * 40
JOB = "full-suite"


class _Impl:
    """Реализация хостинга: задания и отчёт задаются полями класса."""

    CI_BY_PIPELINE = True
    jobs_seq: list = []
    status = "success"
    outcomes: dict | None = {"m::a": "success", "m::b": "skipped"}

    @classmethod
    def pipeline_status(cls, target, sha):
        jobs = cls.jobs_seq.pop(0) if len(cls.jobs_seq) > 1 else cls.jobs_seq[0]
        return forge.PipelineStatus(forge.GREEN, "", jobs)

    @classmethod
    def job_result(cls, target, sha, job_name):
        return forge.JobResult(cls.status)

    @classmethod
    def job_test_report(cls, target, sha, job_name):
        return forge.TestReport(cls.outcomes)


class _NoReport:
    CI_BY_PIPELINE = True
    pipeline_status = _Impl.pipeline_status
    job_result = _Impl.job_result


class JobFullSuiteTest(unittest.TestCase):

    def setUp(self):
        _Impl.jobs_seq = [[forge.Job(JOB, "success", "test", 7)]]
        _Impl.status = "success"
        _Impl.outcomes = {"m::a": "success", "m::b": "skipped"}
        patcher = mock.patch.object(forge.targets, "target",
                                    return_value={"forge": "gitlab"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def judge(self, impl=_Impl):
        with mock.patch.dict(forge.IMPLEMENTATIONS, {"gitlab": impl}):
            return ci.job_full_suite("proj", SHA, JOB)

    def test_green_counts_tests_of_last_attempt(self):
        """Чистый отчёт `success`/`skipped` у `success` — зелёный, номер и счёт тестов.

        Ловит мутацию: `skipped` считается падением или номер задания не
        берётся — итог не зелёный либо `job_id` пуст.
        """
        res = self.judge()
        self.assertEqual(res.state, ci.JOB_GREEN, res)
        self.assertEqual((res.job_id, res.count), (7, 2))

    def test_unknown_outcome_in_report_is_unknown(self):
        """Исход теста вне `success | failed | skipped | error` — «неизвестно» (ANSWER-1, п. 1).

        Ловит мутацию: непонятный исход (`xpassed`) пропускается как
        непадение — итог зелёный.
        """
        _Impl.outcomes = {"m::a": "success", "m::b": "xpassed"}
        res = self.judge()
        self.assertEqual(res.state, ci.JOB_UNKNOWN, res)
        self.assertIn("xpassed", res.reason)

    def test_restarted_during_read_is_unknown(self):
        """Номер последней попытки сменился между чтениями — «неизвестно» (ANSWER-1, п. 3).

        Ловит мутацию: `pipeline_status` после отчёта не перечитывается —
        статус и отчёт разных попыток дают зелёный итог.
        """
        _Impl.jobs_seq = [[forge.Job(JOB, "success", "test", 7)],
                          [forge.Job(JOB, "success", "test", 7),
                           forge.Job(JOB, "running", "test", 9)]]
        res = self.judge()
        self.assertEqual(res.state, ci.JOB_UNKNOWN, res)
        self.assertIn("перезапущено", res.reason)

    def test_hosting_without_report_is_unknown_at_use(self):
        """Реализация хостинга без `job_test_report` — «неизвестно» с причиной при использовании (ANSWER-1, п. 2).

        Ловит мутацию: отказ `forge` «не реализовано» читается как пустой
        отчёт без падений — итог зелёный.
        """
        res = self.judge(_NoReport)
        self.assertEqual(res.state, ci.JOB_UNKNOWN, res)
        self.assertIn("не реализовано", res.reason)


if __name__ == "__main__":
    unittest.main()
