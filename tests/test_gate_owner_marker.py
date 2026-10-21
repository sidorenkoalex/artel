"""Маркер владельца каталогов выписок гейтов исходов и двустороннего
прогона и их уборка `doctor` (SPEC 01M5FRYVP4NF81VT00FYPHPWJH, требования
5-6).

Временный каталог процесса (`tempfile.tempdir`) подменён каталогом теста:
и гейты, и `doctor` видят только его. Уборка гоняет настоящий git в клоне
во временном каталоге теста (`_project_clones` подменён), настоящие клоны
пульта не трогаются.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import doctor, gitcmd, liveness, project_profile
from orchestrator.advance_gates import outcome_integrity, two_sided

MARKER = liveness.GATE_OWNER_MARKER


def dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def artel_profile():
    return project_profile.Profile(
        command=("python3", "-m", "pytest"), long_lived_dir="tests",
        long_lived_name="test_<id>_<name>.py",
        weakening_scope=("tests/**/*.py",),
        mutation_claim_scope=("tests/test_*.py",), report="junit-xml",
        component="default", project="artel")


class TempRootTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.tmp_root = self.root / "tmp"
        self.tmp_root.mkdir()
        patcher = mock.patch.object(tempfile, "tempdir", str(self.tmp_root))
        patcher.start()
        self.addCleanup(patcher.stop)

    def gate_dir(self, prefix: str, marker_pid=None, canary_pid=None) -> Path:
        path = Path(tempfile.mkdtemp(prefix=prefix)).resolve()
        if marker_pid is not None:
            (path / MARKER).write_text(str(marker_pid), encoding="utf-8")
        if canary_pid is not None:
            (path / liveness.CANARY_OWNER_MARKER).write_text(
                str(canary_pid), encoding="utf-8")
        return path


class GateMarkerBeforeWorktreeAddTest(TempRootTest):

    def in_repo_spy(self):
        """`gitcmd.in_repo`: на `worktree add` запоминает содержимое маркера
        каталога выписки и отказывает; прочие вызовы — успех."""
        seen = []

        def in_repo(repo, *args):
            if args[:2] == ("worktree", "add"):
                marker = Path(args[3]).parent / MARKER
                seen.append(marker.read_text(encoding="utf-8")
                            if marker.is_file() else None)
                return subprocess.CompletedProcess(args, 1, "", "отказ теста")
            return subprocess.CompletedProcess(args, 0, "", "")
        return seen, in_repo

    def test_outcome_gate_writes_marker_before_worktree_add(self):
        """`outcome_integrity._gate` при профиле артели кладёт `.artel-gate-owner` с pid процесса до первого `git worktree add`.

        Ловит мутацию: маркер не пишется или пишется после `worktree add`
        (каталог, брошенный обрывом между вызовами, без владельца); маркер
        пишется только при профиле в границе гейта исходов; в маркер
        записан не pid процесса.
        """
        repo = self.root / "clone"
        repo.mkdir()
        seen, in_repo = self.in_repo_spy()
        with mock.patch.object(gitcmd, "in_repo", in_repo), \
                mock.patch.object(gitcmd, "branch_head_sha",
                                  return_value="a" * 40), \
                mock.patch.object(outcome_integrity.workspace, "task_repo",
                                  return_value=repo):
            outcome_integrity._gate(None, "T1", "task/t1", "refs/artifacts/T1",
                                    artel_profile(), lambda *_a: "b" * 40,
                                    False)
        self.assertTrue(seen, "git worktree add не вызван")
        self.assertEqual(seen[0], str(os.getpid()))

    def test_two_sided_writes_marker_before_worktree_add(self):
        """`two_sided.run` кладёт `.artel-gate-owner` с pid процесса до первого `git worktree add`.

        Ловит мутацию: двусторонний прогон маркер не пишет или пишет
        после `worktree add` — его брошенная выписка без владельца.
        """
        repo = self.root / "clone"
        repo.mkdir()
        seen, in_repo = self.in_repo_spy()
        with mock.patch.object(gitcmd, "in_repo", in_repo), \
                mock.patch.object(gitcmd, "branch_head_sha",
                                  return_value="a" * 40):
            two_sided.run(repo, "task/t1", "b" * 40, [])
        self.assertTrue(seen, "git worktree add не вызван")
        self.assertEqual(seen[0], str(os.getpid()))


class GateOrphanTempDirsTest(TempRootTest):

    def test_gate_dir_orphan_unless_live_gate_marker(self):
        """Выписка без маркера, с мёртвым pid или только с живым маркером канарейки — сирота; с живым `.artel-gate-owner` — нет.

        Ловит мутацию: каталоги `artel-outcome-*`/`artel-two-sided-*` не
        входят в перечень `orphans-temp`; общий маркер канарейки
        проверяется раньше ветки выписок и защищает каталог без маркера
        гейта; живой маркер гейта не защищает каталог.
        """
        live = os.getpid()
        for prefix in ("artel-outcome-", "artel-two-sided-"):
            orphans = [self.gate_dir(prefix), self.gate_dir(prefix, dead_pid()),
                       self.gate_dir(prefix, canary_pid=live)]
            owned = self.gate_dir(prefix, live)
            found = {Path(p).resolve() for p in doctor._orphan_temp_dirs()}
            for path in orphans:
                with self.subTest(orphan=path.name):
                    self.assertIn(path, found)
            self.assertNotIn(owned, found)


class GateFixPruneTest(TempRootTest):

    def setUp(self):
        super().setUp()
        self.clone = self.root / "clone"
        self.git("init", "-q", "-b", "main", str(self.clone), cwd=self.root)
        (self.clone / "a.txt").write_text("a\n", encoding="utf-8")
        self.git("add", "a.txt")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                 "-m", "a")

    def git(self, *args, cwd=None):
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_CONFIG_NOSYSTEM="1")
        res = subprocess.run(["git", *args], cwd=cwd or self.clone, env=env,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout

    def checkout(self, scratch: Path) -> Path:
        tree = scratch / "base"
        self.git("worktree", "add", "--detach", str(tree), "HEAD")
        return tree.resolve()

    def registered(self) -> set:
        out = self.git("worktree", "list", "--porcelain")
        return {Path(line.split(" ", 1)[1]).resolve()
                for line in out.splitlines() if line.startswith("worktree ")}

    def test_fix_removes_dead_gate_dir_and_prunes_worktree(self):
        """Уборка удаляет выписку мёртвого владельца и `git worktree prune` убирает её запись в клоне; выписка живого и её запись остаются.

        Ловит мутацию: каталог сироты удаляется без `git worktree prune`
        (запись остаётся в клоне); prune идёт мимо `_project_clones`
        модуля `orphans`; уборка удаляет и выписку живого владельца.
        """
        live = self.gate_dir("artel-outcome-", os.getpid())
        dead = self.gate_dir("artel-two-sided-", dead_pid())
        live_tree, dead_tree = self.checkout(live), self.checkout(dead)
        with mock.patch("orchestrator.doctor.orphans._project_clones",
                        return_value=[self.clone]) as clones:
            doctor._fix_orphan_temp_dirs()
        self.assertFalse(dead.exists())
        self.assertTrue(clones.called)
        self.assertTrue(live.exists())
        registered = self.registered()
        self.assertNotIn(dead_tree, registered)
        self.assertIn(live_tree, registered)

    def test_fix_without_gate_deletions_does_not_call_git(self):
        """Уборка, удалившая только сироту канарейки, `git worktree prune` не зовёт.

        Ловит мутацию: prune выполняется на каждой уборке или после
        удаления любого каталога — уборка трогает клоны проектов без
        повода.
        """
        self.gate_dir("artel-outcome-", os.getpid())
        canary = Path(tempfile.mkdtemp(prefix="artel-canary-"))
        with mock.patch("orchestrator.doctor.orphans._project_clones",
                        return_value=[self.clone]), \
                mock.patch.object(doctor.gitcmd, "in_repo") as in_repo:
            doctor._fix_orphan_temp_dirs()
        self.assertFalse(canary.exists(), "предпосылка: сирота канарейки")
        self.assertEqual(in_repo.call_args_list, [])


if __name__ == "__main__":
    unittest.main()
