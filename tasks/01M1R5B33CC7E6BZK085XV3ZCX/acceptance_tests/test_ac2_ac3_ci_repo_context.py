"""Приёмочный тест AC-2/AC-3 (tasks/01M1R5B33CC7E6BZK085XV3ZCX/SPEC.md,
«Критерии приёмки»).

AC-2: `ci.gh` принимает контекст target и подставляет `--repo <url>` в
вызовы `pr create`, `pr ready`, `pr comment`, `api repos/<owner>/
<repo>/…`, `run list`; для self поведение (без `--repo`, из
`config.ROOT`) байт-в-байт не меняется.

AC-3: `ci.head_sha` и опрос статуса проверок (`check_runs_page`/
`run_list`) резолвят коммит и статус из клона/форджи контекста target'а,
когда target ≠ self.

Тест мокает `subprocess.run` (единственную точку, которую и `gitcmd.git`,
и `ci.gh` зовут в конечном счёте) — содержательность самого форджа не
предмет проверки, только то, что модуль ПРИНИМАЕТ контекст и КОРРЕКТНО
им пользуется на низком уровне (`--repo <url>`/`cwd`).

Красен до реализации: `ci.gh`/`ci.head_sha`/`ci.check_runs_page`/
`ci.run_list` сегодня не принимают никакого параметра контекста —
вызов с `repo=` падает `TypeError: unexpected keyword argument`.
"""
import subprocess
import sys
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import ci, config  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

EXTERNAL_URL = "https://example.invalid/extproj"


class GhRepoFlagTest(RealGitSandbox):
    """`ci.gh(..., repo=...)` — низкоуровневая подстановка `--repo`."""

    def _spy(self):
        calls = []

        def fake_run(args, **kwargs):
            calls.append((list(args), kwargs))
            if args and args[0] == "gh" and "api" in args:
                return subprocess.CompletedProcess(
                    args, 0, '{"check_runs": [], "total_count": 0}', "")
            if args and args[0] == "gh" and "list" in args:
                return subprocess.CompletedProcess(args, 0, "[]", "")
            return subprocess.CompletedProcess(args, 0, "ok\n", "")
        return calls, fake_run

    def test_ac2_self_target_call_carries_no_repo_flag(self):
        """Без `repo=` (self) — argv и `cwd` байт-в-байт как до задачи:
        `["gh", "pr", "ready", "task/x"]`, `cwd=config.ROOT`.

        Ловит мутацию: реализация всегда дописывает `--repo` (например,
        подставляя `None` буквальной строкой) — `assertNotIn` поймает
        появление флага там, где его сегодня нет.
        """
        calls, fake_run = self._spy()
        with mock.patch.object(subprocess, "run", fake_run):
            ci.gh("pr", "ready", "task/x")

        (call,) = calls
        args, kwargs = call
        self.assertEqual(args, ["gh", "pr", "ready", "task/x"])
        self.assertNotIn("--repo", args)
        self.assertEqual(kwargs.get("cwd"), config.ROOT)

    def test_ac2_external_target_pr_create_carries_repo_flag(self):
        """`repo=<url>` — `--repo <url>` в итоговом argv `pr create`.

        Ловит мутацию: параметр принимается, но никуда не подставляется
        (no-op) — `assertIn` на паре `--repo`/URL этого не пропустит.
        """
        calls, fake_run = self._spy()
        with mock.patch.object(subprocess, "run", fake_run):
            ci.gh("pr", "create", "--draft", "--title", "x",
                  repo=EXTERNAL_URL)

        (call,) = calls
        args, _ = call
        self.assertIn("--repo", args)
        self.assertEqual(args[args.index("--repo") + 1], EXTERNAL_URL)

    def test_ac2_external_target_pr_comment_carries_repo_flag(self):
        calls, fake_run = self._spy()
        with mock.patch.object(subprocess, "run", fake_run):
            ci.gh("pr", "comment", "task/x", "--body", "текст",
                  repo=EXTERNAL_URL)

        (call,) = calls
        args, _ = call
        self.assertIn("--repo", args)
        self.assertEqual(args[args.index("--repo") + 1], EXTERNAL_URL)

    def test_ac2_external_target_api_call_carries_repo_flag(self):
        """`api repos/{owner}/{repo}/...` — тоже несёт `--repo <url>`
        (AC-2 явно перечисляет и этот вызов, не только `pr *`)."""
        calls, fake_run = self._spy()
        with mock.patch.object(subprocess, "run", fake_run):
            ci.check_runs_page("deadbeef", 1, repo=EXTERNAL_URL)

        (call,) = calls
        args, _ = call
        self.assertIn("--repo", args)
        self.assertEqual(args[args.index("--repo") + 1], EXTERNAL_URL)

    def test_ac3_run_list_carries_repo_flag(self):
        calls, fake_run = self._spy()
        with mock.patch.object(subprocess, "run", fake_run):
            ci.run_list("task/x", repo=EXTERNAL_URL)

        (call,) = calls
        args, _ = call
        self.assertIn("--repo", args)
        self.assertEqual(args[args.index("--repo") + 1], EXTERNAL_URL)


class HeadShaRepoContextTest(RealGitSandbox):
    """`ci.head_sha(branch, repo=...)` — читает голову ветки ИЗ ДАННОГО
    клона, не из `config.ROOT`."""

    def setUp(self):
        super().setUp()
        # Второй, полностью независимый репозиторий — имитация клона
        # внешнего target: своя ветка `task/x` с коммитом, которого в
        # `config.ROOT` нет и быть не может (разное дерево).
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.other_repo = Path(tmp.name)
        self._g("init", "-q", "-b", config.MAIN_BRANCH)
        self._g("config", "user.email", "artel@example.invalid")
        self._g("config", "user.name", "artel tests")
        (self.other_repo / "f.txt").write_text("x\n", encoding="utf-8")
        self._g("add", "-A")
        self._g("commit", "-q", "-m", "init")
        self._g("checkout", "-q", "-b", "task/x")
        (self.other_repo / "f.txt").write_text("y\n", encoding="utf-8")
        self._g("add", "-A")
        self._g("commit", "-q", "-m", "feature")
        self.other_sha = self._g("rev-parse", "HEAD").strip()

    def _g(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.other_repo,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout

    def test_ac3_head_sha_with_repo_reads_the_given_clone(self):
        """`repo=self.other_repo` — sha ветки `task/x` из НЕГО, а не из
        `config.ROOT` (где такой ветки нет вовсе).

        Ловит мутацию: `repo` принимается, но игнорируется (по-прежнему
        читает `config.ROOT`) — `config.ROOT` не несёт ветки `task/x`,
        и ожидаемый sha не совпал бы с пустой строкой/чужим значением.
        """
        sha, why = ci.head_sha("task/x", repo=self.other_repo)

        self.assertEqual(sha, self.other_sha, why)

    def test_ac3_head_sha_without_repo_still_reads_root(self):
        """Байт-в-байт прежнее поведение self (без `repo=`): читает
        `config.ROOT`, где ветки `task/x` нет — пустая строка и причина."""
        sha, why = ci.head_sha("task/x")

        self.assertEqual(sha, "")
        self.assertNotEqual(why, "")


if __name__ == "__main__":
    import unittest
    unittest.main()
