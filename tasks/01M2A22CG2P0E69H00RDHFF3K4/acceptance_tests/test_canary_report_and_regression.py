"""Приёмочные тесты SPEC 01M2A22CG2P0E69H00RDHFF3K4 (продолжение
`test_spec_gate_artifact_source.py`): строка отчёта прогона канарейки
(AC-5) и тест-регресс на AC-1 внутри `tests/test_canary.py` (AC-6).

Красен до реализации: `canary._run_one_task` (orchestrator/canary.py:
938-1046) на момент написания тестов не несёт признака «test_author=
да/нет» в итоговой строке отчёта — `test_ac5_...` не находит ни один
из двух тегов в захваченном выводе. `tests/test_canary.py` пока не
содержит теста на `_spec_gate_next_state` вовсе — мутация на AC-1
(возврат к `gitcmd.on_foreign_branch`) не добавляет НИ ОДНОГО нового
падения к базовому прогону, `test_ac6_...` падает на пустом
`new_failures`.
"""
import importlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from orchestrator import canary, config, store  # noqa: E402
from tests.sandbox import capture  # noqa: E402


class RunOneTaskReportsTestAuthorPassageTest(unittest.TestCase):
    """`canary._run_one_task` — признак прохождения `tests_writing` в
    строке отчёта (SPEC, требование 3, AC-5)."""

    def setUp(self):
        real_root = config.ROOT
        suffixes = {attr: getattr(config, attr).relative_to(real_root)
                   for attr in canary._CLONE_CONFIG_ATTRS}
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        outer_root = Path(tmp.name) / "outer"
        outer_root.mkdir()
        for attr in canary._CLONE_CONFIG_ATTRS:
            patcher = mock.patch.object(config, attr, outer_root / suffixes[attr])
            patcher.start()
            self.addCleanup(patcher.stop)
        store.create_schema(store.db())

        self.template_path = Path(tmp.name) / "ac5-template.md"
        self.template_path.write_text(
            "# Канареечный шаблон AC-5\n\nОписание без маркера эскалации.\n",
            encoding="utf-8")

        fake_clone_dir = Path(tmp.name) / "clone-ac5"

        def fake_run(cmd, **kw):
            if cmd[:2] == ["git", "clone"]:
                Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        for target, attr, value in (
            (canary.tempfile, "mkdtemp", str(fake_clone_dir)),
        ):
            patcher = mock.patch.object(target, attr, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(canary.subprocess, "run", side_effect=fake_run)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(canary.catalog, "cmd_init", lambda: None)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(canary.catalog, "cmd_new", return_value="T-AC5")
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(
            canary.store, "get_task",
            return_value={"branch": "task/t-ac5-x", "state": "killed",
                         "spent_usd": 2.5, "review_iters": 1})
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(canary.workspace, "ensure",
                                    return_value=(Path("/fake-wt"), None))
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(canary, "_drive_task", lambda conn, tid: None)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(canary.gitcmd, "head_sha",
                                    return_value="deadbeefcafe")
        patcher.start()
        self.addCleanup(patcher.stop)

    def _steps_with(self, include_tests_writing):
        steps = []
        if include_tests_writing:
            steps.append({"ts": "2026-09-12 00:00:00.000000Z",
                         "actor": "test_author",
                         "action": "state -> tests_writing", "detail": ""})
        steps.append({"ts": "2026-09-12 00:00:01.000000Z",
                     "actor": canary.CANARY_MARK_ACTOR,
                     "action": canary._MERGE_GATE_KILL_ACTION, "detail": ""})
        return steps

    def test_ac5_report_line_marks_test_author_passage_from_journal(self):
        """Итоговая строка отчёта прогона несёт «test_author=да», если в
        журнале задачи есть переход «state -> tests_writing», и
        «test_author=нет» в противном случае — по фактическому журналу
        задачи (не по сегодняшнему состоянию задачи).

        Ловит мутацию: признак вычисляется по любому другому условию,
        либо перепутаны ветки «да»/«нет» местами — хотя бы один из двух
        сценариев ниже (журнал с переходом и без него) дал бы
        противоположный, ошибочный тег.
        """
        for include, expected_tag, other_tag in (
            (True, "test_author=да", "test_author=нет"),
            (False, "test_author=нет", "test_author=да"),
        ):
            with self.subTest(include_tests_writing=include):
                with mock.patch.object(canary.store, "task_steps",
                                      return_value=self._steps_with(include)):
                    output = capture(canary._run_one_task, self.template_path,
                                    "20260912T000000Z", 1.5)
                self.assertIn(expected_tag, output)
                self.assertNotIn(other_tag, output)


class SpecGateNextStateRegressionInSuiteTest(unittest.TestCase):
    """`tests/test_canary.py` — тест-регресс на AC-1 (SPEC, AC-6):
    проверяем не наличие метода с каким-то именем (тавтология, ловится
    любым названием), а заявленное в самом AC-6 свойство — что мутация
    «чтение SPEC вернули на `gitcmd.on_foreign_branch`» валит хотя бы
    один тест внутри `tests/test_canary.py`."""

    @staticmethod
    def _old_buggy_spec_gate_next_state(conn, task_id, t):
        # Буквальная копия `_spec_gate_next_state` ДО этой задачи (см.
        # `orchestrator/canary.py:513-523` на момент написания SPEC) —
        # ровно мутация, названная в AC-6: источник — кодовая ветка
        # задачи через `gitcmd.on_foreign_branch`, не артефактная ветка
        # через `artifact_source.resolve`.
        branch = t["branch"]
        if canary.gitcmd.on_foreign_branch(branch):
            spec_text, _reason = canary.gitcmd.show(
                branch, f"tasks/{task_id}/SPEC.md")
            meta = ((canary.yamlmini.frontmatter(spec_text) or {})
                    if spec_text is not None else {})
        else:
            meta = canary.artifacts.frontmatter(
                canary.config.TASKS / task_id / "SPEC.md")
        return "tests_writing" if canary.guard.requires_ac_markup(meta) else "in_dev"

    @staticmethod
    def _run_suite():
        import tests.test_canary as test_canary_module
        importlib.reload(test_canary_module)
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(test_canary_module)
        result = unittest.TestResult()
        suite.run(result)
        return {str(case) for case, _tb in (result.failures + result.errors)}

    def test_ac6_reverting_to_on_foreign_branch_turns_a_test_red(self):
        """Прогоняем весь `tests/test_canary.py` дважды: без мутации
        (базовый набор упавших) и с production-функцией `canary.
        _spec_gate_next_state`, подменённой на буквальную копию версии
        ДО этой задачи (мутация из AC-6). Разница множеств упавших
        тестов обязана быть непустой — файл несёт тест, чувствительный
        именно к этой мутации.

        Ловит мутацию (самого AC-6, зеркально): `tests/test_canary.py`
        не содержит теста, вызывающего реальный
        `canary._spec_gate_next_state` — тогда обе прогонки дают
        одинаковый (обычно пустой) набор падений, и `new_failures`
        оказывается пустым множеством.
        """
        baseline_failed = self._run_suite()
        with mock.patch.object(canary, "_spec_gate_next_state",
                              side_effect=self._old_buggy_spec_gate_next_state):
            mutated_failed = self._run_suite()

        new_failures = mutated_failed - baseline_failed
        self.assertTrue(
            new_failures,
            "мутация AC-6 (возврат к gitcmd.on_foreign_branch) не завалила "
            "ни одного теста в tests/test_canary.py — регресса на AC-1 там "
            "нет")
