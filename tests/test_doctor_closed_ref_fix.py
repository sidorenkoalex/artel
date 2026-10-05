"""Юнит-тесты досылки коммита закрытия `doctor --fix` из главной копии
пульта и порядка починок `cmd_doctor(fix=True)` (SPEC
01M446WV7S94FTZGJCGMPJ667F, требования 3-4; AC-6…AC-8).

Песочница — настоящий git: главная копия пульта, bare `origin` рядом и
клон артели, заведённый `workspace.ensure_clone` из этого `origin` —
отдельный репозиторий (`ARTEL_CLONE_IS_ROOT = False`). Коммит закрытия
собирается в главной копии `commit-tree` и в клоне отсутствует — так жили
коммиты закрытия переходного периода этапа 2 ADR-0021.
"""
import shutil
import subprocess
import unittest
from unittest import mock

from orchestrator import config, doctor, snapshot, store, workspace
from tests.sandbox import _PROJECT_TARGET_ENTRY, RealGitSandbox, capture

TASK = "01UNITCLOSEDREFFIX00000001"


class MainCopyClosingSandbox(RealGitSandbox):

    ARTEL_CLONE_IS_ROOT = False

    def setUp(self):
        super().setUp()
        self.origin = self.root.parent / f"{self.root.name}-origin.git"
        self.git("clone", "-q", "--bare", str(self.root), str(self.origin))
        self.addCleanup(shutil.rmtree, self.origin, True)
        config.TARGETS.write_text(
            "targets:\n" + _PROJECT_TARGET_ENTRY.format(
                name=config.DEFAULT_TARGET, base=config.MAIN_BRANCH).replace(
                f"file:///nonexistent/{config.DEFAULT_TARGET}",
                str(self.origin)),
            encoding="utf-8")
        capture(workspace.ensure_clone, config.DEFAULT_TARGET)
        self.clone = workspace.repo(config.DEFAULT_TARGET)
        self.assertTrue((self.clone / ".git").exists(), "предусловие: клон")
        self.conn = store.db()
        self.ref = f"refs/artifacts/{TASK}"

    def main_copy_commit(self, note: str) -> str:
        """Коммит главной копии, не удерживаемый ни одной ссылкой: его нет
        ни в `origin`, ни в клоне."""
        where = ("-C", str(self.root), "-c", "user.name=t",
                 "-c", "user.email=t@example.invalid")
        tree = self.git(*where, "rev-parse", "HEAD^{tree}").strip()
        return self.git(*where, "commit-tree", tree, "-p", "HEAD",
                        "-m", note).strip()

    def close_task(self, closing: str, target: str = config.DEFAULT_TARGET):
        store.insert_task(self.conn, TASK, "Задача", "killed",
                          f"task/{TASK.lower()}-x", target, 25.0)
        store.journal(self.conn, TASK, "orchestrator", snapshot.CLOSING_ACTION,
                      f"{self.ref} <- {closing} (killed)")
        self.assertEqual(snapshot.closing_sha(self.conn, TASK), closing)

    def in_clone(self, sha: str) -> bool:
        res = subprocess.run(["git", "-C", str(self.clone), "cat-file", "-e",
                              f"{sha}^{{commit}}"], capture_output=True)
        return res.returncode == 0

    def origin_head(self) -> str:
        out = self.git("-C", str(self.origin), "for-each-ref",
                       "--format=%(objectname)", self.ref)
        return out.strip()


class ResendFromMainCopyTest(MainCopyClosingSandbox):

    def test_closing_commit_only_in_main_copy_reaches_origin(self):
        """Коммита закрытия нет в клоне, есть в главной копии, ссылки в
        origin нет — после `--fix` ссылка в origin равна коммиту закрытия.

        Ловит мутацию: досылка по-прежнему требует локальной ссылки в
        клоне (`_local_head != closing -> continue`) или не ищет объект в
        главной копии — origin остаётся без ссылки.
        """
        closing = self.main_copy_commit("закрытие")
        self.assertFalse(self.in_clone(closing), "предусловие")
        self.close_task(closing)

        out = capture(doctor._fix_unsent_closed_refs, self.conn)

        self.assertEqual(self.origin_head(), closing, out)
        self.assertIn(TASK, out)
        self.assertIn("[FIX]", out)

    def test_non_advancing_push_is_rejected_and_named(self):
        """Ссылка в origin указывает на коммит, которого коммит закрытия не
        продолжает: досылка без force отклоняется, origin не меняется, а
        строка `[FIX]` называет задачу и «не дослан».

        Ловит мутацию: досылка из главной копии идёт с `--force` (или
        `+<sha>:<ref>`) — ссылка в origin перезаписывается коммитом
        закрытия.
        """
        other = self.main_copy_commit("чужая голова")
        self.git("-C", str(self.root), "push", "-q", str(self.origin),
                 f"{other}:{self.ref}")
        closing = self.main_copy_commit("закрытие")
        self.close_task(closing)

        out = capture(doctor._fix_unsent_closed_refs, self.conn)

        self.assertEqual(self.origin_head(), other, out)
        line = [l for l in out.splitlines() if "[FIX]" in l and TASK in l]
        self.assertTrue(line, out)
        self.assertIn("не дослан", line[0])


class ClosingCommitNowhereTest(MainCopyClosingSandbox):

    def test_missing_everywhere_prints_fix_line(self):
        """Коммита закрытия нет ни в клоне, ни в главной копии — строка
        `[FIX]` с id задачи и коммитом закрытия, origin не тронут.

        Ловит мутацию: отсутствие объекта пропускается молча (прежний
        `continue` без вывода) — строки с id и коммитом закрытия нет.
        """
        closing = "a1" * 20
        self.close_task(closing)

        out = capture(doctor._fix_unsent_closed_refs, self.conn)

        self.assertEqual(self.origin_head(), "")
        line = [l for l in out.splitlines() if "[FIX]" in l and TASK in l]
        self.assertTrue(line, out)
        self.assertIn(closing, line[0])

    def test_external_project_does_not_search_main_copy(self):
        """Задача внешнего проекта: объект есть только в главной копии
        пульта — он оттуда не досылается, печатается та же строка `[FIX]`.

        Ловит мутацию: поиск в главной копии без условия «задача артели» —
        коммит закрытия внешнего проекта уходит в origin из git пульта.
        """
        closing = self.main_copy_commit("закрытие внешнего")

        out = capture(doctor.artifact_branches._fix_unsent_closed_ref,
                      TASK, "external", self.clone, closing)

        self.assertEqual(self.origin_head(), "")
        self.assertIn("[FIX]", out)
        self.assertIn(TASK, out)
        self.assertIn(closing, out)


class DoctorFixOrderTest(unittest.TestCase):

    def test_project_clones_before_closed_refs_before_checks(self):
        """`cmd_doctor(fix=True)`: заведение клонов — раньше досылки
        закрытых ссылок, обе — раньше `all_checks`.

        Ловит мутацию: `_fix_project_clones` остаётся в конце блока
        `--fix` (после `_fix_unsent_closed_refs`) — досылка на свежем пульте
        не видит клона.
        """
        calls = []
        record = lambda name: (lambda *a, **k: calls.append(name))
        names = ("_fix_ignored_artifact_files", "_fix_unsent_closed_refs",
                 "_fix_dead_lease_groups", "_fix_hung_test_runs",
                 "fix_models_local", "_fix_git_hooks", "_fix_project_clones")
        patches = [mock.patch.object(doctor, n, record(n)) for n in names]
        patches += [
            mock.patch.object(doctor, "all_checks",
                              lambda conn: calls.append("all_checks") or []),
            mock.patch.object(doctor.store, "db", lambda: None),
            mock.patch.object(doctor.runner, "wave_breaker_alerts_open",
                              lambda conn: []),
            mock.patch.object(doctor.alerts, "open_alerts",
                              lambda conn, kind: []),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        capture(lambda: doctor.cmd_doctor(fix=True))

        self.assertLess(calls.index("_fix_project_clones"),
                        calls.index("_fix_unsent_closed_refs"), calls)
        self.assertLess(calls.index("_fix_unsent_closed_refs"),
                        calls.index("all_checks"), calls)


if __name__ == "__main__":
    unittest.main()
