"""AC-12, AC-13 (tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/SPEC.md, требование 4):
`orchestrator.runner.role_env()` — расширение S3 (01M1RDCEF0JZ4AVQRE43JFH8TN,
роль ещё не начата на момент написания этой планки: её ветка совпадает с
main) — выбирает интерпретатором python из `.artel/venv`, когда он
согласован с файлом закреплённых версий, и отказывает без тихого отката
иначе.

Красен до реализации: `role_env()` сегодня не знает о venv вовсе — при
подмене `runner.stack` тест упадёт `AttributeError` (атрибута `stack` у
`orchestrator.runner` ещё нет, S1/S3 не смержены).

Контракт, который эта планка фиксирует за разработчика (SPEC называет
только НАБЛЮДАЕМОЕ поведение, не внутренний механизм): «согласован с
файлом закреплённых версий» — та же проверка, что AC-7/AC-8
(`orchestrator.stack.check_stack()`), а не отдельная копия логики
(требование 2/4 SPEC оба явно на неё ссылаются) — тест подменяет
`runner.stack.check_stack` целиком (тем же приёмом, что уже установлен
S1 для `version.py`: `tasks/01M1RDCAFENSW2VVAPECHCVGMM/acceptance_tests/
test_ac12_ac13_version_output_new_lines.py` подменяет
`orchestrator.stack.check_stack`), не пытаясь угадать, каким именно
файлом/подпроцессом check_stack() сам решает «согласован».

Именно поэтому AC-13 испытывается на `role_env()` (граница НОВОГО кода
этой задачи), а не на всём цикле `run_agent_once`/`agent run SKIPPED`:
`role_env()` может поднять `OSError` — уже ДОКУМЕНТИРОВАННЫЙ существующий
контракт (`orchestrator/doctor.py::check_git_identity`, докстринг:
«role_env() может поднять OSError... настоящий отказ шага по этой
причине остаётся за существующей обработкой в runner.run_agent_once
(agent run SKIPPED)») — по образцу S3, ссылку на который несёт
требование 4 SPEC буквально. Раз этот путь `OSError -> SKIPPED` уже
существует и не меняется этой задачей, «шаг не стартует» из AC-13
сводится к тому, что новая проверка тоже поднимает `OSError` с
именующей причиной, а не тихо возвращает обычное окружение.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, runner  # noqa: E402


def _stack_check(name: str, status: str, detail: str):
    from types import SimpleNamespace
    return SimpleNamespace(name=name, status=status, detail=detail)


class RoleEnvVenvInterpreterTest(unittest.TestCase):

    def test_ac12_consistent_venv_puts_its_bin_first_on_path(self):
        """Требование 4/AC-12: venv существует и согласован (все
        проверки `check_stack()` — `ok`) — PATH окружения роли начинается
        с `<venv>/bin`, то есть голые вызовы `python3`/`pytest` внутри
        шага роли резолвятся в интерпретатор venv, а не в системный.

        Ловит мутацию: `role_env()` не трогает PATH вовсе при согласованном
        venv (интерпретатор роли остаётся системным несмотря на готовый
        venv) — `assertTrue(startswith(...))` откажет.
        """
        venv_dir = Path("/tmp/фейковый-venv-для-теста-ac12")
        ok_checks = [_stack_check("python", "ok", "Python 3.99.0"),
                    _stack_check("venv", "ok", "venv согласован")]

        with mock.patch.object(config, "VENV_DIR", venv_dir, create=True), \
             mock.patch.object(runner.stack, "check_stack",
                               return_value=ok_checks):
            env = runner.role_env()

        expected_bin = str(venv_dir / "bin")
        path_entries = env["PATH"].split(":")
        self.assertEqual(
            expected_bin, path_entries[0],
            f"PATH окружения роли не начинается с bin venv: {env['PATH']!r}")

    def test_ac13_inconsistent_venv_raises_instead_of_silently_using_the_system_python(self):
        """Требование 4/AC-13: `.artel/venv` не согласован с файлом
        закреплённых версий (`check_stack()` возвращает WARN про venv) —
        `role_env()` отказывает поднятым `OSError` с именующей причиной,
        а НЕ тихо возвращает окружение с системным PATH как ни в чём не
        бывало.

        Ловит мутацию: `role_env()` игнорирует WARN про venv и всё равно
        возвращает обычное окружение (тихий откат на системный python) —
        `assertRaises(OSError)` не сработает (исключения не будет);
        либо исключение поднимается, но без упоминания venv в тексте —
        `assertIn` в `str(exc)` откажет.
        """
        venv_dir = Path("/tmp/фейковый-venv-для-теста-ac13")
        warn_checks = [_stack_check("python", "ok", "Python 3.99.0"),
                      _stack_check("venv-packages", "warn",
                                   "версии расходятся: pytest")]

        with mock.patch.object(config, "VENV_DIR", venv_dir, create=True), \
             mock.patch.object(runner.stack, "check_stack",
                               return_value=warn_checks):
            with self.assertRaises(OSError) as ctx:
                runner.role_env()

        self.assertIn("venv", str(ctx.exception).lower(),
                      f"причина отказа не называет venv: {ctx.exception}")

    def test_ac13_missing_venv_also_raises_rather_than_falling_back(self):
        """Требование 4/AC-13 — вторая ветка того же критерия: venv
        вовсе ОТСУТСТВУЕТ (`check_stack()` возвращает WARN «venv» с
        отсутствием, не только расхождением версий) — тот же отказ
        `OSError`, не деградация до системного python.

        Ловит мутацию: обработана только ветка «версии разошлись», а
        ветка «venv вовсе нет» тихо пропускается (например код проверяет
        только статус проверки `venv-packages`, забыв про `venv`) —
        `assertRaises` не сработает.
        """
        venv_dir = Path("/tmp/несуществующий-venv-для-теста-ac13b")
        warn_checks = [_stack_check("python", "ok", "Python 3.99.0"),
                      _stack_check("venv", "warn",
                                   "venv не создан — `python3 artel.py "
                                   "venv-sync`")]

        with mock.patch.object(config, "VENV_DIR", venv_dir, create=True), \
             mock.patch.object(runner.stack, "check_stack",
                               return_value=warn_checks):
            with self.assertRaises(OSError):
                runner.role_env()


if __name__ == "__main__":
    unittest.main()
