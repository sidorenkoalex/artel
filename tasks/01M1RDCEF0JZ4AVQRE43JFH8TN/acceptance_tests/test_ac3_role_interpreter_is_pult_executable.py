"""Приёмочный тест AC-3 (tasks/01M1RDCEF0JZ4AVQRE43JFH8TN/SPEC.md,
«Критерии приёмки»).

AC-3: Интерпретатор роли — `sys.executable` пульта, не первый `python3`,
найденный в собранном PATH роли.

Красен до реализации: сегодня `role_env` не резолвит `python3` через
манифест вообще (PATH — копия `os.environ`), поэтому нет никакой
гарантии, что каталог `sys.executable` окажется первым в PATH роли —
тест ниже нарочно подсовывает ДРУГОЙ (заведомо отличный от
`sys.executable`) путь как ответ `shutil.which("python3")` и проверяет,
что он не выигрывает поиск.
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

# Заведомо ДРУГОЙ python3, чем sys.executable пульта — имитирует pyenv shim
# из PATH Оператора (ровно тот сценарий, ради которого написан AC-3:
# 217 логов шагов с pytest из pyenv, «Контекст» SPEC).
_DIVERGENT_PYTHON3 = "/opt/fake-pyenv/shims/python3"

FAKE_TOOL_PATHS = {
    "python3": _DIVERGENT_PYTHON3,
    "git": "/usr/bin/git",
    "gh": "/usr/local/bin/gh",
    "claude": "/usr/local/bin/claude",
}


def _fake_which(name, *args, **kwargs):
    return FAKE_TOOL_PATHS.get(name)


def _stub_git(*args):
    import subprocess
    return subprocess.CompletedProcess(list(args), 1, "", "")


class RoleInterpreterIsPultsSysExecutableTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        divergent_dir = str(Path(_DIVERGENT_PYTHON3).parent)
        interpreter_dir = str(Path(sys.executable).parent)
        # Гарантия фикстуры: если на машине прогона sys.executable ЖИВЁТ
        # именно в /opt/fake-pyenv/shims — тест ничего бы не доказывал
        # (обе стороны совпали бы случайно), поэтому фиксируем расхождение
        # заранее, а не полагаемся на удачу окружения CI.
        self.assertNotEqual(divergent_dir, interpreter_dir,
                            "фикстура должна отличаться от настоящего "
                            "интерпретатора пульта — иначе тест ничего не проверяет")

    def test_ac3_bare_python3_on_role_path_resolves_to_pults_interpreter(self):
        """`python3`, вызванный на собранном PATH роли, обязан
        резолвиться в `sys.executable` пульта, даже если `which` в
        окружении Оператора нашёл ДРУГОЙ `python3` первым.

        Ловит мутацию: если `role_env` кладёт в PATH каталог
        which-результата для `python3` как есть (без замены на каталог
        `sys.executable`) и притом раньше каталога интерпретатора,
        реальный поиск `python3` на итоговом PATH вернёт файл из
        `/opt/fake-pyenv/shims`, а не пультовый — `assertEqual` ниже
        покраснеет.
        """
        import shutil as real_shutil  # без патча — резолвим на СОБРАННОМ PATH

        # Настоящий исполняемый файл под именем "python3" в каталоге
        # sys.executable — гарантирует, что реальное разрешение видит
        # интерпретатор пульта как валидного кандидата (на некоторых
        # системах бинарь называется python3.NN без симлинка python3).
        interpreter_dir = Path(sys.executable).parent
        probe = interpreter_dir / "python3"
        created_probe = False
        if not probe.exists():
            try:
                probe.symlink_to(sys.executable)
                created_probe = True
            except OSError:
                self.skipTest("нет прав на symlink в каталоге интерпретатора")

        try:
            with mock.patch("shutil.which", side_effect=_fake_which), \
                    mock.patch.object(runner.gitcmd, "git", _stub_git):
                env = runner.role_env()

            resolved = real_shutil.which("python3", path=env["PATH"])
            self.assertIsNotNone(resolved, "python3 не резолвится вовсе на PATH роли")
            self.assertEqual(str(Path(resolved).resolve()),
                             str(Path(sys.executable).resolve()))
        finally:
            if created_probe:
                probe.unlink()

    def test_ac3_role_path_does_not_put_the_divergent_python3_dir_first(self):
        """Каталог `sys.executable` идёт в PATH роли РАНЬШЕ каталога,
        который `which` вернул бы для `python3` в окружении Оператора
        (если тот каталог вообще попал в PATH роли).

        Ловит мутацию: интерпретатор добавлен в PATH ПОСЛЕ
        which-результата для python3 (или не добавлен вовсе) — порядок
        поиска отдаёт первый `python3` не пульту.
        """
        with mock.patch("shutil.which", side_effect=_fake_which), \
                mock.patch.object(runner.gitcmd, "git", _stub_git):
            env = runner.role_env()

        parts = env["PATH"].split(os.pathsep)
        interpreter_dir = str(Path(sys.executable).parent)
        divergent_dir = str(Path(_DIVERGENT_PYTHON3).parent)

        self.assertIn(interpreter_dir, parts,
                     "каталог sys.executable отсутствует в PATH роли")
        if divergent_dir in parts:
            self.assertLess(parts.index(interpreter_dir), parts.index(divergent_dir),
                            "which-результат для python3 обгоняет sys.executable в PATH")


if __name__ == "__main__":
    unittest.main()
