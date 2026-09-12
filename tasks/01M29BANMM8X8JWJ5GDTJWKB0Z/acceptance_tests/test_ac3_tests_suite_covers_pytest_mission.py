"""AC-3 (SPEC 01M29BANMM8X8JWJ5GDTJWKB0Z) — требование 4: основной набор
`tests/` (не только эта планка `tasks/<id>/acceptance_tests/`) несёт
СВОЙ регрессионный тест на форму pytest-команды пункта 5 миссии
test_author, читающий значение таймаута из `stack.PER_TEST_TIMEOUT_SEC`,
а не из литерала 120 — тем же приёмом, каким прошлые задачи заводили
`DeveloperSuiteCoversWorkersAndXdistTest`
(`tasks/01M291M2Z76M84GVP25J387A66/acceptance_tests/
test_full_suite_workers_and_xdist.py`, AC-7): сканируем ИСХОДНЫЙ ТЕКСТ
файлов `tests/test_*.py` на упоминание `mission_brief_package`/
`test_author` вместе с нужными подстроками, не исполняем их — планка
этой задачи это делает статически, прогон самого найденного теста уже
не её забота (его гоняет CI/акцептанс).

Красен до реализации: сегодня НИ ОДИН файл `tests/test_*.py` не
упоминает `mission_brief_package` вместе с `test_author` и разом всеми
нужными подстроками (grep по `tests/` подтверждает — `mission_brief_
package` встречается только в `orchestrator/role_prompt.py` и
`orchestrator/runner.py`, не в `tests/`) — `assertTrue(candidates, ...)`
падает первым же тестом.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402

REQUIRED_MARKERS = ("-m pytest", "-p timeout", "timeout=",
                    "PER_TEST_TIMEOUT_SEC", "unittest discover")


def _candidate_files():
    tests_root = Path(config.ROOT) / "tests"
    out = []
    for path in sorted(tests_root.glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if "mission_brief_package" in text and "test_author" in text:
            out.append((path, text))
    return out


class MainSuiteCoversTestAuthorPytestMissionTest(unittest.TestCase):

    def test_ac3_a_tests_file_asserts_the_mission_pytest_command_dynamically(self):
        """Среди файлов `tests/test_*.py`, которые вообще собирают миссию
        test_author (`mission_brief_package` + слово `test_author` в
        одном файле), есть хотя бы один, чей исходный текст несёт разом
        подстроки `-m pytest`, `-p timeout`, `timeout=` и
        `PER_TEST_TIMEOUT_SEC` (проверка читает значение таймаута из
        константы, не из литерала 120) и `unittest discover` (проверка
        удостоверяется, что старой команды в миссии больше нет).

        Ловит мутацию: разработчик меняет саму миссию (AC-1), но не
        заводит по этому свойству отдельный тест в основном наборе
        `tests/` — после мержа регрессию (например, случайный откат на
        `unittest discover` при рефакторинге) больше никто не ловит,
        только планка этой одноразовой задачи, которая после мержа
        никем не гоняется.
        """
        candidates = _candidate_files()
        self.assertTrue(
            candidates,
            "нет файла в tests/, несущего мисию test_author "
            "(mission_brief_package + 'test_author' в одном файле)")
        covered = [path for path, text in candidates
                  if all(marker in text for marker in REQUIRED_MARKERS)]
        self.assertTrue(
            covered,
            "ни один файл tests/, несущий mission_brief_package для "
            f"test_author, не проверяет разом все подстроки {REQUIRED_MARKERS}: "
            f"{[str(p) for p, _ in candidates]}")


if __name__ == "__main__":
    unittest.main()
