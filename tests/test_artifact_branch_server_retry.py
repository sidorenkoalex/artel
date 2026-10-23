"""Юнит-тесты причины «сервер» и повтора `git push` ссылки документов
(orchestrator/artifact_branch.py, SPEC 01M5K11D3284ZZGRHN39FGQVF2,
требования 1-2). Без git и БД: ответ `git push` — подменённый модульный
`_git`, пауза — ссылка модуля `time` (`TimeWithSleep`).
"""
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import artifact_branch, store
from tests.sandbox import SchemaSeededTmpRootTest, TimeWithSleep

PUSH_OK = "push артефактной ветки"
PUSH_FAILED = "push артефактной ветки FAILED"
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

    def test_pause_uses_module_constant(self):
        """Пауза между попытками — `PUSH_SERVER_RETRY_PAUSE_SEC`, подменённое
        значение модуля действует в момент вызова.

        Ловит мутацию: пауза зашита числом (`time.sleep(1)` или `5`) вместо
        константы модуля."""
        with mock.patch.object(artifact_branch,
                               "PUSH_SERVER_RETRY_PAUSE_SEC", 7):
            _result, _calls, sleep = self.run_attempts(
                [(1, SERVER_FAILED), (0, "")])
        sleep.assert_called_once_with(7)


class ClassifyServerSignsTest(unittest.TestCase):

    def classify(self, stderr):
        return artifact_branch._classify_push_failure(stderr)

    def test_http_5xx_is_server(self):
        """`HTTP 502` и `returned error: 503` — «сервер» (до задачи — «сеть»).

        Ловит мутацию: из признаков сервера убраны шаблоны `http 5\\d\\d`
        или `returned error: 5\\d\\d` — код 5xx уходит в «сеть» без повтора."""
        self.assertEqual(self.classify("error: RPC failed; HTTP 502 curl 22"),
                         artifact_branch.PUSH_REASON_SERVER)
        self.assertEqual(
            self.classify("fatal: unable to access 'x': The requested URL "
                          "returned error: 503"),
            artifact_branch.PUSH_REASON_SERVER)

    def test_commit_refs_fatal_is_server(self):
        """`fatal error in commit_refs` при `(failure)` — «сервер».

        Ловит мутацию: признак `fatal error in commit_refs` убран — строка
        уходит в non-fast-forward по прочему `rejected`."""
        self.assertEqual(
            self.classify("remote: fatal error in commit_refs\n ! [remote "
                          "rejected] a -> a (failure)"),
            artifact_branch.PUSH_REASON_SERVER)

    def test_local_reject_beats_server_signs(self):
        """`[rejected] … (fetch first)` вместе с `Internal Server Error` —
        non-fast-forward: признаки (а) старше признаков сервера (б).

        Ловит мутацию: признаки сервера проверяются раньше локального
        отказа git — расхождение истории повторяется как ответ сервера."""
        self.assertEqual(
            self.classify("remote: Internal Server Error\n ! [rejected] a -> a "
                          "(fetch first)"),
            artifact_branch.PUSH_REASON_NON_FAST_FORWARD)


class SendJournalTest(SchemaSeededTmpRootTest):
    """`_send` в песочнице БД: ответ `git push` — подменённый `_git`, origin
    «настроен» (`remote get-url` отвечает адресом), пауза — заместитель."""

    def send(self, answers):
        pushes = []

        def fake_git(repo, *args):
            if args[:2] == ("remote", "get-url"):
                return subprocess.CompletedProcess(args, 0, "url\n", "")
            if args and args[0] == "push":
                pushes.append(args)
                code, stderr = answers[min(len(pushes), len(answers)) - 1]
                return subprocess.CompletedProcess(args, code, "", stderr)
            return subprocess.CompletedProcess(args, 0, "sha\n", "")

        with mock.patch.object(artifact_branch, "_git", fake_git), \
                mock.patch.object(artifact_branch.gitcmd, "has_no_remote",
                                  return_value=False), \
                mock.patch.object(artifact_branch.gitcmd, "branch_head_sha",
                                  return_value="aaa"), \
                mock.patch.object(artifact_branch.gitcmd, "remote_branch_sha",
                                  return_value="bbb"), \
                mock.patch.object(artifact_branch, "time",
                                  TimeWithSleep(mock.Mock())):
            return artifact_branch._send(self.TASK, Path("/nonexistent"))

    def push_steps(self):
        return [(r["action"], r["detail"])
                for r in store.task_steps(store.db(), self.TASK)
                if r["action"] in (PUSH_OK, PUSH_FAILED)]

    def test_server_failure_detail_names_attempts_without_merge_advice(self):
        """«Сервер» на всех попытках: одна запись FAILED с деталью
        `сервер (попыток 3): …`, без совета свести историю и без пары sha.

        Ловит мутацию: отказ «сервер» журналируется веткой non-fast-forward
        или общей (`сервер: …`) — без числа попыток либо с советом
        «свести merge-коммитом» и sha."""
        self.assertFalse(self.send([(1, SERVER_FAILED)]))
        steps = self.push_steps()
        self.assertEqual(len(steps), 1)
        action, detail = steps[0]
        self.assertEqual(action, PUSH_FAILED)
        self.assertTrue(detail.startswith("сервер (попыток 3): "), detail)
        self.assertNotIn("merge-коммитом", detail)
        self.assertNotIn("aaa", detail)
        self.assertNotIn("bbb", detail)

    def test_success_after_retry_names_attempts(self):
        """«Сервер», затем успех: одна запись успеха с `попыток 2`, FAILED нет.

        Ловит мутацию: `_send` журналирует успех только после записанного
        отказа (условие `attempts > 1` снято) или без числа попыток."""
        self.assertTrue(self.send([(1, SERVER_FAILED), (0, "")]))
        steps = self.push_steps()
        self.assertEqual([a for a, _ in steps], [PUSH_OK])
        self.assertIn("попыток 2", steps[0][1])

    def test_success_after_journaled_failure_is_journaled(self):
        """Отказ «сеть», затем успех следующей отправки — запись успеха есть;
        ещё один успех следом — новой записи нет.

        Ловит мутацию: из условия `_send` убрано чтение последнего исхода
        отправки (`_last_send_failed`) — досылка после отказа не видна в
        журнале; либо успех пишется всегда."""
        self.assertFalse(self.send([(1, "fatal: Could not resolve host: x")]))
        self.assertTrue(self.send([(0, "")]))
        self.assertTrue(self.send([(0, "")]))
        self.assertEqual([a for a, _ in self.push_steps()],
                         [PUSH_FAILED, PUSH_OK])

    def test_two_successes_without_failure_are_silent(self):
        """Две успешные отправки без отказа перед ними — записей нет.

        Ловит мутацию: `_send` журналирует каждый успех."""
        self.assertTrue(self.send([(0, "")]))
        self.assertTrue(self.send([(0, "")]))
        self.assertEqual(self.push_steps(), [])


if __name__ == "__main__":
    unittest.main()
