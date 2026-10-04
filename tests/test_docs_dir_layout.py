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

from orchestrator import (acceptance, agent_log, amend, artifact_branch,
                          checkpoint, config, fixation, fsm, fsm_advance,
                          fsm_autogate, providers, role_prompt, runner, store,
                          workspace)
from orchestrator.advance_gates import acceptance as acceptance_gate
from orchestrator.advance_gates._base import GateRefusal
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

    def test_code_copy_doc_left_before_step_reaches_ref_and_docs_dir(self):
        """Документ, оставленный в `tasks/<id>/` кода до шага, не теряется.

        Сценарий: до старта шага в рабочей копии кода лежит PLAN.md
        (прерванный шаг на прежнем правиле путей, песочница теста).
        `runner.role_cwd` забирает его в ссылку новым коммитом поверх
        прежней головы, выкладывает в каталог документов и убирает
        `tasks/<id>/` из рабочей копии кода.

        Ловит мутацию: `role_cwd` не зовёт `checkpoint.
        harvest_code_copy_docs` и сразу убирает каталог — PLAN.md нет ни в
        ссылке, ни в каталоге документов."""
        before = artifact_branch.ref_head(TASK)
        left = self.wt / "tasks" / TASK / "PLAN.md"
        left.parent.mkdir(parents=True)
        left.write_text("план до шага\n", encoding="utf-8")

        runner.role_cwd(self.conn, TASK, config.DEFAULT_TARGET)

        self.assertEqual(self.ref_text("PLAN.md"), "план до шага\n")
        self.assertNotEqual(artifact_branch.ref_head(TASK), before)
        self.assertEqual((self.docs / "PLAN.md").read_text(encoding="utf-8"),
                         "план до шага\n")
        self.assertFalse((self.wt / "tasks" / TASK).exists())
        self.assertIsNone(fixation.check_integrity(self.conn, TASK))

    def test_code_copy_doc_lands_in_docs_dir_when_layout_fails(self):
        """Выкладка из ссылки не состоялась — забранный документ всё равно в
        каталоге документов.

        Сценарий: `materialize_task_dir` отвечает пустой строкой (git не
        ответил); PLAN.md из `tasks/<id>/` кода оказывается в каталоге
        документов, в рабочей копии кода его нет.

        Ловит мутацию: `role_cwd` не кладёт забранные файлы в каталог
        документов при несостоявшейся выкладке — PLAN.md пропадает до
        запуска роли."""
        left = self.wt / "tasks" / TASK / "PLAN.md"
        left.parent.mkdir(parents=True)
        left.write_text("план до шага\n", encoding="utf-8")

        with mock.patch.object(artifact_branch, "materialize_task_dir",
                               return_value=""):
            runner.role_cwd(self.conn, TASK, config.DEFAULT_TARGET)

        self.assertEqual((self.docs / "PLAN.md").read_text(encoding="utf-8"),
                         "план до шага\n")
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

    def test_plank_deleted_in_docs_dir_is_not_revived_from_code_copy(self):
        """Удаление файла планки в каталоге документов не отменяет её копия в коде.

        Сценарий: задача в `tests_writing`, в ссылке планка
        `acceptance_tests/test_x.py` прошлого шага test_author (лока ещё
        нет — удаление планки им же доезжает до ссылки); test_author копирует планку в рабочую копию кода для прогона
        (так велит миссия), затем в каталоге документов переименовывает
        `test_x.py` в `test_y.py`. После автокоммита шага в ссылке
        `test_y.py` есть, `test_x.py` нет, `tasks/<id>/` в рабочей копии
        кода нет.

        Ловит мутацию: `_merge_code_copy_docs` берёт из рабочей копии кода
        и пути ссылки, удалённые ролью в каталоге документов (снято условие
        `rel in known`), — `test_x.py` воскресает в ссылке (REVIEW
        итерации 1, R1-F2)."""
        self.assertTrue(artifact_branch.commit_files(
            TASK, {f"tasks/{TASK}/acceptance_tests/test_x.py": "# планка\n"},
            f"{TASK}: артефакты шага test_author (автокоммит оркестратора)"))
        store.record_fixation(self.conn, TASK)
        store.update_task(self.conn, TASK, state="tests_writing")
        runner.role_cwd(self.conn, TASK, config.DEFAULT_TARGET)
        copy = self.wt / "tasks" / TASK / "acceptance_tests" / "test_x.py"
        copy.parent.mkdir(parents=True)
        copy.write_text("# планка\n", encoding="utf-8")
        plank = self.docs / "acceptance_tests"
        (plank / "test_x.py").rename(plank / "test_y.py")

        checkpoint.commit_step_artifacts(self.conn, TASK, "test_author")

        self.assertEqual(self.ref_text("acceptance_tests/test_y.py"),
                         "# планка\n")
        self.assertIsNone(self.ref_text("acceptance_tests/test_x.py"))
        self.assertFalse((self.wt / "tasks" / TASK).exists())

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


class _Stop(Exception):
    """Обрывает обработчик перехода после гейтов: дальше — лок и смена
    состояния, к уборке планки не относящиеся."""


class GatesDropPlankAfterRunTest(DocsDirSandbox):
    """Гейты, гоняющие планку, убирают её из рабочей копии кода после
    прогона при любом исходе (SPEC требования 3, 7; AC-7..9; REVIEW
    итерации 1, R1-F1): сторож места вызова, не только
    `plank_in_code_copy`. Прогон подменён наблюдателем — он отмечает, что
    планка во время прогона лежит в рабочей копии кода, и отдаёт исход."""

    def setUp(self):
        super().setUp()
        self.assertTrue(artifact_branch.commit_files(
            TASK, {f"tasks/{TASK}/acceptance_tests/test_x.py": "# планка\n"},
            "планка"))
        self.t = store.get_task(self.conn, TASK)
        self.branch = artifact_branch.branch_name(TASK)
        self.seen = []

    def observer(self, code_dir, outcome):
        def run(*_args, **_kwargs):
            self.seen.append((code_dir / "tasks" / TASK / "acceptance_tests"
                              / "test_x.py").is_file())
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        return run

    def assert_ran_and_dropped(self, code_dir):
        self.assertEqual(self.seen, [True])
        self.assertFalse((code_dir / "tasks" / TASK).exists())

    def run_acceptance_gate(self, outcome):
        with mock.patch.object(acceptance_gate, "long_lived_manifest",
                               return_value=({}, "")), \
                mock.patch.object(acceptance, "run",
                                  side_effect=self.observer(self.wt, outcome)), \
                mock.patch.object(acceptance, "summary",
                                  return_value="карточка"), \
                mock.patch.object(agent_log, "environment_fingerprint",
                                  return_value="окружение"):
            return acceptance_gate._acceptance_run_refuses(
                self.conn, TASK, self.t, self.docs, config.DEFAULT_TARGET,
                self.branch)

    def test_acceptance_run_drops_plank_on_green(self):
        """Зелёный прогон приёмки — планки в рабочей копии кода после нет.

        Ловит мутацию: `_acceptance_run_body` выкладывает планку
        `acceptance.materialize_from_branch` вместо `plank_in_code_copy`
        (или без `ExitStack`) — планка остаётся в рабочей копии кода."""
        self.assertFalse(self.run_acceptance_gate((True, "")))
        self.assert_ran_and_dropped(self.wt)

    def test_acceptance_run_drops_plank_on_red(self):
        """Красный прогон приёмки — переход отклонён, планки в коде нет.

        Ловит мутацию: выкладка планки в `_acceptance_run_body` без
        уборки — на красном исходе (ранний `return True`) планка остаётся
        в рабочей копии кода."""
        self.assertTrue(self.run_acceptance_gate((False, "1 failed")))
        self.assert_ran_and_dropped(self.wt)

    def test_acceptance_run_drops_plank_on_exception(self):
        """Сбой внутри прогона приёмки — планки в коде всё равно нет.

        Ловит мутацию: уборка планки в `_acceptance_run_refuses` — строкой
        после прогона, а не выходом из `ExitStack`: исключение её минует."""
        with self.assertRaises(RuntimeError):
            self.run_acceptance_gate(RuntimeError("сбой прогона"))
        self.assert_ran_and_dropped(self.wt)

    def run_tests_writing(self, outcome):
        with mock.patch.object(fsm, "_tests_writing_ac_state",
                               return_value=({1}, {}, [])), \
                mock.patch.object(fsm_advance, "_tests_writing_code_diff",
                                  return_value=(None, None, None)), \
                mock.patch.object(fsm_advance,
                                  "_tests_writing_stray_plank_files_gate",
                                  return_value=None), \
                mock.patch.object(fsm_advance, "_tests_writing_test_groups_gate",
                                  return_value=None), \
                mock.patch.object(fsm_advance, "_tests_writing_dry_collect_gate",
                                  side_effect=self.observer(self.wt, outcome)), \
                mock.patch.object(store, "set_state", side_effect=_Stop):
            return fsm_advance.tests_writing(self.conn, TASK, self.t,
                                             self.docs, config.DEFAULT_TARGET,
                                             "tests_writing")

    def test_tests_writing_drops_plank_after_dry_collect_on_every_outcome(self):
        """Выход `tests_writing`: планка в коде только на время сухого сбора.

        Сценарий: сухой сбор пройден (дальше — смена состояния, здесь
        оборвана), отклонён и упал исключением — во всех трёх случаях
        планка во время сбора в рабочей копии кода, после — нет.

        Ловит мутацию: `drop_from_code_copy` в `tests_writing` вынесен из
        `finally` за гейты (или снят) — на отказе либо исключении сухого
        сбора планка остаётся в рабочей копии кода."""
        refusal = GateRefusal("переход отклонён: сухой сбор", "красный", "")
        for name, outcome, raised in (
                ("пройден", None, _Stop),
                ("отклонён", refusal, None),
                ("исключение", RuntimeError("сбой сбора"), RuntimeError)):
            with self.subTest(outcome=name):
                self.seen = []
                if raised is None:
                    self.assertFalse(self.run_tests_writing(outcome))
                else:
                    with self.assertRaises(raised):
                        self.run_tests_writing(outcome)
                self.assert_ran_and_dropped(self.wt)

    def test_review_autogate_of_external_target_drops_plank(self):
        """Автогейт после ревью внешнего target — планки в его рабочей копии
        задачи нет.

        Сценарий: `_review_approved` внешнего target выкладывает планку в
        рабочую копию задачи target'а на время автогейта; автогейт проходит штатно и
        падает исключением — после обоих планки там нет.

        Ловит мутацию: `_review_approved` выкладывает планку
        `materialize_from_branch` без `plank_in_code_copy` — планка
        остаётся в рабочей копии кода внешнего target."""
        # Рабочая копия задачи в области проекта (ADR-0021 п.1, этап 2),
        # не общий `workspace/`.
        code_dir = config.PROJECTS / "ext-proj" / "worktrees" / TASK
        for name, outcome in (("штатно", None),
                              ("исключение", RuntimeError("сбой автогейта"))):
            with self.subTest(outcome=name):
                self.seen = []
                with mock.patch.object(store, "set_state"), \
                        mock.patch.object(
                            fsm_autogate, "_maybe_autogate_acceptance",
                            side_effect=self.observer(code_dir, outcome)):
                    if outcome is None:
                        fsm_advance._review_approved(
                            self.conn, TASK, self.t, self.docs, "ext-proj",
                            "review", self.branch, "", {})
                    else:
                        with self.assertRaises(RuntimeError):
                            fsm_advance._review_approved(
                                self.conn, TASK, self.t, self.docs,
                                "ext-proj", "review", self.branch, "", {})
                self.assert_ran_and_dropped(code_dir)

    def test_amend_from_branch_run_drops_plank(self):
        """`amend-tests --from-branch`: прогон с головы ветки убирает планку.

        Сценарий: сухой сбор и прогон долгоживущих файлов
        (`_collect_and_run`) проходят штатно и падают исключением — после
        обоих планки в рабочей копии кода нет.

        Ловит мутацию: `_check_code_head_long_lived` выкладывает планку
        `materialize_from_branch` без `plank_in_code_copy` — планка
        остаётся в рабочей копии кода."""
        for name, outcome in (("штатно", None),
                              ("исключение", RuntimeError("сбой прогона"))):
            with self.subTest(outcome=name):
                self.seen = []
                with mock.patch.object(amend, "_long_lived_errors",
                                       return_value=[]), \
                        mock.patch.object(amend, "_worktree_changed_paths",
                                          return_value=[]), \
                        mock.patch.object(
                            amend, "_collect_and_run",
                            side_effect=self.observer(self.wt, outcome)):
                    call = lambda: amend._check_code_head_long_lived(  # noqa: E731
                        self.conn, self.t, TASK, self.branch, "head", {}, {},
                        [])
                    if outcome is None:
                        call()
                    else:
                        with self.assertRaises(RuntimeError):
                            call()
                self.assert_ran_and_dropped(self.wt)


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
