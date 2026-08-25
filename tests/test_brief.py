"""Юнит-тесты `orchestrator/brief.py` (T028): хэш компонента, сверка
свежести карты, сборка компонентов брифа — по отдельности, функциями
модуля, не через `runner.cmd_run` целиком (это делают приёмочные тесты
`tasks/T028/acceptance_tests/test_brief.py`, AC-1..AC-9).
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import brief, config, gitcmd, store  # noqa: E402

MAP_FRESH = ("---\nbuilt_at_sha: aaaa000011112222333344445555666677778888\n"
            "---\n\n# Карта\n")


def fake_git_clean(*args) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(list(args), 0, "", "")


def fake_git_stale(*paths):
    def fake(*args) -> subprocess.CompletedProcess:
        if args and args[0] == "diff":
            return subprocess.CompletedProcess(
                list(args), 0, "\n".join(paths) + "\n", "")
        return subprocess.CompletedProcess(list(args), 0, "", "")
    return fake


def fake_git_diff_fails(*args) -> subprocess.CompletedProcess:
    """git не отвечает на саму сверку свежести (`diff --name-only`) —
    например история переписана и `built_at_sha` в ней больше не найти."""
    if args and args[0] == "diff":
        return subprocess.CompletedProcess(
            list(args), 128, "", "fatal: bad revision ''")
    return subprocess.CompletedProcess(list(args), 0, "", "")


def fake_git_checkout_fails(*paths):
    """Сверка находит расхождение и checkout-восстановление после
    регенерации не удаётся — рабочее дерево остаётся грязным."""
    def fake(*args) -> subprocess.CompletedProcess:
        if args and args[0] == "diff":
            return subprocess.CompletedProcess(
                list(args), 0, "\n".join(paths) + "\n", "")
        if args and args[0] == "checkout":
            return subprocess.CompletedProcess(
                list(args), 1, "", "стенд: checkout упал")
        return subprocess.CompletedProcess(list(args), 0, "", "")
    return fake


class BriefUnitTest(unittest.TestCase):
    """Песочница: ROOT/TASKS/DB во tmpdir, карта и SPEC на месте."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        (self.root / "docs").mkdir(parents=True)
        (self.root / "docs" / "codebase-map.md").write_text(
            MAP_FRESH, encoding="utf-8")
        (self.root / "CLAUDE.md").write_text(
            "# Конвенции проекта\n", encoding="utf-8")
        (config.TASKS / "T001").mkdir(parents=True)
        (config.TASKS / "T001" / "SPEC.md").write_text(
            "# SPEC\n\nМаркер-текста-SPEC.\n", encoding="utf-8")

        store.create_schema(store.db())

    def journal_details(self, actor: str) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE actor=? ORDER BY id", (actor,))]


class ComponentHashTest(unittest.TestCase):

    def test_same_text_hashes_equal(self):
        self.assertEqual(brief.component_hash("абв"), brief.component_hash("абв"))

    def test_different_text_hashes_differ(self):
        self.assertNotEqual(brief.component_hash("абв"), brief.component_hash("где"))


class FreshMapTextTest(BriefUnitTest):

    def test_fresh_map_returns_the_file_as_is(self):
        with mock.patch.object(gitcmd, "git", fake_git_clean):
            text = brief.fresh_map_text(store.db(), "T001")

        self.assertEqual(text, MAP_FRESH)

    def test_stale_map_is_regenerated_and_the_new_text_is_used(self):
        regenerated = MAP_FRESH.replace("aaaa", "bbbb")

        def fake_run(cmd, **kwargs) -> subprocess.CompletedProcess:
            (self.root / "docs" / "codebase-map.md").write_text(
                regenerated, encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with mock.patch.object(gitcmd, "git",
                               fake_git_stale("orchestrator/runner.py")), \
                mock.patch("subprocess.run", side_effect=fake_run):
            text = brief.fresh_map_text(store.db(), "T001")

        self.assertEqual(text, regenerated)

    def test_failed_regeneration_marks_the_text_and_raises_an_alert(self):
        fail = subprocess.CompletedProcess(
            ["python3"], 1, "", "стенд: генератор упал")
        conn = store.db()

        with mock.patch.object(gitcmd, "git",
                               fake_git_stale("orchestrator/runner.py")), \
                mock.patch("subprocess.run", return_value=fail):
            text = brief.fresh_map_text(conn, "T001")

        self.assertIn("КАРТА НЕАКТУАЛЬНА", text)
        self.assertIn("orchestrator/runner.py", text)
        self.assertIn(MAP_FRESH, text, "исходная карта — не переписана")

        rows = conn.execute("SELECT message FROM alerts").fetchall()
        self.assertTrue(
            any("стенд: генератор упал" in (r["message"] or "") for r in rows),
            "алерт о сбое регенерации не найден")

    def test_no_regeneration_call_when_map_is_fresh(self):
        with mock.patch.object(gitcmd, "git", fake_git_clean), \
                mock.patch("subprocess.run") as run_mock:
            brief.fresh_map_text(store.db(), "T001")

        run_mock.assert_not_called()

    def test_failed_freshness_check_marks_the_text_and_raises_an_alert(self):
        """git не ответил на саму сверку (не только на регенерацию) —
        то же молчаливое доверие запрещено (REVIEW T028 итерация 1,
        замечание major)."""
        conn = store.db()

        with mock.patch.object(gitcmd, "git", fake_git_diff_fails), \
                mock.patch("subprocess.run") as run_mock:
            text = brief.fresh_map_text(conn, "T001")

        self.assertIn("КАРТА НЕАКТУАЛЬНА", text)
        self.assertIn(MAP_FRESH, text, "исходная карта — не переписана")
        run_mock.assert_not_called()

        rows = conn.execute("SELECT message FROM alerts").fetchall()
        self.assertTrue(
            any("сверка свежести карты не удалась" in (r["message"] or "")
               for r in rows),
            "алерт о сбое сверки свежести не найден")

    def test_regeneration_restores_the_working_tree_after_reading(self):
        """Регенерация не должна оставлять незакоммиченную правку в ROOT
        (REVIEW T028 итерация 1, blocker) — checkout восстанавливает файл
        сразу после чтения текста в память."""
        regenerated = MAP_FRESH.replace("aaaa", "bbbb")
        calls = []

        def fake_run(cmd, **kwargs) -> subprocess.CompletedProcess:
            (self.root / "docs" / "codebase-map.md").write_text(
                regenerated, encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        def fake_git(*args) -> subprocess.CompletedProcess:
            calls.append(args)
            return fake_git_stale("orchestrator/runner.py")(*args)

        with mock.patch.object(gitcmd, "git", fake_git), \
                mock.patch("subprocess.run", side_effect=fake_run):
            brief.fresh_map_text(store.db(), "T001")

        self.assertIn(("checkout", "--", brief.MAP_REL), calls)

    def test_failed_restore_after_regeneration_raises_an_alert(self):
        regenerated = MAP_FRESH.replace("aaaa", "bbbb")

        def fake_run(cmd, **kwargs) -> subprocess.CompletedProcess:
            (self.root / "docs" / "codebase-map.md").write_text(
                regenerated, encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        conn = store.db()
        with mock.patch.object(
                gitcmd, "git",
                fake_git_checkout_fails("orchestrator/runner.py")), \
                mock.patch("subprocess.run", side_effect=fake_run):
            text = brief.fresh_map_text(conn, "T001")

        self.assertEqual(text, regenerated, "текст всё равно используется")

        rows = conn.execute("SELECT message FROM alerts").fetchall()
        self.assertTrue(
            any("откат правки" in (r["message"] or "") for r in rows),
            "алерт о неудавшемся откате рабочего дерева не найден")


class DeveloperBriefTest(BriefUnitTest):

    def test_assembles_three_components_and_journals_their_hashes(self):
        conn = store.db()
        with mock.patch.object(gitcmd, "git", fake_git_clean):
            text = brief.developer_brief(conn, "T001")

        self.assertIn("Маркер-текста-SPEC.", text)
        self.assertIn(MAP_FRESH, text)
        self.assertIn("Конвенции проекта", text)

        details = self.journal_details("developer")
        self.assertEqual(len(details), 3)
        for label in ("tasks/T001/SPEC.md", "docs/codebase-map.md",
                     "CLAUDE.md"):
            self.assertTrue(any(label in d for d in details), details)


class AnalystMapComponentTest(BriefUnitTest):

    def test_adds_only_the_map_and_journals_one_hash(self):
        conn = store.db()
        with mock.patch.object(gitcmd, "git", fake_git_clean):
            text = brief.analyst_map_component(conn, "T001")

        self.assertIn(MAP_FRESH, text)
        self.assertNotIn("Маркер-текста-SPEC.", text, "SPEC — не вход analyst")

        details = self.journal_details("analyst")
        self.assertEqual(len(details), 1)
        self.assertIn("docs/codebase-map.md", details[0])


if __name__ == "__main__":
    unittest.main()
