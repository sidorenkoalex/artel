"""Сторожа выноса документов задачи из рабочей копии кода (ADR-0021 пп. 2,
7, 13, этап 1; SPEC 01M409YKM3QE5KVRGV0G94F5ZC, требования 1-4, 7).

Документы задачи лежат в каталоге документов `.artel/projects/<проект>/
tasks/<id>/` (`artifact_branch.docs_dir`): выкладка из ссылки перед шагом
(`runner.role_cwd`), автокоммит правки роли оттуда в ссылку
(`checkpoint.commit_step_artifacts`), рабочая копия кода документов не
несёт, `acceptance_tests/` в ней — только на время прогона
(`acceptance.plank_in_code_copy`). Команду шага у обоих провайдеров и cwd
шага сторожит долгоживущий файл задачи
(`tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py`); здесь — узлы
выкладки, автокоммита и прогона на настоящем git.
"""
import unittest
from unittest import mock

from orchestrator import (acceptance, artifact_branch, checkpoint, config,
                          fixation, providers, role_prompt, runner, store,
                          workspace)
from tests.sandbox import RealGitSandbox

TASK = "01M409YKM3QE5KVRGV0G94F5ZC"
BRANCH = f"task/{TASK.lower()}-docs"
SPEC_TEXT = "---\ntask: x\ntype: spec\n---\n# SPEC песочницы\n"
STUB_BIN = "/artel-test-stub-bin"


class DocsDirSandbox(RealGitSandbox):
    """Задача артели в `in_dev`: ссылка документов несёт SPEC.md и
    зафиксирована, рабочая копия кода заведена `workspace.ensure`."""

    def setUp(self):
        super().setUp()
        self.add_synced_origin()
        self.conn = store.db()
        store.insert_task(self.conn, TASK, "Каталог документов", "in_dev",
                          BRANCH, config.DEFAULT_TARGET, 25.0)
        wt, error = workspace.ensure(TASK, BRANCH)
        self.assertIsNone(error, f"рабочая копия кода не заведена: {error}")
        self.wt = wt
        self.assertTrue(artifact_branch.commit_files(
            TASK, {f"tasks/{TASK}/SPEC.md": SPEC_TEXT}, "SPEC"))
        store.record_fixation(self.conn, TASK)
        self.docs = artifact_branch.docs_dir(TASK, config.DEFAULT_TARGET)

    def ref_text(self, rel: str):
        return artifact_branch.read_tree(TASK).get(f"tasks/{TASK}/{rel}")


class RoleCwdLaysDocsOutsideCodeCopyTest(DocsDirSandbox):

    def test_docs_go_to_docs_dir_and_stale_code_copy_dir_is_dropped(self):
        """Перед шагом документы — в каталоге документов, не в коде.

        Сценарий: в рабочей копии кода осел `tasks/<id>/acceptance_tests/`
        прошлой механики; `runner.role_cwd` возвращает рабочую копию кода,
        SPEC.md ссылки лежит в каталоге документов, а `tasks/<id>/` в
        рабочей копии кода нет.

        Ловит мутацию: `role_cwd` выкладывает документы в рабочую копию
        кода (`materialize_task_dir(task_id, path)`) — SPEC.md в каталоге
        документов нет, а в коде есть; уборка осевшего `tasks/<id>/` из
        рабочей копии кода снята — каталог остаётся."""
        stale = self.wt / "tasks" / TASK / "acceptance_tests" / "test_old.py"
        stale.parent.mkdir(parents=True)
        stale.write_text("# прошлая механика\n", encoding="utf-8")

        cwd = runner.role_cwd(self.conn, TASK, config.DEFAULT_TARGET)

        self.assertEqual(cwd, self.wt)
        self.assertEqual((self.docs / "SPEC.md").read_text(encoding="utf-8"),
                         SPEC_TEXT)
        self.assertFalse((self.wt / "tasks" / TASK).exists())


class StepAutocommitFromDocsDirTest(DocsDirSandbox):

    def test_docs_dir_edit_reaches_ref_code_copy_copy_does_not(self):
        """Правка роли в каталоге документов уходит в ссылку; копия в коде — нет.

        Сценарий: после выкладки роль пишет PLAN.md в каталог документов и
        оставляет `stray.md` в `tasks/<id>/` рабочей копии кода. После
        автокоммита шага PLAN.md в ссылке с текстом роли, `stray.md` в
        ссылке нет, `tasks/<id>/` в рабочей копии кода нет.

        Ловит мутацию: автокоммит читает рабочую копию кода, а не каталог
        документов — PLAN.md в ссылку не попадает; уборка рабочей копии
        кода на пути шага забыта — каталог остаётся."""
        runner.role_cwd(self.conn, TASK, config.DEFAULT_TARGET)
        (self.docs / "PLAN.md").write_text("план роли\n", encoding="utf-8")
        stray = self.wt / "tasks" / TASK / "stray.md"
        stray.parent.mkdir(parents=True)
        stray.write_text("не туда\n", encoding="utf-8")

        checkpoint.commit_step_artifacts(self.conn, TASK, "developer")

        self.assertEqual(self.ref_text("PLAN.md"), "план роли\n")
        self.assertIsNone(self.ref_text("stray.md"))
        self.assertFalse((self.wt / "tasks" / TASK).exists())
        self.assertIsNone(fixation.check_integrity(self.conn, TASK))

    def test_code_copy_artifact_reaches_ref_and_docs_dir_edit_wins(self):
        """Документ роли, записанный в `tasks/<id>/` кода, не теряется.

        Сценарий: роль на прежнем правиле путей HOME пишет PLAN.md в
        рабочую копию кода, а REVIEW.md — и туда, и в каталог документов
        разными текстами. После автокоммита PLAN.md в ссылке с текстом
        роли, REVIEW.md — с текстом каталога документов, `tasks/<id>/` в
        рабочей копии кода нет, журнал называет уборку.

        Ловит мутацию: `_take_code_copy_docs` только убирает каталог и
        возвращает пустой словарь — PLAN.md в ссылку не попадает;
        `_merge_code_copy_docs` берёт рабочую копию кода поверх правки
        каталога документов — в ссылке REVIEW.md из кода."""
        runner.role_cwd(self.conn, TASK, config.DEFAULT_TARGET)
        code_docs = self.wt / "tasks" / TASK
        code_docs.mkdir(parents=True)
        (code_docs / "PLAN.md").write_text("план из кода\n", encoding="utf-8")
        (code_docs / "REVIEW.md").write_text("ревью из кода\n",
                                             encoding="utf-8")
        (self.docs / "REVIEW.md").write_text("ревью каталога\n",
                                             encoding="utf-8")

        checkpoint.commit_step_artifacts(self.conn, TASK, "developer")

        self.assertEqual(self.ref_text("PLAN.md"), "план из кода\n")
        self.assertEqual(self.ref_text("REVIEW.md"), "ревью каталога\n")
        self.assertFalse(code_docs.exists())
        actions = [r["action"] for r in store.task_steps(self.conn, TASK)]
        self.assertIn(checkpoint.CODE_COPY_DOCS_DROPPED_ACTION, actions)

    def test_untouched_docs_dir_makes_no_commit(self):
        """Выкладка, не тронутая ролью, не двигает ссылку.

        Сценарий: выкладка и сразу автокоммит шага — голова ссылки та же.

        Ловит мутацию: автокоммит пишет коммит при совпадающем дереве
        (`commit_files` без сверки) — голова ссылки сдвигается пустым
        коммитом и перефиксируется."""
        runner.role_cwd(self.conn, TASK, config.DEFAULT_TARGET)
        before = artifact_branch.ref_head(TASK)

        checkpoint.commit_step_artifacts(self.conn, TASK, "developer")

        self.assertEqual(artifact_branch.ref_head(TASK), before)


class RefMovedPastPultTest(DocsDirSandbox):

    def test_ref_moved_by_role_is_neither_autocommitted_nor_refixed(self):
        """Ссылку сдвинули мимо пульта — автокоммит и перефиксация не идут.

        Сценарий: после выкладки роль пишет PLAN.md в каталог документов и
        сама двигает ссылку (запись узлом без перефиксации). Автокоммит
        шага ссылку больше не двигает, `fixed_sha` прежний, сверка
        целостности видит расхождение, журнал называет сдвиг.

        Ловит мутацию: сторож `_docs_ref_moved_past_pult` снят — автокоммит
        кладёт коммит поверх подменённой головы и перефиксирует её, сверка
        целостности следующего шага расхождения не видит."""
        runner.role_cwd(self.conn, TASK, config.DEFAULT_TARGET)
        fixed = store.get_task(self.conn, TASK)["fixed_sha"]
        (self.docs / "PLAN.md").write_text("план роли\n", encoding="utf-8")
        moved = artifact_branch.commit_files(
            TASK, {f"tasks/{TASK}/SPEC.md": "подмена\n"}, "подмена роли")

        checkpoint.commit_step_artifacts(self.conn, TASK, "developer")

        self.assertEqual(artifact_branch.ref_head(TASK), moved)
        self.assertEqual(store.get_task(self.conn, TASK)["fixed_sha"], fixed)
        self.assertIsNotNone(fixation.check_integrity(self.conn, TASK))
        actions = [r["action"] for r in store.task_steps(self.conn, TASK)]
        self.assertIn(checkpoint.DOCS_REF_MOVED_ACTION, actions)


class PlankInCodeCopyTest(DocsDirSandbox):

    def setUp(self):
        super().setUp()
        self.assertTrue(artifact_branch.commit_files(
            TASK, {f"tasks/{TASK}/acceptance_tests/test_x.py": "# планка\n"},
            "планка"))
        self.plank = self.wt / "tasks" / TASK / "acceptance_tests"

    def test_plank_is_present_inside_and_gone_after_the_block(self):
        """Внутри блока планка в рабочей копии кода, после — нет.

        Ловит мутацию: `plank_in_code_copy` не выкладывает планку (прогону
        нечего гонять) либо не убирает её на выходе — каталог остаётся."""
        with acceptance.plank_in_code_copy(
                TASK, artifact_branch.branch_name(TASK), self.wt) as tdir:
            self.assertEqual(tdir, self.wt / "tasks" / TASK)
            self.assertTrue((self.plank / "test_x.py").is_file())
        self.assertFalse((self.wt / "tasks" / TASK).exists())

    def test_plank_is_gone_after_an_exception_inside_the_block(self):
        """Исключение внутри прогона — планка всё равно убрана.

        Ловит мутацию: уборка — строка после `yield`, а не `finally`:
        исключение её минует, и планка остаётся в рабочей копии кода."""
        with self.assertRaises(RuntimeError):
            with acceptance.plank_in_code_copy(
                    TASK, artifact_branch.branch_name(TASK), self.wt):
                raise RuntimeError("сбой прогона")
        self.assertFalse((self.wt / "tasks" / TASK).exists())

    def test_drop_never_touches_the_pult_main_copy(self):
        """Уборка не трогает `tasks/<id>/` главной копии пульта.

        Ловит мутацию: `drop_from_code_copy` без отсечки `config.ROOT` —
        легаси-каталог задачи в главной копии удаляется."""
        legacy = config.ROOT / "tasks" / TASK / "SPEC.md"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("легаси\n", encoding="utf-8")

        acceptance.drop_from_code_copy(TASK, config.ROOT)

        self.assertTrue(legacy.is_file())


class CommandWithoutDocsDirTest(unittest.TestCase):

    def setUp(self):
        patcher = mock.patch.object(runner, "declared_tool_path",
                                    lambda name: f"{STUB_BIN}/{name}")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_add_dir_only_when_docs_dir_given_and_model_stays_last(self):
        """`--add-dir` — только с каталогом документов; модель — последней.

        Сценарий: у обоих провайдеров `command(model)` без каталога
        документов не несёт `--add-dir` (офлайн-смок изоляции и
        `role_cmd()` сверяют прежнюю команду); с каталогом — пара
        `--add-dir <каталог>` есть, а хвост argv (модель у claude, модель и
        промпт со стандартного входа у codex) тот же, что без неё.

        Ловит мутацию: флаг добавляется всегда (с `None` или пустым
        значением) — команда без каталога несёт `--add-dir`; флаг встал
        после `--model`/`-m` — хвост argv меняется."""
        docs = "/docs/tasks/X"
        for name in ("claude", "codex"):
            with self.subTest(provider=name):
                provider = providers.get(name)
                bare = provider.command("model-x")
                opened = provider.command("model-x", docs_dir=docs)
                self.assertNotIn("--add-dir", bare)
                at = opened.index("--add-dir")
                self.assertEqual(opened[at + 1], docs)
                self.assertEqual(opened[:at] + opened[at + 2:], bare)
                tail = 2 if name == "claude" else 3
                self.assertEqual(opened[-tail:], bare[-tail:])


class MissionNamesDocsDirTest(unittest.TestCase):

    def test_every_role_mission_names_the_docs_dir(self):
        """Миссия каждой роли называет каталог документов буквальной строкой.

        Ловит мутацию: `mission_brief_package` не дописывает абзац о
        каталоге документов (или дописывает его не всем ролям) — роль не
        знает, куда писать документы, и пишет их в рабочую копию кода."""
        docs = "/docs-root/tasks/" + TASK
        t = {"branch": BRANCH, "reviewed_iter": 0, "title": "x"}
        with mock.patch("orchestrator.brief.analyst_map_component",
                        return_value=""), \
                mock.patch("orchestrator.brief.test_author_answer_component",
                           return_value=""), \
                mock.patch("orchestrator.brief.developer_brief",
                           return_value=""), \
                mock.patch("orchestrator.review.review_package",
                           return_value={"text": ""}):
            for role in ("analyst", "test_author", "developer", "reviewer"):
                with self.subTest(role=role):
                    mission, _b, _p = role_prompt.mission_brief_package(
                        None, TASK, t, role, "/code-copy", docs_dir=docs)
                    self.assertIn(f"Каталог документов задачи — {docs}",
                                  mission)


if __name__ == "__main__":
    unittest.main()
