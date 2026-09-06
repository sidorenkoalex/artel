"""AC-1, AC-2 (SPEC.md, требование 1): `orchestrator.acceptance.run()`
переходит на pytest как раннер приёмочной планки задачи, сохраняя
контракт (зелёно/хвост, вырожденный случай без acceptance_tests/, cwd
прогона, строка `location_note`) и таймаут ВСЕГО прогона.

Красен до реализации: `run()` на этой ветке всё ещё вызывает `python3 -m
unittest discover` — три теста падают именно поэтому (проверено прогоном,
не все шесть тестов файла — см. ниже): `test_ac1_passing_plank_is_green_with_pytest_summary_in_tail`
и `test_ac1_failing_plank_is_red_with_pytest_style_wording` (хвост несёт
unittest-формат «OK»/«FAILED (failures=…)», не pytest-формат «passed»/
«failed») и `test_ac1_invokes_pytest_with_explicit_code_root_as_cwd`
(команда всё ещё содержит `unittest`/`discover`). Остальные три теста
файла УЖЕ зелёные на текущем коде — контроль, не молчаливый пропуск:
`test_ac1_missing_acceptance_tests_is_degenerate_success` (вырожденный
случай не зависит от раннера), `test_ac1_defaults_cwd_to_config_root_when_code_root_none`
(маршрутизация `cwd`/`location_note` при `code_root=None` — существующая
логика, требование 1 её не меняет) и `test_ac2_timeout_of_whole_run_is_red_with_timeout_message`
(`subprocess.TimeoutExpired` ловится одинаково для обеих команд) —
оставлены в этом файле как регресс-гарантия того же требования 1, а не
вынесены отдельным «зелёным» файлом.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import acceptance, config  # noqa: E402

PASSING_TEST = """import unittest


class MarkerTest(unittest.TestCase):
    def test_always_passes(self):
        self.assertTrue(True)
"""

FAILING_TEST = """import unittest


class MarkerTest(unittest.TestCase):
    def test_deliberately_fails(self):
        self.fail("MARKER-RED")
"""

SLEEPING_TEST = """import time
import unittest


class MarkerTest(unittest.TestCase):
    def test_sleeps_past_the_timeout(self):
        time.sleep(3)
"""


class RunPytestContractTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)

    def write_acceptance_test(self, content: str) -> Path:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_marker.py").write_text(content, encoding="utf-8")
        return tests_dir

    def test_ac1_missing_acceptance_tests_is_degenerate_success(self):
        """Планки нет вовсе (каталог `acceptance_tests/` отсутствует) —
        `run()` не блокирует переход: возврат ровно
        `(True, "acceptance_tests/ нет — приёмочные тесты не заведены")`,
        байт в байт, как и до перехода на pytest.

        Ловит мутацию: переход на pytest меняет порядок проверок и
        пытается вызвать pytest на несуществующем каталоге вместо
        раннего `return True, ...` — `subprocess`-раннер либо падает,
        либо возвращает другое сообщение, `assertEqual` откажет.
        """
        green, tail = acceptance.run(self.tdir)
        self.assertEqual(
            (green, tail),
            (True, "acceptance_tests/ нет — приёмочные тесты не заведены"))

    def test_ac1_passing_plank_is_green_with_pytest_summary_in_tail(self):
        """Реальный прогон каталога с одним проходящим `unittest.TestCase`
        тестом под pytest (без моков subprocess) — зелёный результат,
        хвост начинается с `location_note` и несёт pytest-сводку («N
        passed»), не unittest-сводку («OK»).

        Ловит мутацию: `run()` продолжает звать `python3 -m unittest
        discover` — хвост несёт «OK» без «passed», `assertRegex` на
        `\\d+ passed` откажет; либо `location_note` перестал быть первой
        строкой хвоста (переставлен порядок конкатенации) —
        `assertTrue(tail.startswith(...))` откажет.
        """
        tests_dir = self.write_acceptance_test(PASSING_TEST)
        code_root = self.tdir

        green, tail = acceptance.run(self.tdir, code_root)

        self.assertTrue(green, tail)
        location_note = f"планка: {tests_dir}, cwd: {code_root}"
        self.assertTrue(
            tail.startswith(location_note),
            f"хвост не начинается с location_note: {tail[:200]!r}")
        self.assertRegex(
            tail, r"\d+\s+passed",
            f"хвост зелёного прогона не несёт pytest-сводку 'N passed': {tail}")

    def test_ac1_failing_plank_is_red_with_pytest_style_wording(self):
        """Реальный прогон одного намеренно красного теста под pytest —
        красный результат, диагностика (`MARKER-RED`) в хвосте, формат
        сводки — pytest («failed»), не unittest («FAILED (failures=1)»).

        Ловит мутацию: `run()` не переключён на pytest — красная сводка
        приходит в формате `FAILED (failures=1)`, `assertNotIn` на этот
        unittest-формат откажет вместе с `assertRegex` на pytest-формат.
        """
        self.write_acceptance_test(FAILING_TEST)

        green, tail = acceptance.run(self.tdir, self.tdir)

        self.assertFalse(green)
        self.assertIn("MARKER-RED", tail)
        self.assertRegex(tail, r"\d+\s+failed")
        self.assertNotIn(
            "FAILED (failures=", tail,
            "хвост несёт unittest-формат провала вместо pytest-сводки")

    def test_ac1_invokes_pytest_with_explicit_code_root_as_cwd(self):
        """`code_root`, переданный явно, — ровно тот `cwd`, с которым
        запускается прогон; сама команда содержит признак pytest, не
        `python3 -m unittest discover`.

        Ловит мутацию: `run()` продолжает собирать команду вида
        `["python3", "-m", "unittest", "discover", ...]` — проверка
        отсутствия токенов `unittest`/`discover` откажет; либо `cwd`
        прогона не совпадает с переданным `code_root` (например,
        разработчик забыл прокинуть параметр дальше в новый вызов) —
        `assertEqual` на `kwargs["cwd"]` откажет.
        """
        self.write_acceptance_test(PASSING_TEST)
        code_root = self.tdir / "code"
        code_root.mkdir()
        captured = {}

        def fake_run(args, **kwargs):
            captured["args"] = list(args)
            captured["kwargs"] = kwargs
            return subprocess.CompletedProcess(args, 0, "1 passed in 0.01s\n", "")

        with mock.patch.object(acceptance.subprocess, "run", fake_run):
            acceptance.run(self.tdir, code_root)

        self.assertIn("args", captured, "run() не позвал subprocess.run вовсе")
        args_text = " ".join(captured["args"])
        self.assertIn("pytest", args_text.lower(),
                      f"команда не упоминает pytest: {captured['args']}")
        self.assertNotIn("unittest", args_text.lower(),
                         f"команда всё ещё зовёт unittest: {captured['args']}")
        self.assertEqual(captured["kwargs"].get("cwd"), code_root)

    def test_ac1_defaults_cwd_to_config_root_when_code_root_none(self):
        """`code_root=None` — `cwd` прогона равен `config.ROOT` (не
        каталогу планки `tdir`), а `location_note` называет именно его.

        Ловит мутацию: `code_root=None` трактуется как «не передавай
        cwd вовсе» (наследование cwd процесса пульта) вместо явного
        `config.ROOT` — `assertEqual(kwargs["cwd"], fake_root)` откажет.
        """
        self.write_acceptance_test(PASSING_TEST)
        fake_root = self.tdir / "fake-root"
        fake_root.mkdir()
        captured = {}

        def fake_run(args, **kwargs):
            captured["kwargs"] = kwargs
            return subprocess.CompletedProcess(args, 0, "1 passed in 0.01s\n", "")

        with mock.patch.object(config, "ROOT", fake_root), \
             mock.patch.object(acceptance.subprocess, "run", fake_run):
            green, tail = acceptance.run(self.tdir, None)

        self.assertEqual(captured["kwargs"].get("cwd"), fake_root)
        self.assertTrue(tail.startswith(f"планка: {self.tdir / 'acceptance_tests'}, "
                                        f"cwd: {fake_root}"))

    def test_ac2_timeout_of_whole_run_is_red_with_timeout_message(self):
        """Превышение таймаута ВСЕГО прогона (`config.ACCEPTANCE_TIMEOUT_SEC`,
        подменённого на 1с) намеренно спящим тестом (3с) по-прежнему даёт
        красный результат с текстом о превышении таймаута и хвостом
        вывода.

        Ловит мутацию: обработчик `subprocess.TimeoutExpired` потерян при
        переходе на pytest (например, `timeout=` забыт при сборке новой
        команды) — исключение уйдёт наружу вместо `(False, ...)`, тест
        упадёт с necaught TimeoutExpired вместо `assertFalse`.
        """
        self.write_acceptance_test(SLEEPING_TEST)

        with mock.patch.object(config, "ACCEPTANCE_TIMEOUT_SEC", 1):
            green, tail = acceptance.run(self.tdir, self.tdir)

        self.assertFalse(green)
        self.assertIn("превысил", tail)
        self.assertIn("1с", tail)


if __name__ == "__main__":
    unittest.main()
