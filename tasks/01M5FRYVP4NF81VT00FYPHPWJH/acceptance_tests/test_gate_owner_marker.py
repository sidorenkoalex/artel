"""Маркер владельца каталогов выписок гейтов и их уборка `doctor` (AC-6, AC-7, AC-8).

Группа: разовый

Критерии называют закрытые имена `outcome_integrity._gate`,
`doctor._orphan_temp_dirs`, `doctor._fix_orphan_temp_dirs` и подмену
`orchestrator.doctor.orphans._project_clones` — долгоживущему файлу
`tests/` закрытые имена и их подмена недоступны (правило ADR-0020),
поэтому проверка живёт в планке.

Временный каталог процесса (`tempfile.tempdir`) подменён каталогом теста:
и гейты, и `doctor` видят только его. AC-6 подменяет `gitcmd.in_repo`
(вызов `git worktree add` наблюдается без настоящего git и отказывает —
гейт уходит в отказ подготовки), голову ветки и клон проекта. AC-8 гоняет
настоящий git в клоне во временном каталоге теста; вызовы git уборки
наблюдаются подменой `subprocess.Popen` (через неё идут и
`subprocess.run`), настоящие клоны пульта не трогаются.

Красен до реализации: константы `liveness.GATE_OWNER_MARKER` нет (AC-6 падает на атрибуте), `_gate`/`two_sided.run` маркер не пишут, а `doctor._orphan_temp_dirs` каталоги `artel-outcome-*`/`artel-two-sided-*` не рассматривает вовсе — сирота не называется и не удаляется (AC-7, AC-8).
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

PREFIXES = ("artel-outcome-", "artel-two-sided-")
MARKER = ".artel-gate-owner"


def dead_pid() -> int:
    """pid завершённого и снятого дочернего процесса."""
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


def component_profile():
    return project_profile.Profile(
        command=("python3", "-m", "pytest"), long_lived_dir="tests",
        long_lived_name="test_<id>_<name>.py",
        weakening_scope=("tests/**/*.py",),
        mutation_claim_scope=("tests/test_*.py",), report="junit-xml",
        component="web", project="p", from_components=True)


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

    def gate_dir(self, prefix: str, marker_pid: int | None,
                 canary_pid: int | None = None) -> Path:
        path = Path(tempfile.mkdtemp(prefix=prefix))
        if marker_pid is not None:
            (path / MARKER).write_text(str(marker_pid), encoding="utf-8")
        if canary_pid is not None:
            (path / liveness.CANARY_OWNER_MARKER).write_text(
                str(canary_pid), encoding="utf-8")
        return path


class GateMarkerWrittenTest(TempRootTest):

    def spy(self):
        """Подмена `gitcmd.in_repo`: на `worktree add` запоминает маркер
        каталога выписки и отказывает; прочие вызовы — успех."""
        seen = []

        def in_repo(repo, *args):
            if args[:2] == ("worktree", "add"):
                scratch = Path(args[3]).parent
                marker = scratch / MARKER
                seen.append((scratch, marker.read_text(encoding="utf-8")
                             if marker.is_file() else None))
                return subprocess.CompletedProcess(args, 1, "", "отказ теста")
            return subprocess.CompletedProcess(args, 0, "", "")
        return seen, in_repo

    def test_ac6_gate_marker_written_before_worktree_add(self):
        """`_gate` и `two_sided.run` кладут маркер `.artel-gate-owner` с pid процесса в каталог выписки до `git worktree add` — при профиле артели и компонента.

        Сценарий: голова ветки подменена sha, клон проекта — каталог
        теста; `gitcmd.in_repo` на `worktree add` читает файл маркера в
        родителе пути выписки и отказывает. Для `_gate` (оба профиля) и
        `two_sided.run` (без профиля, артель, компонент) маркер на момент
        вызова есть и равен `str(os.getpid())`; константа
        `liveness.GATE_OWNER_MARKER` равна `.artel-gate-owner`.

        Ловит мутацию: маркер пишется после `git worktree add` (на момент
        вызова его нет — сирота после обрыва между вызовами); маркер
        пишется только при профиле в границе (у артели его нет); в маркер
        записан не pid (пусто, ppid); маркер пишет только один из двух
        гейтов.
        """
        self.assertEqual(liveness.GATE_OWNER_MARKER, MARKER)
        pid = str(os.getpid())
        repo = self.root / "clone"
        repo.mkdir()
        for name, profile in (("артель", artel_profile()),
                              ("компонент", component_profile())):
            with self.subTest("_gate", profile=name):
                seen, in_repo = self.spy()
                with mock.patch.object(gitcmd, "in_repo", in_repo), \
                        mock.patch.object(gitcmd, "branch_head_sha",
                                          return_value="a" * 40), \
                        mock.patch.object(outcome_integrity.workspace,
                                          "task_repo", return_value=repo):
                    refusal = outcome_integrity._gate(
                        None, "T1", "task/t1", "refs/artifacts/T1", profile,
                        lambda *_a: "b" * 40, False)
                self.assertIsNotNone(refusal)
                self.assertTrue(seen, "git worktree add не вызван")
                self.assertEqual(seen[0][1], pid, seen)
        for name, profile in (("без профиля", None), ("артель", artel_profile()),
                              ("компонент", component_profile())):
            with self.subTest("two_sided.run", profile=name):
                seen, in_repo = self.spy()
                with mock.patch.object(gitcmd, "in_repo", in_repo), \
                        mock.patch.object(gitcmd, "branch_head_sha",
                                          return_value="a" * 40):
                    two_sided.run(repo, "task/t1", "b" * 40, [],
                                  profile=profile)
                self.assertTrue(seen, "git worktree add не вызван")
                self.assertEqual(seen[0][1], pid, seen)


class OrphanTempDirsTest(TempRootTest):

    def test_ac7_gate_dirs_orphan_unless_live_gate_marker(self):
        """Каталог выписки без маркера, с мёртвым pid или только с живым маркером канарейки — сирота `orphans-temp`; с живым `.artel-gate-owner` — нет.

        Сценарий: для обоих префиксов `artel-outcome-` и
        `artel-two-sided-` — четыре каталога во временном каталоге теста;
        `doctor._orphan_temp_dirs()` называет три из них и не называет
        каталог с живым маркером гейта.

        Ловит мутацию: каталоги выписок не входят в перечень проверки
        (сирота с мёртвым pid не называется); каталог без маркера считается
        живым; общий маркер канарейки `.artel-canary-owner` проверяется
        раньше ветки выписок и защищает каталог без маркера гейта; живой
        маркер гейта не защищает каталог.
        """
        live, dead = os.getpid(), dead_pid()
        expected, protected = [], []
        for prefix in PREFIXES:
            expected.append(self.gate_dir(prefix, None))
            expected.append(self.gate_dir(prefix, dead))
            expected.append(self.gate_dir(prefix, None, canary_pid=live))
            protected.append(self.gate_dir(prefix, live))
        found = [Path(p).resolve() for p in doctor._orphan_temp_dirs()]
        for path in expected:
            with self.subTest(sirota=path.name):
                self.assertIn(path.resolve(), found)
        for path in protected:
            with self.subTest(live=path.name):
                self.assertNotIn(path.resolve(), found)


class RecordingPopen(subprocess.Popen):
    calls: list = []

    def __init__(self, args, *rest, **kwargs):
        RecordingPopen.calls.append(list(args) if not isinstance(args, str)
                                    else [args])
        super().__init__(args, *rest, **kwargs)


def git_calls() -> list:
    return [c for c in RecordingPopen.calls
            if c and Path(str(c[0])).name == "git"]


class FixOrphanTempDirsTest(TempRootTest):

    def setUp(self):
        super().setUp()
        self.clone = self.root / "clone"
        self.git("init", "-q", "-b", "main", str(self.clone), cwd=self.root)
        (self.clone / "a.txt").write_text("a\n", encoding="utf-8")
        self.git("add", "a.txt")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                 "-m", "a")
        RecordingPopen.calls = []

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
        return tree

    def registered(self) -> set:
        out = self.git("worktree", "list", "--porcelain")
        return {str(Path(line.split(" ", 1)[1]).resolve())
                for line in out.splitlines() if line.startswith("worktree ")}

    def test_ac8_fix_removes_dead_gate_dir_and_prunes_its_worktree(self):
        """Уборка удаляет каталог выписки мёртвого владельца и убирает его запись `git worktree` в клоне; каталог и запись живого — остаются.

        Сценарий: в клоне во временном каталоге теста две выписки —
        `artel-outcome-*` с живым маркером гейта и `artel-two-sided-*` с
        маркером мёртвого pid; `orchestrator.doctor.orphans._project_clones`
        подменён на этот клон; `doctor._fix_orphan_temp_dirs()` зовётся
        напрямую. Мёртвый каталог удалён, его записи в `git worktree list`
        нет, подмена вызвана; живой каталог и его запись на месте.

        Ловит мутацию: каталог сироты удаляется без `git worktree prune`
        (запись остаётся в клоне); prune идёт мимо `_project_clones` модуля
        `orphans` (импорт имени — подмена не действует, клон теста не
        чистится); уборка удаляет и каталог живого владельца.
        """
        live = self.gate_dir("artel-outcome-", os.getpid())
        dead = self.gate_dir("artel-two-sided-", dead_pid())
        live_tree, dead_tree = self.checkout(live), self.checkout(dead)
        self.assertIn(str(dead_tree.resolve()), self.registered(),
                      "предпосылка: запись мёртвой выписки в клоне")
        with mock.patch("orchestrator.doctor.orphans._project_clones",
                        return_value=[self.clone]) as clones, \
                mock.patch.object(subprocess, "Popen", RecordingPopen):
            doctor._fix_orphan_temp_dirs()
        self.assertFalse(dead.exists(), "каталог мёртвого владельца не удалён")
        self.assertTrue(clones.called,
                        "удалён каталог выписки, а _project_clones не вызван")
        self.assertTrue(live.exists(), "удалён каталог живого владельца")
        registered = self.registered()
        self.assertNotIn(str(dead_tree.resolve()), registered,
                         "запись git worktree мёртвой выписки не убрана")
        self.assertIn(str(live_tree.resolve()), registered,
                      "убрана запись git worktree живой выписки")

    def test_ac8_fix_without_gate_deletions_does_not_call_git(self):
        """Уборка, не удалившая ни одного каталога выписки, git не зовёт — даже когда удалила сироту канарейки.

        Сценарий: во временном каталоге теста — `artel-outcome-*` с живым
        маркером гейта (его выписка зарегистрирована в клоне) и сирота
        `artel-canary-*` без маркера; `_project_clones` подменён на клон;
        `doctor._fix_orphan_temp_dirs()` зовётся напрямую. Сирота
        канарейки удалена, каталог выписки и его запись на месте, ни одного
        процесса `git` уборка не запустила.

        Ловит мутацию: `git worktree prune` выполняется на каждой уборке
        (или после удаления любого каталога, в том числе канарейки) —
        уборка трогает настоящие клоны пульта без повода.
        """
        live = self.gate_dir("artel-outcome-", os.getpid())
        live_tree = self.checkout(live)
        canary = Path(tempfile.mkdtemp(prefix="artel-canary-"))
        RecordingPopen.calls = []
        with mock.patch("orchestrator.doctor.orphans._project_clones",
                        return_value=[self.clone]), \
                mock.patch.object(subprocess, "Popen", RecordingPopen):
            doctor._fix_orphan_temp_dirs()
        self.assertFalse(canary.exists(),
                         "предпосылка: сирота канарейки не удалена")
        self.assertEqual(git_calls(), [], "уборка без удалений выписок звала git")
        self.assertTrue(live.exists())
        self.assertIn(str(live_tree.resolve()), self.registered())


if __name__ == "__main__":
    unittest.main()
