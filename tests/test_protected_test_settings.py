"""Юнит-тесты общего помощника сверки пути с перечнем защищённых путей
`config.is_protected_path` (tasks/01M3MVXZXF25KYY2P213E0M39X/SPEC.md) —
грани, которые приёмочная планка задачи намеренно не проверяет: явный
перечень вместо `config.PROTECTED_PATHS`, чтение перечня в момент вызова,
маска на пути с каталогом-тёзкой, направление расхождения
`guard.protected_zones` с прежним `zone_lock._covered_by`, запуск
`scripts/ci_protected_paths.py` как скрипта (импорт `orchestrator.config`
из каталога `scripts/`).
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, fsm_merge_gate  # noqa: E402
from scripts import guard  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


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
