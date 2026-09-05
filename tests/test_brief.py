"""Юнит-тесты `orchestrator/brief.py` (T028): хэш компонента, сверка
свежести карты, сборка компонентов брифа — по отдельности, функциями
модуля, не через `runner.cmd_run` целиком (это делают приёмочные тесты
`tasks/T028/acceptance_tests/test_brief.py`, AC-1..AC-9).
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import brief, config, context_package, gitcmd, store  # noqa: E402
from tests.sandbox import (TmpRootTest, disk_backed_ls_tree_files,  # noqa: E402
                           disk_backed_show, fake_git, fake_git_for)

MAP_FRESH = ("---\nbuilt_at_sha: aaaa000011112222333344445555666677778888\n"
            "---\n\n# Карта\n")


def fake_git_stale(*paths):
    """Сверка свежести карты находит расхождение по указанным путям."""
    return fake_git_for({"diff": (0, "\n".join(paths) + "\n", "")})


# git не отвечает на саму сверку свежести (`diff --name-only`) —
# например история переписана и `built_at_sha` в ней больше не найти.
fake_git_diff_fails = fake_git_for({"diff": (128, "", "fatal: bad revision ''")})


def fake_git_checkout_fails(*paths):
    """Сверка находит расхождение и checkout-восстановление после
    регенерации не удаётся — рабочее дерево остаётся грязным."""
    return fake_git_for({
        "diff": (0, "\n".join(paths) + "\n", ""),
        "checkout": (1, "", "стенд: checkout упал"),
    })


class BriefUnitTest(TmpRootTest):
    """Песочница: sandbox.TmpRootTest полным набором путей (SPEC T061,
    AC-3) — карта и SPEC остаются собственной фикстурой этого файла."""

    def setUp(self):
        super().setUp()
        (self.root / "docs").mkdir(parents=True)
        (self.root / "docs" / "codebase-map.md").write_text(
            MAP_FRESH, encoding="utf-8")
        (self.root / "CLAUDE.md").write_text(
            "# Конвенции проекта\n", encoding="utf-8")
        (config.TASKS / "T001").mkdir(parents=True)
        (config.TASKS / "T001" / "SPEC.md").write_text(
            "# SPEC\n\nМаркер-текста-SPEC.\n", encoding="utf-8")

        store.create_schema(store.db())

        # `artifact_source.resolve` теперь ВСЕГДА `foreign=True` (A7) —
        # бриф читает SPEC/QUESTIONS/ANSWER через `gitcmd.show`/
        # `ls_tree_files`, не с диска напрямую. `fake_git` (патчится
        # локально каждым тестом этого файла) отвечает пустым успехом на
        # ЛЮБУЮ подкоманду, включая `show`/`ls-tree` несуществующего
        # файла — из-за этого `_branch_or_disk_text`/`_latest_answer_rel`
        # видели бы фиктивное непустое содержимое там, где на диске
        # ничего нет. Эта песочница без настоящего git ведёт диск
        # `config.TASKS` как единственный источник истины (тем же
        # приёмом, что `tests.sandbox.TmpRootTest`-наследники в других
        # файлах).
        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)

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
        with mock.patch.object(gitcmd, "git", fake_git):
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
        with mock.patch.object(gitcmd, "git", fake_git), \
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

        def fake_git_with_calls(*args) -> subprocess.CompletedProcess:
            calls.append(args)
            return fake_git_stale("orchestrator/runner.py")(*args)

        with mock.patch.object(gitcmd, "git", fake_git_with_calls), \
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
        with mock.patch.object(gitcmd, "git", fake_git):
            text = brief.developer_brief(conn, "T001")

        self.assertIn("Маркер-текста-SPEC.", text)
        self.assertIn(MAP_FRESH, text)
        self.assertIn("Конвенции проекта", text)

        details = self.journal_details("developer")
        self.assertEqual(len(details), 3)
        for label in ("tasks/T001/SPEC.md", "docs/codebase-map.md",
                     "CLAUDE.md"):
            self.assertTrue(any(label in d for d in details), details)


class DeveloperBriefStaleMapManifestTest(BriefUnitTest):
    """R1-F4 (REVIEW.md итерация 1, minor): опись компонента карты
    обязана нести размер/sha256 ИСХОДНОГО файла на диске, а не текста с
    примешанной пометкой «КАРТА НЕАКТУАЛЬНА» — иначе sha256 из описи
    расходится с `sha256sum docs/codebase-map.md`, пока карта стухшая."""

    def test_manifest_sha256_matches_the_file_on_disk_even_when_stale(self):
        conn = store.db()
        with mock.patch.object(gitcmd, "git", fake_git_diff_fails):
            text = brief.developer_brief(conn, "T001")

        self.assertIn("КАРТА НЕАКТУАЛЬНА", text, "пометка обязана остаться видна роли")
        expected_sha = context_package.sha256_of(MAP_FRESH)
        expected_size = len(MAP_FRESH.encode("utf-8"))
        self.assertIn(
            expected_sha, text,
            "опись обязана нести sha256 исходного файла карты (без "
            "пометки), а не текста с примешанной пометкой стухлости")
        self.assertIn(str(expected_size), text,
                     "опись обязана нести размер исходного файла карты")


class AnalystMapComponentTest(BriefUnitTest):

    def test_adds_only_the_map_and_journals_one_hash(self):
        conn = store.db()
        with mock.patch.object(gitcmd, "git", fake_git):
            text = brief.analyst_map_component(conn, "T001")

        self.assertIn(MAP_FRESH, text)
        self.assertNotIn("Маркер-текста-SPEC.", text, "SPEC — не вход analyst")

        details = self.journal_details("analyst")
        self.assertEqual(len(details), 1)
        self.assertIn("docs/codebase-map.md", details[0])


class AnswerComponentTest(BriefUnitTest):
    """SPEC T075, AC-6: ANSWER-n.md/QUESTIONS.md — добавка брифа, не его
    обязательная часть. `DeveloperBriefTest`/`AnalystMapComponentTest`
    выше уже проверяют регрессию «нет ANSWER — состав брифа не меняется»
    (три/один журналируемых компонента без правки этого файла); здесь —
    то, что этой регрессией не покрыто: содержимое, когда ANSWER есть, и
    выбор ПОСЛЕДНЕГО файла при нескольких раундах."""

    def test_developer_brief_includes_the_only_answer(self):
        (config.TASKS / "T001" / "ANSWER-1.md").write_text(
            "---\ntask: T001\ntype: answer\nauthor_role: operator\n"
            "status: ready\nschema_version: 2\n---\n\n"
            "# ANSWER-1: ответ Оператора\n\n## Ответы\n\nМАРКЕР-ANSWER-1\n",
            encoding="utf-8")
        conn = store.db()
        with mock.patch.object(gitcmd, "git", fake_git):
            text = brief.developer_brief(conn, "T001")

        self.assertIn("МАРКЕР-ANSWER-1", text)
        self.assertIn("tasks/T001/ANSWER-1.md", text)

    def test_developer_brief_picks_the_latest_of_several_answers(self):
        for n in (1, 2, 10):
            (config.TASKS / "T001" / f"ANSWER-{n}.md").write_text(
                "---\ntask: T001\ntype: answer\nauthor_role: operator\n"
                "status: ready\nschema_version: 2\n---\n\n"
                f"# ANSWER-{n}: ответ Оператора\n\n## Ответы\n\n"
                f"МАРКЕР-ANSWER-{n}\n",
                encoding="utf-8")
        conn = store.db()
        with mock.patch.object(gitcmd, "git", fake_git):
            text = brief.developer_brief(conn, "T001")

        self.assertIn("МАРКЕР-ANSWER-10", text,
                      "номер сравнивается как число (10 > 2), не строкой")
        self.assertNotIn("МАРКЕР-ANSWER-1\n", text)
        self.assertNotIn("МАРКЕР-ANSWER-2\n", text)

    def test_analyst_brief_pairs_questions_with_the_answer(self):
        (config.TASKS / "T001" / "QUESTIONS.md").write_text(
            "---\ntask: T001\ntype: questions\nauthor_role: analyst\n"
            "status: draft\nschema_version: 2\n---\n\n# QUESTIONS\n\n"
            "## Вопросы\n\n1. **Вопрос?** — МАРКЕР-QUESTION — дефолт: A.\n",
            encoding="utf-8")
        (config.TASKS / "T001" / "ANSWER-1.md").write_text(
            "---\ntask: T001\ntype: answer\nauthor_role: operator\n"
            "status: ready\nschema_version: 2\n---\n\n"
            "# ANSWER-1: ответ Оператора\n\n## Ответы\n\nМАРКЕР-ANSWER\n",
            encoding="utf-8")
        conn = store.db()
        with mock.patch.object(gitcmd, "git", fake_git):
            text = brief.analyst_map_component(conn, "T001")

        self.assertIn("МАРКЕР-QUESTION", text)
        self.assertIn("МАРКЕР-ANSWER", text)


class SkillsTextTest(BriefUnitTest):
    """R1-F1 (REVIEW.md итерация 1, minor): `skills_text` журналирует
    хэши скилов ОДНИМ проходом ПОСЛЕ подтверждения, что все скилы роли
    прочитаны — отказ чтения скила N не должен оставлять в журнале
    запись про скилы <N для шага, который так и не стартовал."""

    def setUp(self):
        super().setUp()
        (self.root / "skills").mkdir(parents=True)

    def test_journals_all_skills_after_all_succeed(self):
        (self.root / "skills" / "a.md").write_text(
            "# Скил A\n", encoding="utf-8")
        (self.root / "skills" / "b.md").write_text(
            "# Скил B\n", encoding="utf-8")
        conn = store.db()

        text, reason = brief.skills_text(conn, "T001", "developer",
                                         ["a", "b"])

        self.assertEqual(reason, "")
        self.assertIn("Скил A", text)
        self.assertIn("Скил B", text)
        details = self.journal_details("developer")
        self.assertEqual(len(details), 2)
        self.assertTrue(any("skills/a.md" in d for d in details))
        self.assertTrue(any("skills/b.md" in d for d in details))

    def test_no_partial_journal_when_a_later_skill_fails(self):
        (self.root / "skills" / "a.md").write_text(
            "# Скил A\n", encoding="utf-8")
        # skills/b.md намеренно отсутствует на диске — имитирует отказ
        # чтения второго скила роли.
        conn = store.db()

        text, reason = brief.skills_text(conn, "T001", "developer",
                                         ["a", "b"])

        self.assertIsNone(text)
        self.assertIn("skills/b.md", reason)
        details = self.journal_details("developer")
        self.assertEqual(
            details, [],
            "отказ чтения второго скила не должен оставлять в журнале "
            "запись про первый — шаг так и не стартовал")


class ReturnReasonComponentTest(BriefUnitTest):
    """tasks/01M1SAA2AZX3ERQ779QJ5TS9J4, требования 1-5: раздел «Причина
    возврата» — юнит-покрытие поверх приёмочных тестов задачи
    (`tasks/01M1SAA2AZX3ERQ779QJ5TS9J4/acceptance_tests/`, залоченных
    tasks/T023), тем же приёмом сырой сеянной истории журнала."""

    def seed_state(self, actor: str, state: str, detail: str = "") -> None:
        store.journal(store.db(), "T001", actor, f"state -> {state}", detail)

    def test_developer_brief_carries_verbatim_reason_after_changes_requested(self):
        """Ловит мутацию: раздел «Причина возврата» добавлен НЕ первым
        элементом `parts` (например, после `_manifest_component` SPEC) —
        порядок требования 3/AC-4 сломан, хотя текст детали присутствует."""
        conn = store.db()
        self.seed_state("fsm", "in_dev", "приёмочные тесты готовы")
        self.seed_state("operator", "review", "готово к ревью")
        self.seed_state("fsm", "in_dev", "замечания ревью, итерация 1")

        with mock.patch.object(gitcmd, "git", fake_git):
            text = brief.developer_brief(conn, "T001")

        self.assertIn(brief.RETURN_REASON_HEADER, text)
        self.assertIn("замечания ревью, итерация 1", text)
        self.assertIn(brief.RETURN_REASON_CLOSING, text)
        self.assertLess(text.find(brief.RETURN_REASON_HEADER),
                        text.find("Маркер-текста-SPEC."))

    def test_developer_brief_unchanged_after_normal_advance_from_tests_writing(self):
        """Ловит мутацию: предшественник `tests_writing` по ошибке добавлен
        в `_RETURN_TRIGGER_STATES` — обычный первый заход `in_dev` (не
        возврат) получил бы раздел «Причина возврата», хотя требование
        5/AC-6 запрещают его для штатного advance."""
        conn = store.db()
        self.seed_state("operator", "tests_writing",
                        "гейт SPEC пройден — приёмочные тесты до кода")
        self.seed_state("fsm", "in_dev",
                        "приёмочные тесты готовы — трассируемость AC пройдена")

        with mock.patch.object(gitcmd, "git", fake_git):
            text = brief.developer_brief(conn, "T001")

        self.assertNotIn(brief.RETURN_REASON_HEADER, text)

    def test_developer_brief_after_escalation_return_shows_escalated_detail_not_fixed_phrase(self):
        """Ловит мутацию: `_return_context` берёт `detail` записи
        `state -> in_dev` (фиксированная фраза approve «эскалация
        разрешена, продолжаем») вместо `detail` записи `state ->
        escalated` — раздел нёс бы бессодержательную фразу вместо причины
        эскалации (требование 2/AC-3)."""
        conn = store.db()
        self.seed_state("fsm", "in_dev", "приёмочные тесты готовы")
        self.seed_state("operator", "review", "готово к ревью")
        self.seed_state("fsm", "escalated",
                        "лимит ревью 3 исчерпан")
        (config.TASKS / "T001" / "ANSWER-1.md").write_text(
            "---\ntask: T001\ntype: answer\nauthor_role: operator\n"
            "status: ready\nschema_version: 2\n---\n\n# ANSWER-1\n\nОК.\n",
            encoding="utf-8")
        self.seed_state("operator", "in_dev", "эскалация разрешена, продолжаем")

        with mock.patch.object(gitcmd, "git", fake_git):
            text = brief.developer_brief(conn, "T001")

        self.assertIn(brief.RETURN_REASON_HEADER, text)
        self.assertIn("лимит ревью 3 исчерпан", text)
        self.assertIn("tasks/T001/ANSWER-1.md", text)
        span_start = text.find(brief.RETURN_REASON_HEADER)
        span_end = text.find(brief.RETURN_REASON_CLOSING, span_start)
        self.assertNotIn("эскалация разрешена, продолжаем",
                        text[span_start:span_end],
                        "фиксированная фраза approve — не содержательная "
                        "причина, не должна занимать место раздела")

    def test_analyst_brief_no_section_on_first_visit(self):
        """Ловит мутацию: `_return_context` не возвращает `None`, когда
        записи `state -> spec_writing` этой задачи нет вовсе (первый визит)
        — раздел «Причина возврата» появился бы у analyst без реального
        возврата (требование 5/AC-6)."""
        conn = store.db()

        with mock.patch.object(gitcmd, "git", fake_git):
            text = brief.analyst_map_component(conn, "T001")

        self.assertNotIn(brief.RETURN_REASON_HEADER, text)

    def test_test_author_brief_carries_return_reason_after_escalation(self):
        """Ловит мутацию: `test_author_answer_component` не подключает
        `_return_reason_component` вовсе (сборщик обновлён только для
        developer/analyst) — раздел «Причина возврата» отсутствовал бы у
        test_author при возврате из эскалации (требование 1)."""
        conn = store.db()
        self.seed_state("operator", "tests_writing",
                        "гейт SPEC пройден — приёмочные тесты до кода")
        self.seed_state("fsm", "escalated",
                        "test_author: критерий неисполним тестом — AC-7")
        (config.TASKS / "T001" / "ANSWER-1.md").write_text(
            "---\ntask: T001\ntype: answer\nauthor_role: operator\n"
            "status: ready\nschema_version: 2\n---\n\n# ANSWER-1\n\nОК.\n",
            encoding="utf-8")
        self.seed_state("operator", "tests_writing",
                        "эскалация разрешена, продолжаем")

        with mock.patch.object(gitcmd, "git", fake_git):
            text = brief.test_author_answer_component(conn, "T001")

        self.assertIsNotNone(text)
        self.assertIn(brief.RETURN_REASON_HEADER, text)
        self.assertIn("test_author: критерий неисполним тестом — AC-7", text)


if __name__ == "__main__":
    unittest.main()
