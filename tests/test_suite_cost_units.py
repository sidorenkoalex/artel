"""Unit cases for the junit time report outside the GitHub path."""

import io
import unittest
import zipfile
from unittest import mock

from orchestrator import ci, forge


def junit_zip(xml: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("report.xml", xml.encode("utf-8"))
    return buf.getvalue()


def suite(case_time: str, suite_time: str = "1.0") -> str:
    return (f'<testsuites><testsuite tests="1" time="{suite_time}">'
            f'<testcase classname="pkg.Case" name="test_a" time="{case_time}"/>'
            f'</testsuite></testsuites>')


class ParseJunitTimesTest(unittest.TestCase):
    def test_non_finite_time_is_refused(self):
        """Ловит мутацию: `float("nan")`/`inf` в атрибуте `time` принят как
        время теста — сумма и доли сводки становятся `nan`."""
        for value in ("nan", "inf", "-inf"):
            for data in (junit_zip(suite(value)), junit_zip(suite("0.5", value))):
                times, seconds, reason = forge.parse_junit_times(data)
                self.assertIsNone(times, value)
                self.assertIsNone(seconds, value)
                self.assertIn("time", reason)

    def test_dtd_and_repeated_key_are_refused(self):
        """Ловит мутацию: разбор времени не повторяет отказы разбора исходов —
        отчёт с DTD разобран или повтор ключа узла молча перезаписан."""
        dtd = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]>' + suite("1")
        twice = suite("1").replace(
            "</testsuite>",
            '<testcase classname="pkg.Case" name="test_a" time="2"/></testsuite>')
        for xml, word in ((dtd, "DTD"), (twice, "больше одного раза")):
            times, seconds, reason = forge.parse_junit_times(junit_zip(xml))
            self.assertEqual((times, seconds), (None, None))
            self.assertIn(word, reason)


class NonGithubHostingTest(unittest.TestCase):
    def test_ci_suite_report_and_last_commit_refuse_without_gh(self):
        """Ловит мутацию: `ci_suite_report`/`last_executed_commit` зовут `gh`
        у проекта, чей хостинг их не реализует, вместо отказа с причиной."""
        with mock.patch.object(forge, "_hosting", return_value=("gitlab", "")), \
                mock.patch.object(ci, "gh", side_effect=AssertionError("gh")), \
                mock.patch.object(ci, "gh_bytes",
                                  side_effect=AssertionError("gh_bytes")):
            report = forge.ci_suite_report("proj", "a" * 40)
            latest = forge.last_executed_commit("proj", "main", ci.FULL_SUITE_JOB)
        self.assertEqual(report[:3], (None, None, None))
        self.assertIn("не реализовано для gitlab", report[3])
        self.assertIsNone(latest[0])
        self.assertIn("не реализовано для gitlab", latest[1])


if __name__ == "__main__":
    unittest.main()
