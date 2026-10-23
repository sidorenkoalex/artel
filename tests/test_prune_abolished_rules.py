"""`prune`: свойства отбора, не покрытые долгоживущим файлом задачи
01M5KBQGMZ051ENRVS8F42MA4V — порядок причин «оставлено», локальность
вызовов git проверки `.artel/notes-work`, нечитаемый pid `run.json`.
"""
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from unittest import mock

from orchestrator import config, gitcmd, prune, suite_lock
from tests.sandbox import (InitializedTmpRootTest, RealGitSandbox, capture,
                           init_bare_origin)

NOTES_LINE = "  каталог упразднённого механизма .artel/notes-work"
OLD_ID = "01M" + "0" * 20 + "ABC"


def _age(path: Path, days: float) -> None:
    stamp = time.time() - days * 86400
    os.utime(path, (stamp, stamp))


class NotesWorkRulesTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.notes = self.root / ".artel" / "notes-work"

    def ngit(self, *args: str) -> str:
        return self.git("-C", str(self.notes), "-c", "user.name=t",
                        "-c", "user.email=t@example.invalid",
                        "-c", "commit.gpgsign=false", *args)

    def clean_repo(self) -> None:
        origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, origin, ignore_errors=True)
        init_bare_origin(origin, self.git)
        self.git("init", "-q", "-b", config.MAIN_BRANCH, str(self.notes))
        (self.notes / "README.md").write_text("заметки\n", encoding="utf-8")
        self.ngit("add", "-A")
        self.ngit("commit", "-q", "-m", "заметки")
        self.ngit("remote", "add", "origin", str(origin))
        self.ngit("push", "-q", "origin", config.MAIN_BRANCH)

    def test_first_reason_in_order_wins(self):
        """Несколько причин сразу — одна строка с первой по перечню SPEC.

        Правка отслеживаемого файла, неотслеживаемый файл, непустой stash
        и отделённый HEAD одновременно: печатается только «незакоммиченные
        правки».

        Ловит мутацию: проверки переставлены (stash или HEAD раньше правок)
        либо печатается строка на каждую причину — строка «незакоммиченные
        правки» не единственная строка каталога или её нет.
        """
        self.clean_repo()
        (self.notes / "README.md").write_text("спрятано\n", encoding="utf-8")
        self.ngit("stash", "-q")
        self.ngit("checkout", "-q", "--detach")
        (self.notes / "README.md").write_text("правка\n", encoding="utf-8")
        (self.notes / "new.md").write_text("н\n", encoding="utf-8")

        out = capture(prune.cmd_prune)

        lines = [line for line in out.splitlines() if line.startswith(NOTES_LINE)]
        self.assertEqual(lines, [f"{NOTES_LINE} оставлено: незакоммиченные правки"],
                         out)

    def test_git_failure_outranks_unsaved_work(self):
        """Сбой одного вызова git — «git не ответил», даже если другой
        вызов показал бы несохранённую работу.

        Ловит мутацию: ответы разбираются по мере вызовов, и признак работы
        из удавшегося вызова печатается раньше сбоя — строка «коммиты вне
        origin» вместо «git не ответил: …».
        """
        self.clean_repo()
        (self.notes / "late.md").write_text("п\n", encoding="utf-8")
        self.ngit("add", "-A")
        self.ngit("commit", "-q", "-m", "поздняя")
        real = gitcmd.in_repo

        def failing_stash(repo, *args):
            if args[:1] == ("stash",):
                return real(repo, "no-such-subcommand")
            return real(repo, *args)

        with mock.patch.object(gitcmd, "in_repo", side_effect=failing_stash):
            out = capture(prune.cmd_prune)

        self.assertTrue(any(line.startswith(f"{NOTES_LINE} оставлено: git не ответил: ")
                            for line in out.splitlines()), out)

    def test_checks_are_local_git_only(self):
        """Проверка `.artel/notes-work` не обращается к сети.

        Ловит мутацию: перед сверкой с `origin` добавлен `fetch`/`ls-remote`/
        `remote update` — подкоманда сетевого git попадает в перечень вызовов.
        """
        self.clean_repo()
        real = gitcmd.in_repo
        calls = []

        def spy(repo, *args):
            calls.append(args)
            return real(repo, *args)

        with mock.patch.object(gitcmd, "in_repo", side_effect=spy):
            out = capture(prune.cmd_prune)

        self.assertIn(f"{NOTES_LINE} (", out)
        network = {"fetch", "pull", "push", "ls-remote", "remote", "clone"}
        self.assertTrue(calls, out)
        for args in calls:
            self.assertFalse(network & set(args), args)


class SuiteRunPidTest(InitializedTmpRootTest):

    def test_unreadable_pid_is_not_a_live_run(self):
        """`run.json` с pid не целым, нулевым, без ключа `pid` или
        испорченный — признака живого прогона нет, старый каталог задачи,
        которой нет в БД, удаляется.

        Ловит мутацию: нечитаемый pid считается живым прогоном (или чтение
        падает исключением) — старый каталог переживает `--execute`.
        """
        for n, body in enumerate(('{"pid": "abc"}', '{"pid": 0}', '{"run": 1}',
                                  "не json", '{"pid": -5}')):
            with self.subTest(body=body):
                task_id = f"{OLD_ID[:-1]}{n}"
                run_dir = suite_lock.directory() / task_id
                run_dir.mkdir(parents=True)
                run = run_dir / "run.json"
                run.write_text(body, encoding="utf-8")
                old = config.LOG_RETENTION_DAYS + 5
                _age(run, old)
                _age(run_dir, old)

                out = capture(prune.cmd_prune, True)

                self.assertIn(f"  каталог suite-run {task_id} (1 файлов) удалён",
                              out.splitlines(), out)
                self.assertFalse(run_dir.exists())

    def test_live_pid_parsed_as_integer_text(self):
        """`pid` строкой из цифр живого процесса читается как целое —
        каталог не отбирается (то же чтение, что `_live_suite_run_in`).

        Ловит мутацию: pid сравнивается без `int(...)` (`isinstance(pid,
        int)`) — строковый pid живого процесса не распознан, каталог удалён.
        """
        task_id = OLD_ID
        run_dir = suite_lock.directory() / task_id
        run_dir.mkdir(parents=True)
        run = run_dir / "run.json"
        run.write_text(json.dumps({"pid": str(os.getpid())}), encoding="utf-8")
        _age(run, config.LOG_RETENTION_DAYS + 5)

        out = capture(prune.cmd_prune, True)

        self.assertNotIn(task_id, out)
        self.assertTrue(run.exists())
