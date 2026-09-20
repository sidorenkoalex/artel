"""Приёмочные тесты AC-1, AC-2, AC-3 (tasks/01M2XJKV84SQ9VEVR0VNVKDNGJ/
SPEC.md): argv[0] шага роли — абсолютный путь из резолва манифеста,
прочий состав запуска (флаги `role_cmd()` и PATH роли) не меняется,
одноимённый бинарник в каталоге другого объявленного инструмента шаг не
подменяет.

Красен до реализации: `role_cmd()` начинается литералом `claude`
(`orchestrator/runner.py:778`) — argv[0] шага не абсолютный путь, оба
теста AC-1/AC-3 падают сравнением с `resolved["claude"]`. Два теста
AC-2 — сохранение существующего поведения (состав флагов и PATH роли),
они зелёные с рождения и обязаны остаться зелёными: их предмет — то,
что правка argv[0] НЕ должна задеть.
"""
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (INCIDENT_MODEL, StepRunSandbox,  # noqa: E402
                      expected_flags, expected_role_path_dirs,
                      write_executable)
from orchestrator import runner  # noqa: E402


class StepCommandTest(StepRunSandbox):
    """Один шаг роли: модель — из таблицы инцидента, версия CLI заведомо
    выше любой минимальной, чтобы предполётная проверка модели не
    вмешивалась в предмет этих критериев."""

    def setUp(self):
        super().setUp()
        self.set_model(INCIDENT_MODEL)
        self.set_cli_version("9.9.9")

    def test_ac1_argv0_is_the_absolute_path_from_the_manifest_resolve(self):
        """Шаг роли запускается абсолютным путём `claude`, добытым тем же
        резолвом манифеста, из которого собирается PATH роли, — а не
        голым именем, которое CLI ищет по PATH в момент запуска.

        Ловит мутацию: `role_cmd()` оставлен начинаться литералом
        `"claude"` (либо абсолютный путь подставлен не из резолва
        манифеста, а, например, из `sys.argv`/жёсткой строки) — argv[0]
        перестаёт совпадать с `shutil.which("claude")`.
        """
        self.run_step()

        argv0 = self.argv()[0]
        self.assertEqual(argv0, shutil.which("claude"),
                         "argv[0] обязан быть путём резолва манифеста")
        self.assertTrue(Path(argv0).is_absolute(), argv0)
        self.assertNotEqual(argv0, "claude",
                            "литерал `claude` в argv[0] — предмет AC-1")

    def test_ac2_flag_composition_after_argv0_is_unchanged(self):
        """Состав и порядок флагов шага — те же, что до задачи, `--model`
        по-прежнему довеском в конце.

        Ловит мутацию: правка argv[0] заодно переставляет/теряет флаги
        изоляции (`--setting-sources`, `--strict-mcp-config`) либо
        вклинивает `--model` в середину списка.
        """
        self.run_step()

        self.assertEqual(self.argv()[1:],
                         expected_flags() + ["--model", INCIDENT_MODEL])

    def test_ac2_role_path_composition_and_order_are_unchanged(self):
        """PATH роли — `.artel/venv/bin` первым, дальше каталоги
        объявленных манифестом инструментов в порядке манифеста.

        Ловит мутацию: резолв для argv[0] «заодно» переписывает сборку
        PATH роли — каталог `claude` уходит из PATH (раз бинарник теперь
        зовётся по полному пути) или встаёт первым, раньше
        `.artel/venv/bin`.
        """
        env = runner.role_env(self.ROLE, self.TASK)

        self.assertEqual(env["PATH"].split(os.pathsep),
                         expected_role_path_dirs())

    def test_ac3_declared_binary_wins_over_a_namesake_in_another_tools_dir(self):
        """Сценарий затенения (инцидент 06.09): каталог другого
        объявленного инструмента (`gh`) несёт одноимённый `claude` и
        стоит в PATH роли РАНЬШЕ каталога `claude` из резолва манифеста —
        шаг обязан запустить бинарник резолва, а не тёзку.

        Ловит мутацию: argv[0] оставлен именем (или собирается поиском по
        PATH роли) — запускается `claude` из каталога `gh`, стоящего в
        PATH раньше.
        """
        resolved_dir = self.root / "resolved-bin"
        other_tool_dir = self.root / "gh-bin"
        resolved_dir.mkdir()
        other_tool_dir.mkdir()
        write_executable(resolved_dir / "claude")
        write_executable(other_tool_dir / "gh")
        namesake = write_executable(other_tool_dir / "claude")
        path = os.pathsep.join([str(resolved_dir), str(other_tool_dir),
                                os.environ.get("PATH", "")])

        with mock.patch.dict(os.environ, {"PATH": path}):
            role_path = runner.role_env(self.ROLE, self.TASK)["PATH"]
            self.run_step()
            argv0 = self.argv()[0]

        dirs = role_path.split(os.pathsep)
        self.assertLess(dirs.index(str(other_tool_dir)),
                        dirs.index(str(resolved_dir)),
                        f"сценарий затенения не воспроизведён: {dirs}")
        self.assertEqual(argv0, str(resolved_dir / "claude"))
        self.assertNotEqual(argv0, str(namesake))


if __name__ == "__main__":
    unittest.main()
