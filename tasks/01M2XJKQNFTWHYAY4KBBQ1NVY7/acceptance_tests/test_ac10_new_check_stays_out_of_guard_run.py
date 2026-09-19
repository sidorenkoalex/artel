"""AC-10: новая проверка не участвует в `check()`/`main()` guard, а
названные SPEC существующие тесты остаются зелёными.

Зелёный с рождения: проверки ещё нет, поэтому и `guard.py --all`, и пять названных тестовых файлов зелены уже сейчас — сценарии сторожат ровно тот способ сломать требование 7, который появится вместе с реализацией (подключение сверки к `check()`/`main()` и перепроверка исторических SPEC).
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from scripts import guard  # noqa: E402

REPO_ROOT = _util.REPO_ROOT

# Файлы из формулировки AC-10 — буквально.
NAMED_TESTS = ("tests/test_catalog_tz_zones_parsing.py",
               "tests/test_new_argv_parsing.py",
               "tests/test_guard_zones.py",
               "tests/test_guard_split_signals.py",
               "tests/test_guard_division_section.py")


class NewCheckStaysOutOfGuardRunTest(unittest.TestCase):

    def test_ac10_guard_over_all_task_artifacts_stays_green(self):
        """`python3 scripts/guard.py --all` по всему каталогу `tasks/`
        (тот же вызов, которым CI проверяет артефакты задач) остаётся
        зелёным — а в `tasks/` пульта исторические SPEC с путями вне
        зон есть (SPEC, «Контекст»: `answer.py`, `doctor.py`,
        `docs/adr`, `docs/reference/role-home.md`).

        Ловит мутацию: новая сверка подключена к `_content_errors`/
        `check()` ради «единообразия» — исторические SPEC покраснели бы
        разом, и `returncode` стал бы ненулевым.
        """
        res = subprocess.run([sys.executable, "scripts/guard.py", "--all"],
                             cwd=REPO_ROOT, capture_output=True, text=True,
                             timeout=90)

        self.assertEqual(res.returncode, 0,
                         f"guard --all покраснел:\n{res.stdout}\n{res.stderr}")

    def test_ac10_check_content_is_silent_about_an_unclassified_spec_path(self):
        """SPEC с путём, названным в «## Требования» и не покрытым
        `zones:`/«## Не входит»/«## Материалы», проходит через
        `guard.check_content` без единой ошибки, называющей этот путь:
        проверка требования 5 живёт отдельной функцией, а не в общем
        ядре содержания.

        Проверяется адресно, не только косвенно через зелёный `--all`
        выше: так сценарий не зависит от того, какие именно
        исторические SPEC лежат в `tasks/` в момент прогона.

        Ловит мутацию: новая функция вызвана из `_content_errors`
        (общего ядра `check`/`check_content`) — в списке ошибок
        появилось бы имя пути.
        """
        text = _util.spec_text(
            "01M2XJKQNFTWHYAY4KBBQ1NVY7",
            zones=_util.ZONE_PATH,
            requirement=f"Починить разбор ответа в {_util.UNCLASSIFIED_PATH}.")

        errors = guard.check_content("tasks/ФИКСТУРА/SPEC.md", text)

        named = [e for e in errors if _util.UNCLASSIFIED_PATH in e]
        self.assertEqual(named, [],
                         "check_content ссылается на неклассифицированный "
                         "путь — новая проверка попала в общее ядро")

    def test_ac10_named_existing_tests_stay_green(self):
        """Пять тестовых файлов, названных критерием поимённо, проходят
        целиком.

        Ловит мутацию: сборщик путей требования 1 написан правкой
        `ZONE_PATH`/`_zone_paths` вместо новой функции (прямой запрет
        требования 1) — `tests/test_guard_split_signals.py`, считающий
        сигнал деления по этому же множеству, покраснел бы.
        """
        res = subprocess.run(
            [sys.executable, "-m", "pytest", *NAMED_TESTS,
             "-p", "no:cacheprovider", "-q"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=90)

        self.assertEqual(res.returncode, 0,
                         f"{res.stdout}\n{res.stderr}")


if __name__ == "__main__":
    unittest.main()
