"""Предел процессов шага роли: формула, чтение источников, строка doctor
(SPEC 01M6KB0FS809DG55K9A20CYKJE, требования 1-3, 6)."""
import resource
import subprocess
import unittest
from unittest import mock

from orchestrator import config, doctor, runner

INF = resource.RLIM_INFINITY


def _rlimit(soft, hard):
    real = resource.getrlimit

    def fake(which):
        return (soft, hard) if which == resource.RLIMIT_NPROC else real(which)

    return mock.patch.object(resource, "getrlimit", fake)


def _completed(rc: int, out: str):
    return mock.patch.object(
        subprocess, "run",
        return_value=subprocess.CompletedProcess(["x"], rc, out, ""))


class RoleNprocLimitTest(unittest.TestCase):

    def test_min_takes_finite_pult_limits_only(self):
        """Предел — min(V − запас, конечные пределы пульта).

        Ловит мутацию: из min выпал жёсткий предел пульта (берётся только
        мягкий) — при мягком бесконечном и жёстком 500 результат
        V − запас вместо 500.
        """
        value = config.ROLE_NPROC_RESERVE + 5000
        with mock.patch.object(runner, "_read_maxprocperuid",
                               return_value=(value, "ok")):
            with _rlimit(INF, 500):
                self.assertEqual(runner.role_nproc_limit(), 500)
            with _rlimit(700, INF):
                self.assertEqual(runner.role_nproc_limit(), 700)
            with _rlimit(INF, INF):
                self.assertEqual(runner.role_nproc_limit(),
                                 value - config.ROLE_NPROC_RESERVE)

    def test_non_darwin_is_absent_without_subprocess(self):
        """Не macOS — исход `(None, "absent")`, `sysctl` не зовётся.

        Ловит мутацию: проверка платформы снята — на Linux `sysctl` зовётся
        и сбой даёт "failed" (лишнее предупреждение в журнале шага на CI).
        """
        with mock.patch.object(runner.sys, "platform", "linux"), \
                mock.patch.object(subprocess, "run",
                                  side_effect=AssertionError("sysctl")):
            self.assertEqual(runner._read_maxprocperuid(), (None, "absent"))

    def test_darwin_reads_number_and_fails_on_error_code(self):
        """macOS: число из вывода — "ok"; ненулевой код — "failed".

        Ловит мутацию: код возврата `sysctl` не проверяется — вывод
        ошибочного вызова разбирается как значение либо ValueError уходит
        наружу.
        """
        with mock.patch.object(runner.sys, "platform", "darwin"):
            with _completed(0, "4000\n"):
                self.assertEqual(runner._read_maxprocperuid(), (4000, "ok"))
            with _completed(1, "4000\n"):
                self.assertEqual(runner._read_maxprocperuid(), (None, "failed"))

    def test_process_count_counts_pid_lines_and_raises_on_error(self):
        """`ps` с тремя pid — 3; ненулевой код — исключение, не ноль.

        Ловит мутацию: код возврата `ps` не проверяется — частичный вывод
        упавшего `ps` засчитывается как полный счёт процессов.
        """
        with _completed(0, "  1\n 22\n333\n"):
            self.assertEqual(runner._user_process_count(), 3)
        with _completed(1, "1\n2\n"), self.assertRaises(Exception):
            runner._user_process_count()


class RoleNprocDoctorTest(unittest.TestCase):

    def check(self, count=None, error=None, maxproc=(5000, "ok")):
        counter = (mock.patch.object(runner, "_user_process_count",
                                     side_effect=error)
                   if error is not None else
                   mock.patch.object(runner, "_user_process_count",
                                     return_value=count))
        with mock.patch.object(runner, "_read_maxprocperuid",
                               return_value=maxproc), _rlimit(INF, INF), counter:
            return doctor.check_role_nproc()

    def test_status_against_step_limit(self):
        """N ≥ M — warn, N < M — ok; в тексте значение, предел и счёт.

        Ловит мутацию: строка сравнивает счёт с kern.maxprocperuid, а не с
        пределом шага — при N = M (между M и V) строка ok.
        """
        limit = 5000 - config.ROLE_NPROC_RESERVE
        warn = self.check(count=limit)
        self.assertEqual(warn.status, "warn")
        for text in ("5000", str(limit)):
            self.assertIn(text, warn.detail)
        self.assertEqual(self.check(count=limit - 1).status, "ok")

    def test_count_failure_is_warn_with_mark(self):
        """Сбой счёта — warn с пометкой «счёт недоступен», doctor цел.

        Ловит мутацию: исключение счёта не ловится — `check_role_nproc`
        падает RuntimeError.
        """
        row = self.check(error=RuntimeError("ps не ответил"))
        self.assertEqual(row.status, "warn")
        self.assertIn("счёт недоступен", row.detail)

    def test_absent_maxproc_is_ok_with_default_mark(self):
        """kern.maxprocperuid нет — ok, «недоступен» и «значение по умолчанию».

        Ловит мутацию: пометка ставится только на исход "failed" — у
        "absent" её нет.
        """
        row = self.check(count=1, maxproc=(None, "absent"))
        self.assertEqual(row.status, "ok")
        self.assertIn("недоступен", row.detail)
        self.assertIn("значение по умолчанию", row.detail)


if __name__ == "__main__":
    unittest.main()
