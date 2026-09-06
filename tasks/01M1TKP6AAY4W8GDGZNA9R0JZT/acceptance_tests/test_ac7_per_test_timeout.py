"""AC-7 (SPEC.md, требование 4): таймаут ОТДЕЛЬНОГО теста (плагин
pytest-timeout, значение — именованная константа `orchestrator/stack.py`,
по умолчанию 120с, из требования 6 конфигурации `pyproject.toml`/
`pytest.ini`) укладывает намеренно зависший тест-метод, не роняя весь
прогон по общему таймауту `config.ACCEPTANCE_TIMEOUT_SEC`.

Тест намеренно НЕ использует `@pytest.mark.timeout(N)` с маленьким N —
маркер работал бы уже сегодня (pytest-timeout установлен и активен по
умолчанию, см. `requirements.lock`) и доказывал бы только то, что
сторонняя библиотека сама по себе исправна, а не то, что ЭТА задача
корректно связала значение `stack.py` с конфигурацией `pyproject.toml`/
`pytest.ini` (требование 6). Каталог планки (`tdir/acceptance_tests`)
намеренно лежит ВНЕ дерева `code_root` (обычная ситуация в проде —
планка задачи и код лежат в разных worktree): эмпирическая проверка
(`pytest <путь-вне-cwd>` с `cwd=<каталог с pytest.ini>`) подтвердила, что
голого `cwd=code_root` уже достаточно — pytest учитывает `cwd` как
кандидата поиска конфигурации независимо от расположения аргументов
путей теста, — но именно это и стоит закрепить регресс-тестом, а не
считать гарантией без проверки.

Красен до реализации: `pyproject.toml`/`pytest.ini` (требование 6) в
корне репозитория ещё не заведены — `_util.read_pytest_config` возвращает
`None`, `assertIsNotNone` в `setUp` падает раньше собственно прогона;
после появления файла конфигурации, но до правки `acceptance.run()` под
требование 1, `run()` всё ещё зовёт `unittest discover`, который не
собирает голую pytest-функцию с `@pytest.mark` вовсе (в этом файле его
нет — здесь обычный `unittest.TestCase`, поэтому в фазе «раннер ещё
unittest» тест реально повиснет на все 3×дефолт таймаута, будет убит
`config.ACCEPTANCE_TIMEOUT_SEC` подстраховкой ниже, и `assertNotIn`
«превысил» откажет так же честно, как и отсутствие pytest-сводки).
"""
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import acceptance, config  # noqa: E402
from _util import read_pytest_config  # noqa: E402

HANGING_TEST = """import time
import unittest


class MarkerTest(unittest.TestCase):
    def test_hangs_forever(self):
        time.sleep({sleep_seconds})
"""


class PerTestTimeoutTest(unittest.TestCase):

    def setUp(self):
        self.cfg = read_pytest_config(REPO_ROOT)
        self.assertIsNotNone(
            self.cfg,
            "требование 6 (pyproject.toml/pytest.ini с таймаутом по "
            "умолчанию) ещё не заведено — нечего читать")
        self.default_timeout = self.cfg["timeout"]
        self.assertIsNotNone(
            self.default_timeout,
            f"конфигурация pytest найдена, но без ключа timeout: {self.cfg}")

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True)
        sleep_seconds = self.default_timeout + 10
        (tests_dir / "test_marker.py").write_text(
            HANGING_TEST.format(sleep_seconds=sleep_seconds), encoding="utf-8")

    @pytest.mark.timeout(600)
    # Собственный таймаут ЭТОГО (внешнего) теста-обёртки — маркер
    # переопределяет ini-дефолт задачи (120с) высочайшим приоритетом
    # pytest-timeout: сам сценарий ждёт, пока ВНУТРЕННИЙ (порождённый
    # subprocess'ом) прогон исчерпает ini-дефолт (~120с) плюс накладные
    # расходы — без переопределения внешний тест столкнулся бы с тем же
    # ini-дефолтом раньше, чем внутренний прогон успеет её продемонстрировать
    # (эмпирически найдено при валидации стабом: внешний тест был убит
    # тем же таймаутом на 120.11с).
    def test_ac7_hanging_test_is_cut_by_per_test_timeout_not_whole_run(self):
        """Тест, спящий дольше настроенного ПО УМОЛЧАНИЮ таймаута
        отдельного теста (`default_timeout + 10`с), убит pytest-timeout
        задолго до общего таймаута `run()` (подмена
        `config.ACCEPTANCE_TIMEOUT_SEC` на заведомо больший запас) —
        хвост несёт формулировку pytest-timeout, не «прогон превысил».

        Ловит мутацию: `acceptance.run()` собирает pytest-команду, но
        забывает прокинуть `cwd=code_root` в `subprocess.run` (например,
        наследует старое поведение `cwd=run_cwd` только частично или
        обнуляет его при рефакторинге) — плагин таймаута не находит
        `pyproject.toml`/`pytest.ini` из требования 6, зависший тест
        ждёт весь запас `config.ACCEPTANCE_TIMEOUT_SEC` (общий таймаут
        срабатывает первым, `assertNotIn` «превысил» откажет).
        """
        safety_margin = self.default_timeout + 60
        started = time.perf_counter()
        with mock.patch.object(config, "ACCEPTANCE_TIMEOUT_SEC", safety_margin):
            green, tail = acceptance.run(self.tdir, REPO_ROOT)
        elapsed = time.perf_counter() - started

        self.assertFalse(green, tail)
        self.assertNotIn(
            "превысил", tail,
            f"тест убит общим таймаутом run(), не таймаутом отдельного "
            f"теста: {tail}")
        self.assertIn("pytest-timeout", tail, tail)
        self.assertIn("Timeout", tail, tail)
        self.assertLess(
            elapsed, safety_margin - 5,
            f"прогон занял {elapsed:.1f}с — почти весь запас "
            f"{safety_margin}с, таймаут отдельного теста не сработал "
            f"раньше общего")


if __name__ == "__main__":
    unittest.main()
