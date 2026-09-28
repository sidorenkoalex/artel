"""Юнит-тесты защиты настроек сбора тестов и общего помощника сверки пути
с перечнем защищённых путей `config.is_protected_path`
(tasks/01M3MVXZXF25KYY2P213E0M39X/SPEC.md).

Долгоживущие свойства задачи сторожатся здесь, а не только планкой задачи
(ADR-0018, п. 3): состав реального `config.PROTECTED_PATHS`, новые записи
условия полного прогона на мерже, опознание маски `**/conftest.py` и
корневых литералов каждым из шести мест сверки на РЕАЛЬНОМ перечне.
Плюс грани помощника: явный перечень вместо `config.PROTECTED_PATHS`,
чтение перечня в момент вызова, маска на пути с каталогом-тёзкой,
направление расхождения `guard.protected_zones` с прежним
`zone_lock._covered_by`, запуск `scripts/ci_protected_paths.py` как
скрипта (импорт `orchestrator.config` из каталога `scripts/`).
"""
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, fsm_merge_gate, github_adapter  # noqa: E402
from orchestrator.advance_gates import zones  # noqa: E402
from scripts import ci_protected_paths, guard  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

LEGACY_PROTECTED_PATHS = (
    "gates.yaml", "roles.yaml", ".github/", "templates/", "skills/",
    "docs/invariants.md", "tests/test_invariants.py", "docs/adr/",
    "CLAUDE.md", "AGENTS.md", "targets.yaml", "models.yaml")
TEST_SETTINGS_ENTRIES = ("**/conftest.py", "pyproject.toml", "pytest.ini",
                         "setup.cfg", "tox.ini")
# Пути, которые каждое место сверки обязано признать защищёнными на
# реальном перечне: маска в корне и во вложенном каталоге, корневые
# литералы; и заведомо незащищённые соседи.
TEST_SETTINGS_PATHS = ("conftest.py", "tests/conftest.py",
                       "tests/sub/conftest.py", "pyproject.toml",
                       "pytest.ini", "setup.cfg", "tox.ini")
UNPROTECTED_PATHS = ("tests/test_store.py", "orchestrator/store.py",
                     "tests/test_conftest_role_guard.py",
                     "docs/pyproject.md", "tests/pytest.ini")


class RealProtectedPathsCompositionTest(unittest.TestCase):

    def test_real_list_keeps_legacy_entries_and_adds_test_settings(self):
        """Реальный `config.PROTECTED_PATHS` — прежние 12 записей на
        прежних местах плюс пять записей настроек сбора тестов.

        Ловит мутацию: из перечня удалена `**/conftest.py` (или любой из
        литералов `pyproject.toml`/`pytest.ini`/`setup.cfg`/`tox.ini`),
        либо прежняя запись переставлена/удалена — защита настроек сбора
        тестов снимается без единого красного гейта."""
        self.assertEqual(tuple(config.PROTECTED_PATHS[:12]),
                         LEGACY_PROTECTED_PATHS)
        for entry in TEST_SETTINGS_ENTRIES:
            with self.subTest(entry=entry):
                self.assertIn(entry, config.PROTECTED_PATHS)
        self.assertEqual(len(config.PROTECTED_PATHS), 17)

    def test_real_config_source_carries_the_entries_for_ci_job(self):
        """Текст `orchestrator/config.py`, разобранный джобом CI, несёт те
        же пять записей — джоб читает перечень из исходника, не из памяти.

        Ловит мутацию: запись-маска вынесена из литерала кортежа
        (конкатенация, вычисление) — `protected_paths_from_source` вернёт
        None, и джоб на следующей базе не сверит ни одного пути."""
        source = (REPO_ROOT / "orchestrator" / "config.py").read_text(
            encoding="utf-8")
        paths, reason = ci_protected_paths.protected_paths_from_source(source)
        self.assertEqual(reason, "")
        for entry in TEST_SETTINGS_ENTRIES:
            with self.subTest(entry=entry):
                self.assertIn(entry, paths)


class SixCheckPointsOnRealListTest(unittest.TestCase):
    """Каждое из шести мест сверки требования 5 SPEC — на реальном
    перечне, без подмены."""

    def _assert_verdicts(self, is_protected):
        for path in TEST_SETTINGS_PATHS:
            with self.subTest(path=path):
                self.assertTrue(is_protected(path))
        for path in UNPROTECTED_PATHS:
            with self.subTest(path=path):
                self.assertFalse(is_protected(path))

    def test_merge_gate_diff_check(self):
        """Ловит мутацию: `fsm_merge_gate._touches_protected_path`
        возвращена к собственной префиксной формуле — `tests/sub/conftest.py`
        уезжает в main мимо гейта диффа на мерже."""
        self._assert_verdicts(fsm_merge_gate._touches_protected_path)

    def test_zones_gate_check(self):
        """Ловит мутацию: `zones._protected_paths_touched` возвращена к
        `_touches_zone` над перечнем — маска не опознаётся, и переход
        `in_dev → review` с правкой `tests/sub/conftest.py` проходит."""
        self._assert_verdicts(
            lambda p: zones._protected_paths_touched([p]) == [p])

    def test_ci_job_check_on_real_config_source(self):
        """Ловит мутацию: `ci_protected_paths.is_violation` возвращена к
        `path.startswith(prefix)` — джоб CI не считает нарушением
        `tests/sub/conftest.py` при перечне базы с маской."""
        source = (REPO_ROOT / "orchestrator" / "config.py").read_text(
            encoding="utf-8")
        protected, _ = ci_protected_paths.protected_paths_from_source(source)
        self._assert_verdicts(
            lambda p: ci_protected_paths.is_violation(p, protected))

    def test_plan_appendix_check(self):
        """Ловит мутацию: `guard._appendix_path_is_protected` возвращена к
        префиксной формуле — приложение PLAN к `tests/sub/conftest.py`
        отвергается как незащищённое, и правку приходится вести мимо
        приложения."""
        self._assert_verdicts(guard._appendix_path_is_protected)

    def test_spec_protected_zones_check(self):
        """Ловит мутацию: `guard.protected_zones` возвращена к
        `zone_lock._covered_by` — зона SPEC `tests/sub/conftest.py` не
        помечается защищённой."""
        self._assert_verdicts(
            lambda p: guard.protected_zones([p]) == [p])

    def test_draft_mr_highlight_check(self):
        """Ловит мутацию: `github_adapter._touched_protected_paths`
        возвращена к префиксной формуле — Draft MR не подсвечивает правку
        `tests/sub/conftest.py`."""
        def touched(path):
            res = SimpleNamespace(returncode=0, stdout=path + "\n")
            with mock.patch.object(github_adapter.gitcmd, "git",
                                   return_value=res):
                return github_adapter._touched_protected_paths(
                    "task/x", "main") == [path]
        self._assert_verdicts(touched)


class FullSuiteTestSettingsTest(unittest.TestCase):

    def test_appendix_to_test_settings_needs_full_suite(self):
        """Приложение к каждой настройке сбора тестов требует полного
        прогона `tests/` в цикле мержа (требование 10 SPEC).

        Ловит мутацию: из `_FULL_SUITE_APPENDIX_PREFIXES` удалена
        `**/conftest.py` или любой из корневых литералов — приложение к
        `pyproject.toml` уезжает в main без полного набора."""
        for path in TEST_SETTINGS_PATHS:
            with self.subTest(path=path):
                self.assertTrue(
                    fsm_merge_gate._appendix_needs_full_suite([path]))
        self.assertFalse(fsm_merge_gate._appendix_needs_full_suite(
            ["skills/spec-authoring.md"]))


class MaskEntryTest(unittest.TestCase):

    def test_mask_matches_by_last_component_only(self):
        """Маска `**/<имя>` сверяется с последним компонентом пути, а не
        с подстрокой и не с каталогом.

        Ловит мутацию: маска проверяется `path.endswith(имя)` — тогда
        `tests/myconftest.py` становится защищённым, а проверка по
        вхождению (`имя in path`) защитила бы и каталог
        `conftest.py/x.py`."""
        protected = ("**/conftest.py",)

        self.assertTrue(config.is_protected_path("a/b/conftest.py",
                                                 protected))
        self.assertFalse(config.is_protected_path("tests/myconftest.py",
                                                  protected))
        self.assertFalse(config.is_protected_path("conftest.py/x.py",
                                                  protected))

    def test_mask_is_not_a_literal_prefix(self):
        """Путь, буквально начинающийся с текста маски, маской не покрыт
        как префиксом — маска не превращается в префикс `**/`.

        Ловит мутацию: ветка маски потеряна, запись `**/conftest.py`
        сверяется общей префиксной формулой — тогда `conftest.py` вне
        корня не защищён вовсе, а защищён лишь несуществующий путь
        `**/conftest.py/…`."""
        protected = ("**/conftest.py",)

        self.assertTrue(config.is_protected_path("tests/conftest.py",
                                                 protected))
        self.assertTrue(config.is_protected_path("**/conftest.py",
                                                 protected))
        self.assertFalse(config.is_protected_path("**/conftest.py.bak",
                                                  protected))


class ExplicitListAndCallTimeTest(unittest.TestCase):

    def test_explicit_list_replaces_the_config_list(self):
        """Явный перечень используется ВМЕСТО `config.PROTECTED_PATHS` —
        так джоб CI сверяет пути с перечнем базы сравнения.

        Ловит мутацию: явный перечень склеивается с
        `config.PROTECTED_PATHS` (или игнорируется) — `gates.yaml`
        оказался бы нарушением при перечне базы без него, и ветка,
        добавляющая защищённый путь, покрасила бы собственный PR."""
        self.assertFalse(config.is_protected_path("gates.yaml",
                                                  ["skills/"]))
        self.assertTrue(config.is_protected_path("skills/x.md",
                                                 ["skills/"]))

    def test_config_list_is_read_at_call_time(self):
        """Без явного перечня помощник читает `config.PROTECTED_PATHS` в
        момент вызова.

        Ловит мутацию: перечень снят значением по умолчанию параметра
        (`protected=PROTECTED_PATHS`) при определении функции — подмена
        перечня перестаёт действовать, и следующая запись не заработала
        бы без правки помощника."""
        with mock.patch.object(config, "PROTECTED_PATHS", ("only.txt",)):
            self.assertTrue(config.is_protected_path("only.txt"))
            self.assertFalse(config.is_protected_path("gates.yaml"))


class ProtectedZonesDirectionTest(unittest.TestCase):

    def test_file_entry_with_suffix_is_now_protected(self):
        """`guard.protected_zones` на общей формуле считает защищённым
        «запись-файл плюс суффикс» — единственное расхождение с прежним
        `zone_lock._covered_by`, и оно в сторону усиления (требование 6).

        Ловит мутацию: `protected_zones` остался на `zone_lock._covered_by`
        — `CLAUDE.md.bak` не помечается, и вердикт пометки зон расходится
        с гейтом зон, который тот же путь отказывает."""
        self.assertEqual(guard.protected_zones(["CLAUDE.md.bak"]),
                         ["CLAUDE.md.bak"])


class FullSuiteLegacyPrefixesTest(unittest.TestCase):

    def test_legacy_prefixes_keep_prefix_semantics(self):
        """Прежние записи условия полного прогона (`tests/`, `.github/`)
        после перехода на общий помощник сверяются префиксом, как раньше.

        Ловит мутацию: условие полного прогона переведено на точное
        равенство или только на маски — приложение к
        `tests/test_invariants.py` уехало бы в main без полного набора."""
        self.assertTrue(fsm_merge_gate._appendix_needs_full_suite(
            ["docs/x.md", "tests/sub/test_x.py"]))
        self.assertTrue(fsm_merge_gate._appendix_needs_full_suite(
            [".github/workflows/ci.yml"]))
        self.assertFalse(fsm_merge_gate._appendix_needs_full_suite(
            ["docs/pyproject.md", "tests.md"]))


class CiScriptRunsAsScriptTest(unittest.TestCase):

    def test_script_imports_config_when_started_from_scripts_dir(self):
        """`python3 scripts/ci_protected_paths.py` (контракт вызова джоба)
        доходит до разбора `BASE_SHA`, а не падает на импорте
        `orchestrator.config`.

        Ловит мутацию: вставка корня репозитория в `sys.path` убрана —
        у скрипта в `sys.path` лежит `scripts/`, импорт падает
        `ModuleNotFoundError`, и джоб CI красный на каждом PR с причиной,
        не имеющей отношения к защищённым путям."""
        res = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" /
                                 "ci_protected_paths.py")],
            capture_output=True, text=True, timeout=60, cwd=REPO_ROOT,
            env={"PATH": "/usr/bin:/bin", "BASE_SHA": ""})

        self.assertEqual(res.returncode, 2, res.stderr)
        self.assertNotIn("ModuleNotFoundError", res.stderr)
        self.assertIn("BASE_SHA", res.stdout)


if __name__ == "__main__":
    unittest.main()
