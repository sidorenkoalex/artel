"""AC-7, AC-8, AC-9, AC-10, AC-17 (tasks/01M1RDCAFENSW2VVAPECHCVGMM/SPEC.md,
требование 4): поведение `orchestrator.stack.check_stack()`.

Красен до реализации: `orchestrator/stack.py` (и его функция
`check_stack()`) ещё не существуют — импорт модуля падает
`ModuleNotFoundError` для всех тестов ниже.

Подмена `subprocess.run` — через `stack.subprocess` (модульный объект
внутри `orchestrator/stack.py`), тем же приёмом, что
`tests/test_version.py` (`mock.patch.object(doctor.subprocess, "run",
...)`) и `tests/test_doctor.py`: единый источник подмены на весь
процесс, не отдельный мок на инструмент.

Версии-заглушки выбраны заведомо ЗА пределами любого правдоподобного
диапазона («999.999.999» — заведомо выше любого реалистичного минимума,
«0.0.1» — заведомо ниже) — тесты не знают и не обязаны знать конкретные
минимальные версии, объявленные разработчиком в манифесте (требование 1,
AC-2/AC-3 этой же планки их не фиксируют численно).
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import stack  # noqa: E402

HIGH_VERSION = "999.999.999"
LOW_VERSION = "0.0.1"
OK_PYTHON_VERSION_INFO = (3, 99, 0, "final", 0)


def _all_ok_run(args, **kwargs):
    return subprocess.CompletedProcess(args, 0, f"{HIGH_VERSION}\n", "")


def _run_with_low_version_for(tool: str):
    def fake_run(args, **kwargs):
        version = LOW_VERSION if args[0] == tool else HIGH_VERSION
        return subprocess.CompletedProcess(args, 0, f"{version}\n", "")
    return fake_run


def _run_with_missing_tool(tool: str):
    def fake_run(args, **kwargs):
        if args[0] == tool:
            raise FileNotFoundError(f"{tool}: команда не найдена")
        return subprocess.CompletedProcess(args, 0, f"{HIGH_VERSION}\n", "")
    return fake_run


class CheckStackTest(unittest.TestCase):

    def test_ac7_one_check_per_manifest_tool(self):
        """Требование 4/AC-7: по одной проверке на КАЖДЫЙ инструмент
        манифеста (Python, git, gh, claude) — ровно 4 проверки, когда все
        версии заведомо проходят порог.

        Ловит мутацию: `check_stack()` пропускает инструмент (забытая
        ветка цикла) или задваивает проверку одного и того же инструмента
        — счётчик проверок отклонится от 4, `assertEqual` откажет.
        """
        with mock.patch.object(stack.subprocess, "run", side_effect=_all_ok_run), \
             mock.patch.object(sys, "version_info", OK_PYTHON_VERSION_INFO):
            checks = stack.check_stack()

        self.assertEqual(
            4, len(checks),
            f"ожидалось 4 проверки (python, git, gh, claude), получено "
            f"{len(checks)}: {checks}")

    def test_ac8_version_mismatch_gives_warn_with_names_and_versions_in_one_line(self):
        """AC-8: инструмент с версией ниже минимально требуемой — статус
        WARN, текст в ОДНУ строку с именем инструмента, фактической и
        требуемой версией. `git` заведомо занижен (`LOW_VERSION`), `gh`/
        `claude` заведомо завышены (`HIGH_VERSION`) — WARN обязан
        относиться именно к `git`.

        Ловит мутацию: расхождение версии трактуется как `ok` (порог не
        сравнивается) или `detail` не несёт фактическую версию —
        `assertIn(LOW_VERSION, ...)` откажет; требуемая версия
        отсутствует в строке — второй `assertGreaterEqual` по числу
        различных версий в строке откажет.
        """
        with mock.patch.object(stack.subprocess, "run",
                               side_effect=_run_with_low_version_for("git")), \
             mock.patch.object(sys, "version_info", OK_PYTHON_VERSION_INFO):
            checks = stack.check_stack()

        warn_checks = [c for c in checks if c.status == "warn"]
        self.assertTrue(warn_checks, f"нет ни одной WARN-проверки: {checks}")
        detail = " ".join(c.detail for c in warn_checks)
        self.assertIn("git", detail.lower(), detail)
        self.assertIn(LOW_VERSION, detail, detail)
        version_numbers = set(re.findall(r"\d+(?:\.\d+){1,2}", detail))
        self.assertGreaterEqual(
            len(version_numbers), 2,
            f"строка WARN обязана содержать И фактическую, И требуемую "
            f"версию — найдено чисел: {version_numbers} в {detail!r}")

    def test_ac9_missing_tool_gives_fail(self):
        """AC-9: инструмент отсутствует в PATH/системе (`FileNotFoundError`
        на попытке его вызвать) — статус FAIL для этого инструмента, а не
        для остальных (`gh`/`claude` заведомо завышены и обязаны остаться
        ok).

        Ловит мутацию: отсутствие инструмента трактуется как `warn` (не
        `fail`) либо роняет весь `check_stack()` необработанным
        исключением вместо структурированного FAIL — оба случая
        `assertTrue`/сам вызов без исключения это поймают.
        """
        with mock.patch.object(stack.subprocess, "run",
                               side_effect=_run_with_missing_tool("gh")), \
             mock.patch.object(sys, "version_info", OK_PYTHON_VERSION_INFO):
            checks = stack.check_stack()

        fail_checks = [c for c in checks if c.status == "fail"]
        self.assertTrue(fail_checks, f"нет ни одной FAIL-проверки: {checks}")
        self.assertIn("gh", " ".join(c.detail for c in fail_checks).lower())

    def test_ac10_check_stack_makes_no_network_calls(self):
        """AC-10/инвариант 35 (docs/invariants.md): `check_stack()` не
        обращается к сети — подмена `socket.socket` на взрыв доказывает
        отсутствие попытки сетевого соединения при полностью успешном
        прогоне (все версии заведомо проходят порог, чтобы не спутать
        сетевой поход с обработкой WARN/FAIL).

        Ловит мутацию: реализация проверки версии инструмента вместо
        `subprocess`+CLI использует сетевой запрос (например, к API
        релизов инструмента) — `socket.socket` будет вызван, подмена
        поднимет `AssertionError`, и вызов `check_stack()` внутри `with`
        завершится этим исключением вместо штатного результата.
        """
        def explode(*args, **kwargs):
            raise AssertionError("check_stack() обратился к сети (socket.socket)")

        with mock.patch.object(stack.subprocess, "run", side_effect=_all_ok_run), \
             mock.patch.object(sys, "version_info", OK_PYTHON_VERSION_INFO), \
             mock.patch("socket.socket", side_effect=explode):
            checks = stack.check_stack()

        self.assertTrue(checks)

    def test_ac17_ok_warn_fail_scenarios_all_covered_in_one_run(self):
        """AC-17: три сценария `check_stack()` в одном прогоне с
        подменёнными `subprocess.run`/`sys.version_info` — python и
        `claude` в порядке (ok), `git` занижен (warn), `gh` отсутствует
        (fail).

        Ловит мутацию: любой из трёх статусов отсутствует среди
        результатов (например, реализация распознаёт только ok/fail, без
        промежуточного warn, либо не восстанавливается после
        `FileNotFoundError` одного инструмента и не проверяет
        остальные) — соответствующий `assertIn` откажет.
        """
        def fake_run(args, **kwargs):
            if args[0] == "git":
                return subprocess.CompletedProcess(args, 0, f"{LOW_VERSION}\n", "")
            if args[0] == "gh":
                raise FileNotFoundError("gh: команда не найдена")
            return subprocess.CompletedProcess(args, 0, f"{HIGH_VERSION}\n", "")

        with mock.patch.object(stack.subprocess, "run", side_effect=fake_run), \
             mock.patch.object(sys, "version_info", OK_PYTHON_VERSION_INFO):
            checks = stack.check_stack()

        statuses = {c.status for c in checks}
        self.assertIn("ok", statuses, checks)
        self.assertIn("warn", statuses, checks)
        self.assertIn("fail", statuses, checks)


if __name__ == "__main__":
    unittest.main()
