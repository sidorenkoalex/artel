"""Чтения git со сроком, своим окружением и потоком: `gitcmd.read`,
`gitcmd.read_env`, `gitcmd.read_stream` (SPEC 01M5T79C5GFJGQ9XCTH8W0PDFQ,
требование 2) — исходы самих функций, без мест-потребителей."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import gitcmd


def _git(repo: Path, *args: str) -> str:
    res = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c",
         "user.email=t@example.invalid", "-c", "commit.gpgsign=false",
         "-c", "core.hooksPath=/dev/null", *args],
        capture_output=True, text=True, check=True)
    return res.stdout.strip()


class _Repo(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / "repo"
        self.repo.mkdir()
        _git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "big.txt").write_bytes(b"0123456789\n" * 1000)
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "c")


class _SlowProc:
    """Процесс, у которого первый `communicate` со сроком истекает."""

    def __init__(self, *a, **kw):
        self.args = a[0] if a else kw.get("args")
        self.events = []
        self.returncode = None

    def communicate(self, input=None, timeout=None):
        self.events.append(("communicate", timeout))
        if timeout is not None:
            raise subprocess.TimeoutExpired(self.args, timeout)
        return "", ""

    def kill(self):
        self.events.append(("kill",))
        self.returncode = -9


class ReadStreamOutcomesTest(_Repo):
    def test_over_limit_timeout_and_nonzero_code_are_distinct(self):
        """Перебор предела — `OverLimit`, ненулевой код — результат с кодом,
        полный вывод в пределе — результат с байтами; ни один исход не
        выдаёт себя за другой.

        Ловит мутацию: `read_stream` при переборе предела не бросает
        `OverLimit`, а возвращает обрезанный вывод с кодом убитого процесса
        — тест получает результат вместо исключения.
        """
        with self.assertRaises(gitcmd.OverLimit):
            gitcmd.read_stream(self.repo, "show", "HEAD:big.txt",
                               limit=100, timeout=30, chunk=16)
        res = gitcmd.read_stream(self.repo, "show", "HEAD:big.txt",
                                 limit=1 << 20, timeout=30, chunk=16)
        self.assertEqual((res.returncode, res.stdout),
                         (0, b"0123456789\n" * 1000))
        bad = gitcmd.read_stream(self.repo, "show", "HEAD:нет-файла",
                                 limit=1 << 20, timeout=30)
        self.assertNotEqual(bad.returncode, 0)

    def test_deadline_kills_process_and_raises_timeout(self):
        """Срок истёк во время чтения — `Timeout`, процесс git убит.

        Ловит мутацию: таймер срока не убивает процесс — чтение ждёт
        конца `sleep 30`, процесс завершается сам с кодом 0, а не сигналом
        (отрицательный код).
        """
        bindir = self.repo.parent / "bin"
        bindir.mkdir()
        exe = bindir / "git"
        exe.write_text("#!/bin/sh\nprintf partial\nexec /bin/sleep 30\n",
                       encoding="utf-8")
        exe.chmod(0o755)
        path = f"{bindir}:{os.environ['PATH']}"
        made = []
        real_popen = subprocess.Popen

        def popen(*a, **kw):
            made.append(real_popen(*a, **kw))
            return made[-1]

        with mock.patch.dict(os.environ, {"PATH": path}), \
                mock.patch.object(subprocess, "Popen", popen):
            with self.assertRaises(gitcmd.Timeout):
                gitcmd.read_stream(self.repo, "ls-tree", "HEAD",
                                   limit=1 << 20, timeout=0.5)
        [proc] = made
        self.assertLess(proc.returncode, 0)

    def test_launch_failure_keeps_original_exception(self):
        """Отказ запуска процесса — `LaunchFailed` с исходным исключением,
        в том числе `TimeoutExpired` конструктора (это не истечение срока).

        Ловит мутацию: `read_stream` сводит `TimeoutExpired` запуска к
        `Timeout` — тест получает `Timeout` вместо `LaunchFailed`.
        """
        for error in (FileNotFoundError(2, "нет git"),
                      subprocess.TimeoutExpired(["git"], 3)):
            with self.subTest(error=type(error).__name__), \
                    mock.patch.object(subprocess, "Popen",
                                      mock.Mock(side_effect=error)):
                with self.assertRaises(gitcmd.LaunchFailed) as info:
                    gitcmd.read_stream(self.repo, "ls-tree", "HEAD",
                                       limit=10, timeout=5)
                self.assertIs(info.exception.error, error)


class ReadTimeoutTest(_Repo):
    def test_read_turns_timeout_expired_into_timeout(self):
        """Истечение срока `subprocess.run` — `gitcmd.Timeout`, не
        `subprocess.TimeoutExpired`; вывод без срока — байты.

        Ловит мутацию: `read` пропускает `TimeoutExpired` наружу —
        `assertRaises(gitcmd.Timeout)` получает чужое исключение.
        """
        self.assertEqual(gitcmd.read(self.repo, "show", "HEAD:big.txt").stdout,
                         b"0123456789\n" * 1000)
        expired = subprocess.TimeoutExpired(["git"], 1)
        with mock.patch.object(subprocess, "run",
                               mock.Mock(side_effect=expired)):
            with self.assertRaises(gitcmd.Timeout):
                gitcmd.read(self.repo, "show", "HEAD:big.txt", timeout=1)

    def test_read_env_kills_and_drains_on_timeout(self):
        """Срок `read_env` истёк — процесс убит, вывод дочитан, `Timeout`;
        окружение процесса — переданное плюс маркер пульта.

        Ловит мутацию: `read_env` по сроку не зовёт `kill` — в событиях
        процесса нет `("kill",)`.
        """
        made = []

        def popen(*a, **kw):
            proc = _SlowProc(*a, **kw)
            proc.kwargs = kw
            made.append(proc)
            return proc

        env = {"GIT_INDEX_FILE": "/tmp/индекс"}
        with mock.patch.object(subprocess, "Popen", popen):
            with self.assertRaises(gitcmd.Timeout):
                gitcmd.read_env(self.repo, env, "write-tree", timeout=15)
        [proc] = made
        self.assertEqual(proc.events, [("communicate", 15), ("kill",),
                                       ("communicate", None)])
        self.assertEqual(proc.kwargs["env"], gitcmd.pult_env(env))


if __name__ == "__main__":
    unittest.main()
