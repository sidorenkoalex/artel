"""Отправка ссылки документов задачи: причина «сервер» с повтором, запись
отказа и успеха, снятие `send_pending` (`orchestrator/artifact_branch.py`).

Группа: разовый

Группа разовая не по смыслу, а по правилу guard: импорт `orchestrator.artifact_branch`/`orchestrator.gitcmd` в долгоживущем файле — признак «git-модуль» (`scripts/guard.py::_GIT_MODULES`), а предмет критериев — именно этот модуль.

Красен до реализации: в `artifact_branch` нет `PUSH_REASON_SERVER`,
`PUSH_SERVER_RETRY_ATTEMPTS`, `PUSH_SERVER_RETRY_PAUSE_SEC` и повтора — ответ сервера пишется как non-fast-forward или «сеть» после одного `git push`, успех после отказа не журналируется, `send_pending` ещё есть; критерии прежнего поведения (AC-3, AC-5, AC-10, AC-12) и отсутствие силы при отправке (AC-11) зелены и до правки.

Связка, которую держат тесты: узел записи `artifact_branch.commit_files` —
отправка в `origin` — журнал задачи. Пульт — настоящий git с bare
`origin` (`tests.sandbox.AutoOriginSandbox`); ответ `git push` подменяется
на уровне `gitcmd.git` (остальные вызовы git идут в настоящий git), пауза
повтора — ссылкой модуля `artifact_branch.time` (`TimeWithSleep`, без
глобальной подмены `time.sleep`). Классификация наблюдается по детали
записи «push артефактной ветки FAILED»: она начинается с причины.
"""
import io
import random
import re
import subprocess
import unittest
from pathlib import Path, PurePosixPath
from unittest import mock

from orchestrator import artifact_branch, config, gitcmd, store
from tests.sandbox import AutoOriginSandbox, TimeWithSleep, strip_dash_c

PUSH_OK = "push артефактной ветки"
PUSH_FAILED = "push артефактной ветки FAILED"
SERVER = "сервер"

SEED = random.randrange(1 << 30)
print(f"зерно: {SEED}")
RNG = random.Random(SEED)

REF = "refs/artifacts/01UNITPUSHSERVER0001"
TAIL = "error: failed to push some refs to 'origin'"


def noise() -> str:
    """Случайная строка-примесь перед ответом git: признаки причины ищутся
    по всему `stderr`, не по его началу."""
    return f"remote: обработка {RNG.randrange(10 ** 6)} объектов"


ISE = (f"{noise()}\nremote: Internal Server Error\nTo origin\n"
       f" ! [remote rejected] {REF} -> {REF} (Internal Server Error)\n{TAIL}")
REMOTE_FAILED = f"To origin\n ! [remote rejected] {REF} -> {REF} (failed)\n{TAIL}"
COMMIT_REFS = (f"remote: fatal error in commit_refs\nTo origin\n"
               f" ! [remote rejected] {REF} -> {REF} (failure)\n{TAIL}")
HTTP_503 = ("fatal: unable to access 'origin': The requested URL returned "
            "error: 503")
HTTP_502 = "error: RPC failed; HTTP 502\nfatal: the remote end hung up unexpectedly"
FETCH_FIRST = (f"To origin\n ! [rejected]        {REF} -> {REF} (fetch first)\n"
               f"{TAIL}\nhint: Updates were rejected because the remote "
               f"contains work that you do\nhint: not have locally. This is "
               f"usually caused by another repository pushing\nhint: to the "
               f"same ref. If you want to integrate the remote changes,\n"
               f"hint: use 'git pull' before pushing again.\nhint: See the "
               f"'Note about fast-forwards' in 'git push --help' for details.")
HOOK = (f"To origin\n ! [remote rejected] {REF} -> {REF} "
        f"(pre-receive hook declined)\n{TAIL}")
FAILED_TO_UPDATE = (f"To origin\n ! [remote rejected] {REF} -> {REF} "
                    f"(failed to update ref)\n{TAIL}")
FAILURE = f"To origin\n ! [remote rejected] {REF} -> {REF} (failure)\n{TAIL}"
NETWORK = ("fatal: unable to access 'origin': Could not resolve host: "
           "origin-host")

SHA_PATTERN = re.compile(r"\b[0-9a-f]{40}\b")


class ScriptedPush:
    """Подмена `gitcmd.git`: вызов `push` получает очередной ответ сценария
    (`None` — настоящий push в bare `origin`, строка — отказ с этим
    `stderr`; ответы кончились — повторяется последний), остальные вызовы
    git идут в настоящий git. `events` — порядок отправок и пауз."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.push_calls = []
        self.pauses = []
        self.events = []
        self.real_git = gitcmd.git

    def git(self, *args, **kwargs):
        stripped = strip_dash_c(args)
        if stripped[:1] != ("push",):
            return self.real_git(*args, **kwargs)
        self.push_calls.append(tuple(stripped))
        self.events.append("push")
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if answer is None:
            return self.real_git(*args, **kwargs)
        return subprocess.CompletedProcess(list(args), 1, "", answer)

    def sleep(self, seconds):
        self.pauses.append(seconds)
        self.events.append("sleep")


class PushServerSandbox(AutoOriginSandbox):
    """Задача артели `TASK` в `in_dev` с одним коммитом в ссылке документов,
    уже отправленным в `origin` (журнал отправок пуст)."""

    TASK = "01UNITPUSHSERVER0001"

    def setUp(self):
        super().setUp()
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          f"task/{self.TASK.lower()}-x", config.DEFAULT_TARGET,
                          25.0)
        self.ref = artifact_branch.branch_name(self.TASK)
        self.repo = artifact_branch.task_repo(self.TASK)
        self.counter = 0
        self.assertTrue(self.commit(), "предусловие: первый коммит ссылки")
        self.assertEqual(self.push_rows(), [], "предусловие: журнал отправок пуст")

    def doc_path(self, name: str) -> str:
        passport = artifact_branch.PASSPORT_REL_TMPL.format(task_id=self.TASK)
        return str(PurePosixPath(passport).with_name(name))

    def commit(self) -> str:
        self.counter += 1
        return artifact_branch.commit_files(
            self.TASK, {self.doc_path("SPEC.md"): f"спека {self.counter}\n"},
            f"{self.TASK}: правка {self.counter}")

    def scripted_commit(self, *answers, attempts=None) -> ScriptedPush:
        """Коммит ссылки, чья отправка получает ответы `answers`; `attempts`
        — подменённый потолок попыток повтора (`None` — как в модуле)."""
        script = ScriptedPush(answers)
        with mock.patch.object(gitcmd, "git", side_effect=script.git), \
                mock.patch.object(artifact_branch, "time",
                                  TimeWithSleep(script.sleep), create=True):
            if attempts is None:
                self.commit()
            else:
                with mock.patch.object(artifact_branch,
                                       "PUSH_SERVER_RETRY_ATTEMPTS", attempts,
                                       create=True):
                    self.commit()
        return script

    def push_rows(self) -> list:
        return [r for r in store.task_steps(store.db(), self.TASK)
                if r["action"] in (PUSH_OK, PUSH_FAILED)]

    def failed_details(self) -> list:
        return [r["detail"] for r in self.push_rows() if r["action"] == PUSH_FAILED]

    def success_details(self) -> list:
        return [r["detail"] for r in self.push_rows() if r["action"] == PUSH_OK]

    def assert_reason(self, stderr: str, reason: str) -> ScriptedPush:
        """Отказ с `stderr` на всех попытках записан причиной `reason`."""
        before = len(self.failed_details())
        script = self.scripted_commit(stderr)
        details = self.failed_details()[before:]
        self.assertEqual(len(details), 1,
                         f"зерно {SEED}: ровно одна запись отказа: {details}")
        self.assertTrue(details[0].startswith(reason),
                        f"зерно {SEED}: ждали причину «{reason}», деталь "
                        f"«{details[0]}», stderr «{stderr}»")
        return script

    def assert_single_push_no_pause(self, script: ScriptedPush) -> None:
        self.assertEqual(len(script.push_calls), 1,
                         f"зерно {SEED}: {script.push_calls}")
        self.assertEqual(script.pauses, [], f"зерно {SEED}")


class ServerClassificationTest(PushServerSandbox):

    def test_ac1_internal_server_error_is_server(self):
        """Ответ `remote: Internal Server Error … [remote rejected] …
        (Internal Server Error)` записан причиной «сервер», константа
        причины — «сервер».

        Ловит мутацию: `[remote rejected]` проверяется раньше признаков
        сервера (порядок (в) перед (б)) — деталь отказа начинается с
        «non-fast-forward» и несёт совет свести историю.
        """
        self.assertEqual(getattr(artifact_branch, "PUSH_REASON_SERVER", None),
                         SERVER)
        self.assert_reason(ISE, SERVER)

    def test_ac2_remote_failed_and_commit_refs_are_server(self):
        """`[remote rejected] … (failed)` и `fatal error in commit_refs …
        (failure)` записаны причиной «сервер».

        Ловит мутацию: признак `(failed)` или `fatal error in commit_refs`
        пропущен в наборе (б) — деталь отказа начинается с
        «non-fast-forward».
        """
        for stderr in (REMOTE_FAILED, COMMIT_REFS):
            with self.subTest(stderr=stderr):
                self.assert_reason(stderr, SERVER)

    def test_ac4_http_5xx_is_server(self):
        """`The requested URL returned error: 503` и `RPC failed; HTTP 502`
        записаны причиной «сервер», не «сеть».

        Ловит мутацию: признак кода HTTP 5xx не добавлен (или ищется только
        одна из форм `HTTP 5\\d\\d`/`returned error: 5\\d\\d`) — деталь
        отказа начинается с «сеть».
        """
        for stderr in (HTTP_503, HTTP_502):
            with self.subTest(stderr=stderr):
                self.assert_reason(stderr, SERVER)


class NonFastForwardKeptTest(PushServerSandbox):

    def test_ac3_fetch_first_and_hook_declined_are_non_fast_forward(self):
        """`[rejected] … (fetch first)` записан прежней деталью побайтно (пара
        sha, совет «свести merge-коммитом»); `[remote rejected] …
        (pre-receive hook declined)` — non-fast-forward; оба — одна
        отправка без паузы.

        Ловит мутацию: деталь non-fast-forward перестроена общим форматом
        «сервер (попыток N)» (или обрезка stderr сменилась) — запись не
        совпадает с прежней побайтно; либо повтор идёт для любой причины —
        `git push` вызван больше одного раза, пауза вызвана.
        """
        nff = artifact_branch.PUSH_REASON_NON_FAST_FORWARD
        script = self.scripted_commit(FETCH_FIRST)
        local = gitcmd.branch_head_sha(self.ref, repo=self.repo)
        origin = gitcmd.remote_branch_sha(self.ref, repo=self.repo)
        self.assertNotEqual(local, origin, "предусловие: коммит не отправлен")
        expected = (f"{nff}: {FETCH_FIRST[:300]}; локальный sha {local}, "
                    f"origin sha {origin} — свести merge-коммитом")
        self.assertEqual(self.failed_details(), [expected])
        self.assert_single_push_no_pause(script)

        script = self.assert_reason(HOOK, nff)
        self.assert_single_push_no_pause(script)

    def test_ac5_local_rejection_outranks_server_signs(self):
        """В `stderr` есть и `[rejected] … (fetch first)`, и `Internal Server
        Error` — записан non-fast-forward.

        Ловит мутацию: признаки сервера (б) проверяются раньше локального
        отказа (а) — деталь начинается с «сервер», отправка повторяется.
        """
        stderr = f"{FETCH_FIRST}\nremote: Internal Server Error"
        script = self.assert_reason(
            stderr, artifact_branch.PUSH_REASON_NON_FAST_FORWARD)
        self.assert_single_push_no_pause(script)

    def test_ac12_failed_to_update_ref_and_failure_are_not_server(self):
        """`[remote rejected] … (failed to update ref)` и `[remote rejected]
        … (failure)` без иных признаков сервера — non-fast-forward, одна
        отправка без паузы.

        Ловит мутацию: признак `(failed)` ищется подстрокой `(fail` или
        `failed` без скобки в конце — деталь начинается с «сервер»,
        `git push` вызван несколько раз, пауза вызвана.
        """
        for stderr in (FAILED_TO_UPDATE, FAILURE):
            with self.subTest(stderr=stderr):
                script = self.assert_reason(
                    stderr, artifact_branch.PUSH_REASON_NON_FAST_FORWARD)
                self.assert_single_push_no_pause(script)


class NetworkNotRetriedTest(PushServerSandbox):

    def test_ac10_network_failure_is_sent_once_without_pause(self):
        """`Could not resolve host` — причина «сеть», `git push` вызван ровно
        один раз, пауза не вызвана.

        Ловит мутацию: повтор идёт для любой причины, кроме
        non-fast-forward, — `git push` вызван `PUSH_SERVER_RETRY_ATTEMPTS`
        раз, пауза вызвана.
        """
        script = self.assert_reason(NETWORK, artifact_branch.PUSH_REASON_NETWORK)
        self.assert_single_push_no_pause(script)


class ServerRetryTest(PushServerSandbox):

    def assert_no_force(self, script: ScriptedPush) -> None:
        self.assertTrue(script.push_calls)
        for call in script.push_calls:
            for arg in call[1:]:
                self.assertNotEqual(arg, "--force", call)
                self.assertFalse(arg.startswith("--force-with-lease"), call)
                self.assertFalse(arg.startswith("+"), call)

    def test_ac6_server_then_success_sends_twice_with_one_pause(self):
        """«Сервер», затем успех: две отправки, одна пауза длиной
        `PUSH_SERVER_RETRY_PAUSE_SEC` (5); в журнале запись успеха, записи
        отказа нет, ссылка в `origin` равна локальной.

        Ловит мутацию: `_send` журналирует отказ первой попытки до повтора
        (или не повторяет вовсе) — в журнале появляется «push артефактной
        ветки FAILED»; либо пауза зовётся без аргумента константы.
        """
        self.assertEqual(getattr(artifact_branch, "PUSH_SERVER_RETRY_PAUSE_SEC",
                                 None), 5)
        script = self.scripted_commit(ISE, None)
        self.assertEqual(len(script.push_calls), 2, script.push_calls)
        self.assertEqual(script.pauses,
                         [artifact_branch.PUSH_SERVER_RETRY_PAUSE_SEC])
        self.assertEqual(self.failed_details(), [])
        self.assertTrue(self.success_details(), self.push_rows())
        self.assertEqual(gitcmd.remote_branch_sha(self.ref, repo=self.repo),
                         gitcmd.branch_head_sha(self.ref, repo=self.repo))

    def test_ac7_server_on_every_attempt_is_one_failure_record(self):
        """«Сервер» на всех попытках: `git push` вызван
        `PUSH_SERVER_RETRY_ATTEMPTS` (3) раз, одна запись отказа
        `сервер (попыток N): …` без совета свести историю и без пары sha;
        при подменённом случайном потолке N равно ему.

        Ловит мутацию: отказ журналируется на каждой попытке (записей
        отказа больше одной), либо N в детали — номер последней паузы или
        литерал 3 (при подменённом потолке деталь с неверным числом), либо
        деталь «сервер» достраивается советом non-fast-forward.
        """
        self.assertEqual(getattr(artifact_branch, "PUSH_SERVER_RETRY_ATTEMPTS",
                                 None), 3)
        for attempts in (None, RNG.randrange(2, 6)):
            with self.subTest(attempts=attempts):
                before = len(self.failed_details())
                script = self.scripted_commit(ISE, attempts=attempts)
                n = (artifact_branch.PUSH_SERVER_RETRY_ATTEMPTS
                     if attempts is None else attempts)
                self.assertEqual(len(script.push_calls), n,
                                 f"зерно {SEED}: {script.push_calls}")
                details = self.failed_details()[before:]
                self.assertEqual(len(details), 1, f"зерно {SEED}: {details}")
                self.assertTrue(details[0].startswith(f"{SERVER} (попыток {n}): "),
                                f"зерно {SEED}: {details[0]}")
                self.assertNotIn("свести merge-коммитом", details[0])
                self.assertNotIn("локальный sha", details[0])
                self.assertIsNone(SHA_PATTERN.search(details[0]), details[0])

    def test_ac11_retries_never_force(self):
        """В сценариях повтора (успех со второй попытки и «сервер» на всех)
        ни один `git push` не несёт `--force`, `--force-with-lease[=…]` и
        refspec с `+`.

        Ловит мутацию: повтор «чинит» отказ сервера силой — последняя
        попытка идёт с `--force-with-lease` или refspec `+ref:ref`.
        """
        for answers in ((ISE, None), (ISE,)):
            with self.subTest(answers=len(answers)):
                self.assert_no_force(self.scripted_commit(*answers))

    def test_ac13_success_after_retry_names_attempts(self):
        """Успех со второй попытки: деталь записи успеха содержит
        `попыток 2`.

        Ловит мутацию: в деталь успеха пишется номер паузы или потолок
        попыток вместо числа сделанных вызовов — деталь несёт «попыток 1»
        или «попыток 3».
        """
        self.scripted_commit(ISE, None)
        details = self.success_details()
        self.assertEqual(len(details), 1, self.push_rows())
        self.assertIn("попыток 2", details[0])

    def test_ac14_pauses_are_attempts_minus_one(self):
        """Пауз на одну меньше попыток: успех со второй — одна пауза,
        «сервер» на всех — `PUSH_SERVER_RETRY_ATTEMPTS − 1` (2, и при
        случайном подменённом потолке тоже); последняя операция — отправка,
        не пауза.

        Ловит мутацию: пауза стоит после каждой попытки, включая последнюю,
        — пауз столько же, сколько отправок, последнее событие — пауза.
        """
        script = self.scripted_commit(ISE, None)
        self.assertEqual(script.events, ["push", "sleep", "push"])
        for attempts in (None, RNG.randrange(2, 6)):
            with self.subTest(attempts=attempts):
                script = self.scripted_commit(ISE, attempts=attempts)
                n = (getattr(artifact_branch, "PUSH_SERVER_RETRY_ATTEMPTS", 3)
                     if attempts is None else attempts)
                self.assertEqual(len(script.pauses), n - 1,
                                 f"зерно {SEED}: {script.events}")
                self.assertEqual(script.events[-1:], ["push"],
                                 f"зерно {SEED}: {script.events}")
                self.assertEqual(script.events.count("push"), n,
                                 f"зерно {SEED}: {script.events}")


class SuccessAfterFailureJournalTest(PushServerSandbox):

    def test_ac8_success_after_network_failure_is_journaled(self):
        """Отказ «сеть», затем успешная отправка следующего коммита — в
        журнале запись успеха; две успешные отправки подряд без отказа
        перед ними — записей успеха нет.

        Ловит мутацию: `_send` журналирует успех только после повтора в том
        же вызове и не читает последнюю запись исхода — успех после
        прошлого отказа молчит; либо успех журналируется всегда — записи
        успеха появляются и без отказа.
        """
        self.commit()
        self.commit()
        self.assertEqual(self.success_details(), [], self.push_rows())

        self.scripted_commit(NETWORK)
        self.assertEqual(len(self.failed_details()), 1, self.push_rows())
        self.commit()
        rows = self.push_rows()
        self.assertEqual(rows[-1]["action"], PUSH_OK, rows)


class SendPendingRemovedTest(unittest.TestCase):

    EXISTING = ("tests.test_artifact_ref_sync.SendAfterCommitTest."
                "test_refusal_is_journaled_commit_kept_and_retried_on_transition")

    def test_ac9_send_pending_removed_and_transition_resends(self):
        """`send_pending` нет ни в модуле, ни в файлах `orchestrator/`;
        существующий тест досылки на переходе зелёный.

        Ловит мутацию: функция удалена, а докстринг модуля (или вызов в
        другом модуле пульта) по-прежнему называет `send_pending` — поиск
        находит вхождение; либо вместе с ней снята досылка коммитом
        паспорта — существующий тест досылки краснеет.
        """
        self.assertFalse(hasattr(artifact_branch, "send_pending"))
        package = Path(artifact_branch.__file__).resolve().parent
        hits = []
        for path in sorted(package.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "send_pending" in text:
                hits.append(str(path.relative_to(package)))
        self.assertEqual(hits, [])

        suite = unittest.defaultTestLoader.loadTestsFromName(self.EXISTING)
        result = unittest.TextTestRunner(stream=io.StringIO(),
                                         verbosity=0).run(suite)
        self.assertEqual(result.testsRun, 1)
        self.assertTrue(result.wasSuccessful(),
                        result.failures + result.errors)


if __name__ == "__main__":
    unittest.main()
