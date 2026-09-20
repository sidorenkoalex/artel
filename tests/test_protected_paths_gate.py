"""Юнит-тесты защищённых путей — единый список, гейт зон и гейт мержа
(tasks/01M27JPEGCGMDDRX5A98QWJW0Z/SPEC.md): чистые функции
`fsm_advance._protected_paths_touched`/`_protected_path_refusal_detail`,
`fsm_merge_gate._protected_path_diff_gate`/`_protected_path_refusal_detail`
— сценарии AC-1..AC-5 уже кроют `tasks/01M27JPEGCGMDDRX5A98QWJW0Z/
acceptance_tests/` (залочены, tasks/T023), здесь — грани, которые
приёмочная планка намеренно не проверяет: приоритет защищённого пути над
обычным «вне зон» отказом при смешанном диффе, скип внешнего target'а на
гейте мержа, fail-open (не `sys.exit`) на неответившем git у гейта мержа.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (config, fsm_advance, fsm_merge_gate,  # noqa: E402
                          gitcmd, repo_context, store)
from tests.sandbox import TaskIdSchemaConnTmpRootTest, TmpRootTest  # noqa: E402


class ProtectedPathsTouchedTest(unittest.TestCase):

    def test_matches_are_filtered_preserving_order(self):
        """Ловит мутацию: фильтр возвращает не подмножество `files` в их
        исходном порядке, а что-то ещё (весь список PROTECTED_PATHS,
        отсортированный список и т.п.)."""
        files = ["orchestrator/store.py", "CLAUDE.md", "tests/foo.py",
                "gates.yaml"]
        self.assertEqual(
            fsm_advance._protected_paths_touched(files),
            ["CLAUDE.md", "gates.yaml"])

    def test_directory_protected_path_matches_nested_file(self):
        """Ловит мутацию: сравнение сужено до точного равенства — файл
        ПОД защищённым каталогом (`.github/workflows/ci.yml`) обязан
        матчиться префиксом `.github/`, как и `docs/adr/0001.md` под
        `docs/adr/`."""
        files = [".github/workflows/ci.yml", "docs/adr/0001-foo.md",
                "orchestrator/config.py"]
        self.assertEqual(
            fsm_advance._protected_paths_touched(files),
            [".github/workflows/ci.yml", "docs/adr/0001-foo.md"])

    def test_unrelated_files_are_not_touched(self):
        self.assertEqual(
            fsm_advance._protected_paths_touched(
                ["orchestrator/store.py", "tests/test_store.py"]),
            [])


class ProtectedPathRefusalDetailTest(unittest.TestCase):

    def test_single_path_named_text(self):
        self.assertEqual(
            fsm_advance._protected_path_refusal_detail(["gates.yaml"]),
            "защищённый путь gates.yaml — правит только Оператор "
            "коммитом в main; предложи правку приложением к PLAN "
            "(unified-дифф)")

    def test_multiple_paths_are_joined(self):
        detail = fsm_advance._protected_path_refusal_detail(
            ["gates.yaml", "CLAUDE.md"])
        self.assertEqual(
            detail,
            "защищённый путь gates.yaml, CLAUDE.md — правит только "
            "Оператор коммитом в main; предложи правку приложением к "
            "PLAN (unified-дифф)")

    def test_zones_gate_and_merge_gate_texts_are_byte_identical(self):
        """Требование 4 SPEC: «оба отказа несут один и тот же именованный
        текст» — ловит мутацию, где текст гейта мержа тихо разошёлся с
        текстом гейта зон (перефразировка, другой порядок слов)."""
        self.assertEqual(
            fsm_advance._protected_path_refusal_detail(["gates.yaml"]),
            fsm_merge_gate._protected_path_refusal_detail(["gates.yaml"]))


class ZonesGateProtectedPathPriorityTest(TaskIdSchemaConnTmpRootTest):
    """Дифф, где ОДНОВРЕМЕННО есть защищённый путь и обычный файл вне
    заявленных zones (не защищённый) — отказ обязан называть только
    защищённый путь (требование 2 срабатывает раньше проверки zones),
    не смешивать его с обычным текстом «дифф трогает файлы вне
    заявленных zones»."""

    def test_protected_path_wins_over_ordinary_out_of_zone_refusal(self):
        t = {"title": "Тест", "branch": "task/t001-x",
             "zones": "orchestrator/store.py", "zones_extension": None}
        with mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(
                 gitcmd, "diff_names",
                 return_value=["gates.yaml", "orchestrator/other.py"]):
            refuses = fsm_advance._zones_gate_refuses(
                self.conn, self.task_id, t, "task/t001-x", "PLAN\n")
        self.assertTrue(refuses)
        details = [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=?", (self.task_id,))]
        combined = " ".join(details)
        self.assertIn(
            "защищённый путь gates.yaml — правит только Оператор "
            "коммитом в main; предложи правку приложением к PLAN "
            "(unified-дифф)", combined)
        self.assertNotIn("вне заявленных zones", combined)


class MergeGateProtectedPathDiffGateTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T001"
        store.insert_task(self.conn, self.task_id, "Задача", "merge_gate",
                          "task/t001-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.self_ctx = repo_context.RepoContext(
            path=config.ROOT, remote="origin", base=config.MAIN_BRANCH)

    def test_external_target_never_calls_diff_base(self):
        """Ловит мутацию: проверка `ctx.path != config.ROOT` убрана —
        гейт мержа звонил бы `gitcmd.diff_base` и на внешний target,
        чей клон и защищённые пути этого списка (файлы пульта) не имеют
        отношения друг к другу."""
        ext_ctx = repo_context.RepoContext(
            path=config.PROJECTS / "extproj" / "workspace",
            remote="origin", base="main")
        with mock.patch.object(gitcmd, "diff_base") as diff_base:
            escalated = fsm_merge_gate._protected_path_diff_gate(
                self.conn, self.task_id, "merge_gate", "task/t001-x",
                ext_ctx)
        self.assertFalse(escalated)
        diff_base.assert_not_called()

    def test_git_not_answering_diff_base_does_not_escalate_or_exit(self):
        """Fail-open здесь намеренно (докстринг `_protected_path_diff_gate`):
        сломанный git тем же вызовом всё равно упрётся в `sys.exit` на
        следующих узлах гейта (публикация головы/merge) — эта проверка
        не обязана дублировать тот отказ `sys.exit`'ом.

        Ловит мутацию: `base is None` не проверен — `gitcmd.diff_names`
        зовётся с `None` вместо реального sha."""
        with mock.patch.object(gitcmd, "diff_base", return_value=None), \
             mock.patch.object(gitcmd, "diff_names") as diff_names:
            escalated = fsm_merge_gate._protected_path_diff_gate(
                self.conn, self.task_id, "merge_gate", "task/t001-x",
                self.self_ctx)
        self.assertFalse(escalated)
        diff_names.assert_not_called()
        row = self.conn.execute("SELECT state FROM tasks WHERE id=?",
                                (self.task_id,)).fetchone()
        self.assertEqual(row["state"], "merge_gate")

    def test_git_not_answering_diff_names_does_not_escalate(self):
        with mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names", return_value=None):
            escalated = fsm_merge_gate._protected_path_diff_gate(
                self.conn, self.task_id, "merge_gate", "task/t001-x",
                self.self_ctx)
        self.assertFalse(escalated)

    def test_no_protected_path_in_diff_does_not_escalate(self):
        with mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names",
                               return_value=["orchestrator/store.py"]):
            escalated = fsm_merge_gate._protected_path_diff_gate(
                self.conn, self.task_id, "merge_gate", "task/t001-x",
                self.self_ctx)
        self.assertFalse(escalated)
        row = self.conn.execute("SELECT state FROM tasks WHERE id=?",
                                (self.task_id,)).fetchone()
        self.assertEqual(row["state"], "merge_gate")

    def test_protected_path_escalates_with_named_text(self):
        with mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(
                 gitcmd, "diff_names",
                 return_value=["gates.yaml", "CLAUDE.md"]):
            escalated = fsm_merge_gate._protected_path_diff_gate(
                self.conn, self.task_id, "merge_gate", "task/t001-x",
                self.self_ctx)
        self.assertTrue(escalated)
        row = self.conn.execute("SELECT state FROM tasks WHERE id=?",
                                (self.task_id,)).fetchone()
        self.assertEqual(row["state"], "escalated")
        details = [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=?", (self.task_id,))]
        combined = " ".join(details)
        self.assertIn("gates.yaml", combined)
        self.assertIn("CLAUDE.md", combined)
        self.assertIn(
            "правит только Оператор коммитом в main; предложи правку "
            "приложением к PLAN (unified-дифф)", combined)


if __name__ == "__main__":
    unittest.main()


class AgentsMdIsProtectedTest(unittest.TestCase):
    """Решение Оператора 11.09: AGENTS.md — символьная ссылка на CLAUDE.md,
    как путь обязан стоять в списке защищённых, иначе роль подменяет
    инструкции агентам, заменив ссылку обычным файлом."""

    def test_agents_md_is_in_protected_paths(self):
        """Ловит мутацию: AGENTS.md выпал из PROTECTED_PATHS."""
        self.assertIn("AGENTS.md", config.PROTECTED_PATHS)


class ModelsCatalogNotYetProtectedTest(unittest.TestCase):
    """Решение Оператора 20.09 (возврат из verifying задачи
    01M3009Y9AGGY6ZCFA7H1HJ1TD): каталог моделей входит в
    `config.PROTECTED_PATHS` частью 2 линии (01M300A14K), не этой веткой
    — CI-джоб `protected-paths` читает список из ветки PR, и ветка,
    которая создаёт файл и объявляет его защищённым одним мержем, красит
    собственный PR."""

    def test_models_yaml_is_not_in_protected_paths_until_part_two(self):
        """Ловит мутацию: `models.yaml` вернули в список этой веткой —
        джоб `protected-paths` снова читает объявление из ветки PR,
        видит создание файла и падает, а обойти его приложением к PLAN
        нельзя (гейт приложений сверяется со списком главной копии)."""
        self.assertNotIn("models.yaml", config.PROTECTED_PATHS)
        self.assertEqual(
            fsm_advance._protected_paths_touched(
                ["models.yaml", "orchestrator/models.py"]),
            [])

    def test_gate_reads_the_list_of_the_main_copy_at_call_time(self):
        """Гейт читает `config.PROTECTED_PATHS` В МОМЕНТ проверки, а не
        снимком при импорте: как только часть 2 внесёт `models.yaml` в
        список главной копии, тот же дифф начнёт отказывать без правок
        самого гейта.

        Ловит мутацию: список снят снимком при импорте модуля гейта
        (константа рядом с функцией) — подмена `config.PROTECTED_PATHS`
        перестала бы влиять на вердикт, и защита каталога, включённая
        частью 2, не заработала бы вовсе."""
        after_part_two = tuple(config.PROTECTED_PATHS) + ("models.yaml",)

        with mock.patch.object(config, "PROTECTED_PATHS", after_part_two):
            touched = fsm_advance._protected_paths_touched(
                ["models.yaml", "orchestrator/config.py"])

        self.assertEqual(touched, ["models.yaml"])
