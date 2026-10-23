"""Юнит-тесты причины «сервер» и повтора `git push` ссылки документов
(orchestrator/artifact_branch.py, SPEC 01M5K11D3284ZZGRHN39FGQVF2,
требования 1-2). Без git и БД: ответ `git push` — подменённый модульный
`_git`, пауза — ссылка модуля `time` (`TimeWithSleep`).
"""
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import artifact_branch
from tests.sandbox import TimeWithSleep

SERVER_FAILED = (" ! [remote rejected] refs/artifacts/x -> refs/artifacts/x "
                 "(failed)\nerror: failed to push some refs")
FAILED_TO_UPDATE = (" ! [remote rejected] refs/artifacts/x -> "
                    "refs/artifacts/x (failed to update ref)")


class ClassifyServerTest(unittest.TestCase):

    def classify(self, stderr):
        return artifact_branch._classify_push_failure(stderr)

    def test_failed_word_must_close_rejection_line(self):
        """`(failed)` в конце строки `[remote rejected]` — «сервер», в
        середине строки или как `(failed to update ref)` — нет.

        Ловит мутацию: признак `(failed)` ищется подстрокой `(failed` без
        закрывающей скобки или без привязки к концу строки — `(failed to
        update ref)` уходит в «сервер»."""
        self.assertEqual(self.classify(SERVER_FAILED),
                         artifact_branch.PUSH_REASON_SERVER)
        self.assertEqual(self.classify(FAILED_TO_UPDATE),
                         artifact_branch.PUSH_REASON_NON_FAST_FORWARD)
        self.assertEqual(
            self.classify(" ! [remote rejected] a -> a (failed) hook said no"),
            artifact_branch.PUSH_REASON_NON_FAST_FORWARD)

    def test_server_signs_are_case_insensitive_and_beat_remote_rejected(self):
        """`INTERNAL SERVER ERROR` при `[remote rejected]` — «сервер»:
        признаки (б) старше прочего `rejected` (в), регистр не важен.

        Ловит мутацию: проверка «любой rejected» стоит раньше признаков
        сервера, либо признаки сравниваются без приведения регистра."""
        stderr = ("remote: INTERNAL SERVER ERROR\n ! [remote rejected] a -> a "
                  "(Internal Server Error)")
        self.assertEqual(self.classify(stderr),
                         artifact_branch.PUSH_REASON_SERVER)

    def test_non_5xx_http_code_is_network(self):
        """HTTP 4xx — не «сервер»: признак — только код 5xx.

        Ловит мутацию: признак HTTP-кода принимает любой код (`HTTP \\d\\d\\d`)
        — `returned error: 403` становится «сервер» и повторяется."""
        self.assertEqual(
            self.classify("fatal: unable to access 'x': The requested URL "
                          "returned error: 403"),
            artifact_branch.PUSH_REASON_NETWORK)


class AttemptPushRetryTest(unittest.TestCase):

    def run_attempts(self, answers, attempts_cap=None):
        calls = []

        def fake_git(repo, *args):
            calls.append(args)
            code, stderr = answers[min(len(calls), len(answers)) - 1]
            return subprocess.CompletedProcess(args, code, "", stderr)

        sleep = mock.Mock()
        patches = [
            mock.patch.object(artifact_branch, "_git", fake_git),
            mock.patch.object(artifact_branch.gitcmd, "has_no_remote",
                              return_value=False),
            mock.patch.object(artifact_branch, "time", TimeWithSleep(sleep)),
        ]
        if attempts_cap is not None:
            patches.append(mock.patch.object(
                artifact_branch, "PUSH_SERVER_RETRY_ATTEMPTS", attempts_cap))
        for p in patches:
            p.start()
        try:
            result = artifact_branch._attempt_push("refs/artifacts/x",
                                                   Path("/nonexistent"))
        finally:
            for p in reversed(patches):
                p.stop()
        return result, calls, sleep

    def test_attempt_count_is_returned_and_cap_read_at_call_time(self):
        """«Сервер» на всех попытках при потолке 4: четыре вызова, три
        паузы, возврат несёт причину «сервер» и число попыток 4.

        Ловит мутацию: потолок попыток зашит дефолтом аргумента или
        числом 3 — подменённая константа модуля не действует; либо
        возвращается не число вызовов, а номер паузы."""
        (ok, reason, stderr, attempts), calls, sleep = self.run_attempts(
            [(1, SERVER_FAILED)], attempts_cap=4)
        self.assertFalse(ok)
        self.assertEqual(reason, artifact_branch.PUSH_REASON_SERVER)
        self.assertEqual(stderr, SERVER_FAILED.strip())
        self.assertEqual(attempts, 4)
        self.assertEqual(len(calls), 4)
        self.assertEqual(sleep.call_count, 3)

    def test_server_then_other_reason_stops_retry(self):
        """«Сервер», затем отказ хука: повтор прекращается на второй
        попытке, причина — последнего ответа (non-fast-forward).

        Ловит мутацию: повтор продолжается до потолка независимо от причины
        следующего ответа, либо возвращается причина первого ответа."""
        (ok, reason, _stderr, attempts), calls, sleep = self.run_attempts(
            [(1, SERVER_FAILED),
             (1, " ! [remote rejected] a -> a (pre-receive hook declined)")])
        self.assertFalse(ok)
        self.assertEqual(reason, artifact_branch.PUSH_REASON_NON_FAST_FORWARD)
        self.assertEqual(attempts, 2)
        self.assertEqual(len(calls), 2)
        self.assertEqual(sleep.call_count, 1)

    def test_first_success_is_one_attempt(self):
        """Успех с первого раза: одна попытка, без паузы.

        Ловит мутацию: счёт попыток начинается с нуля после вызова (успех
        с первого раза — `0`), и `_send` пишет «попыток» на каждом успехе."""
        (ok, _reason, _stderr, attempts), calls, sleep = self.run_attempts(
            [(0, "")])
        self.assertTrue(ok)
        self.assertEqual(attempts, 1)
        self.assertEqual(len(calls), 1)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
