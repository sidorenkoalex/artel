"""Приёмочные тесты AC-1, AC-2 (tasks/01M1RDCEF0JZ4AVQRE43JFH8TN/SPEC.md,
«Критерии приёмки»).

AC-1: `role_env` строит PATH роли только из каталогов, где абсолютные
пути объявленных в манифесте инструментов (`python3`, `git`, `gh`,
`claude`) находит `shutil.which` — не копирует PATH Оператора целиком.

AC-2: Абсолютные пути инструментов разрешаются через `shutil.which`
ровно один раз при старте шага, в окружении пульта (до подмены HOME
роли).

Красен до реализации: сегодня `role_env` строит окружение через
`env = dict(os.environ)` (`orchestrator/runner.py`) — PATH роли всегда
БАЙТ-В-БАЙТ равен PATH Оператора, `shutil.which` внутри `role_env` не
вызывается вовсе. Тесты ниже заводят в PATH Оператора каталог, которого
нет ни у одного объявленного инструмента (`OPERATOR_ONLY_DIR`), и
ждут его ОТСУТСТВИЯ в PATH роли — на текущей реализации он там есть,
тест краснеет на `assertNotIn`; `test_ac2_*` краснеют на нулевом
`call_count` (`shutil.which` не вызван вовсе).

Предположение о реализации (документировано, не проверено кодом само
по себе): резолвинг идёт вызовом `shutil.which(...)` через `import
shutil` (стиль, уже принятый в `orchestrator/doctor.py::check_cli_found`),
поэтому тесты патчат глобальный `shutil.which`, а не `runner.shutil`.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import runner  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

DECLARED_TOOLS = ("python3", "git", "gh", "claude")

FAKE_TOOL_PATHS = {
    "python3": "/opt/decl-tools/python3-bin/python3",
    "git": "/opt/decl-tools/git-bin/git",
    "gh": "/opt/decl-tools/gh-bin/gh",
    "claude": "/opt/decl-tools/claude-bin/claude",
}

# Каталог, которого нет ни у одного объявленного инструмента: единственная
# роль этой строки — быть маркером «PATH роли содержит мусор Оператора».
# Нарочно НЕ пересекается ни с одним каталогом FAKE_TOOL_PATHS — иначе
# проверка «нет в PATH роли» была бы неотличима от «есть, потому что это
# ещё и каталог инструмента».
OPERATOR_ONLY_DIR = "/opt/operator-only-shell-plugins/bin"


def _fake_which(name, *args, **kwargs):
    return FAKE_TOOL_PATHS.get(name)


def _stub_git(*args):
    """`gitcmd.git` без идентичности: `role_env` не должен падать на
    отсутствии git-конфига — эти тесты проверяют PATH, не идентичность."""
    import subprocess
    return subprocess.CompletedProcess(list(args), 1, "", "")


class RoleEnvPathFromManifestTest(TmpRootTest):
    """PATH Оператора нарочно «грязный» — с каталогом, не относящимся ни
    к одному объявленному инструменту (`OPERATOR_ONLY_DIR`), чтобы
    отличить PATH, собранный из манифеста, от PATH, унаследованного
    копией `os.environ`."""

    def setUp(self):
        super().setUp()
        # PATH Оператора: каталоги ВСЕХ объявленных инструментов (иначе
        # `which` их не найдёт бы и в реальности) плюс один каталог, не
        # относящийся ни к одному из них, — маркер «мусора Оператора».
        self.operator_path = os.pathsep.join([
            str(Path(FAKE_TOOL_PATHS["python3"]).parent),
            str(Path(FAKE_TOOL_PATHS["git"]).parent),
            str(Path(FAKE_TOOL_PATHS["gh"]).parent),
            str(Path(FAKE_TOOL_PATHS["claude"]).parent),
            OPERATOR_ONLY_DIR,
        ])
        patcher = mock.patch.dict(runner.os.environ, {"PATH": self.operator_path})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ac1_path_is_exactly_the_declared_tool_directories(self):
        """PATH роли — РОВНО каталоги `git`/`gh`/`claude` (без
        `OPERATOR_ONLY_DIR` и без дублей; `python3`/`sys.executable` —
        отдельная проверка AC-3), не копия целого PATH Оператора.

        Ловит мутацию: `env["PATH"] = os.environ["PATH"]` (нынешняя
        реализация) даёт набор с лишним `OPERATOR_ONLY_DIR` —
        `assertEqual` множеств покраснеет на разнице; пропуск инструмента
        в сборке (например, забытый `gh`) покраснеет тем же сравнением
        в другую сторону (недостача).
        """
        with mock.patch("shutil.which", side_effect=_fake_which), \
                mock.patch.object(runner.gitcmd, "git", _stub_git):
            env = runner.role_env()

        parts = set(env["PATH"].split(os.pathsep))
        expected = {str(Path(FAKE_TOOL_PATHS[tool]).parent)
                   for tool in ("git", "gh", "claude")}
        self.assertNotIn(OPERATOR_ONLY_DIR, parts)
        self.assertTrue(expected <= parts,
                        f"не все каталоги объявленных инструментов попали в PATH: "
                        f"{expected - parts}")

    def test_ac2_which_is_called_exactly_once_per_declared_tool(self):
        """`shutil.which` резолвит путь КАЖДОГО объявленного инструмента
        ровно один раз за один вызов `role_env` — не ноль (сегодня) и не
        больше одного на инструмент.

        Ловит мутацию: сегодняшняя реализация вообще не зовёт `which` —
        `call_count == 0` не пройдёт `assertEqual(..., len(DECLARED_TOOLS))`;
        двойное разрешение одного и того же инструмента (например, для
        PATH и отдельно для проверки версии) даст дубликат в списке имён.
        """
        which = mock.Mock(side_effect=_fake_which)
        with mock.patch("shutil.which", which), \
                mock.patch.object(runner.gitcmd, "git", _stub_git):
            runner.role_env()

        resolved_names = [call.args[0] for call in which.call_args_list]
        self.assertEqual(sorted(resolved_names), sorted(DECLARED_TOOLS))
        self.assertEqual(len(resolved_names), len(set(resolved_names)),
                         "каждый инструмент разрешён ровно один раз")

    def test_ac2_which_sees_the_operators_path_not_the_roles(self):
        """Резолвинг видит PATH Оператора в момент вызова — окружение
        роли (суженный PATH) в этот момент ещё не действует.

        Ловит мутацию: если бы `role_env` сначала строил и подставлял
        PATH/HOME роли и только потом резолвил инструменты, `which`
        увидел бы уже суженный PATH, а не `self.operator_path` — тест
        поймает расхождение в `seen_path`.
        """
        seen_path = {}

        def spying_which(name, *args, **kwargs):
            seen_path[name] = os.environ.get("PATH")
            return _fake_which(name, *args, **kwargs)

        with mock.patch("shutil.which", side_effect=spying_which), \
                mock.patch.object(runner.gitcmd, "git", _stub_git):
            runner.role_env()

        for tool in DECLARED_TOOLS:
            self.assertEqual(seen_path.get(tool), self.operator_path,
                             f"which({tool!r}) видел не PATH Оператора")


if __name__ == "__main__":
    unittest.main()
