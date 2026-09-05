"""AC-2 (tasks/01M1QHQ277PQQA894X97RVEX9Y/SPEC.md): «Тот же вызов с
локальным bare-репозиторием (адрес — `file://` либо абсолютный путь) не
перехватывается и проходит как раньше — без изменений в поведении
локальных git-фикстур (T048/T053).»

Зелёный с рождения: локальный bare-репозиторий, адресуемый абсолютным
путём или `file://`, уже сегодня проходит сквозь `SpyRun(
passthrough_unknown=True)` без единого изменения (перехвата ещё нет
вовсе — блокировать нечему, `tests/sandbox.py:476`). Тест здесь —
регрессионная защита СУЩЕСТВУЮЩЕГО поведения на будущее: после того как
разработчик добавит перехват сетевых адресов (AC-1), этот же сценарий
обязан остаться зелёным (перехват не имеет права задеть локальные
адреса).
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, gitcmd  # noqa: E402
from tests.sandbox import TmpRootTest, resilient_tmp_cleanup  # noqa: E402


class LocalBareRepoFetchPushStillWorkTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        self._git("init", "-q", "-b", config.MAIN_BRANCH)
        self._git("config", "user.email", "artel-tests@example.invalid")
        self._git("config", "user.name", "artel tests")
        (self.root / "marker.txt").write_text("main\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "init")

        bare_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, bare_tmp)
        self.bare = Path(bare_tmp.name) / "origin.git"
        res = subprocess.run(["git", "init", "-q", "--bare", str(self.bare)],
                             capture_output=True, text=True)
        self.assertEqual(0, res.returncode, res.stderr)

    def _git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(0, res.returncode, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def test_ac2_push_fetch_ls_remote_clone_with_local_path_address_succeed(self):
        """push/fetch/ls-remote/clone против локального bare-репозитория,
        адресуемого абсолютным путём или `file://`, обязаны проходить
        как раньше (rc=0) — перехват сетевых адресов их не касается.

        Ловит мутацию: перехват сужает критерий «локальности» только до
        `file://` без абсолютных путей (или наоборот) — здесь оба вида
        адресов проверены раздельно на push/fetch, и обе формы обязаны
        оставаться зелёными.
        """
        push = gitcmd.git("push", "-q", str(self.bare), config.MAIN_BRANCH)
        self.assertEqual(0, push.returncode, push.stderr)

        fetch_abs = gitcmd.git("fetch", "-q", str(self.bare), config.MAIN_BRANCH)
        self.assertEqual(0, fetch_abs.returncode, fetch_abs.stderr)

        fetch_file_url = gitcmd.git(
            "fetch", "-q", f"file://{self.bare}", config.MAIN_BRANCH)
        self.assertEqual(0, fetch_file_url.returncode, fetch_file_url.stderr)

        ls = gitcmd.git("ls-remote", str(self.bare), config.MAIN_BRANCH)
        self.assertEqual(0, ls.returncode, ls.stderr)
        self.assertTrue(ls.stdout.strip(), "ls-remote обязан вернуть sha ветки")

        clone_dest = self.root / "ac2-clone-dest"
        clone = gitcmd.git("clone", "-q", str(self.bare), str(clone_dest))
        self.assertEqual(0, clone.returncode, clone.stderr)
        self.assertTrue((clone_dest / ".git").is_dir())


if __name__ == "__main__":
    unittest.main()
