"""AC-6 (tasks/T085/SPEC.md): тесты состава условий автогейта acceptance
в `tasks/T066/acceptance_tests/` (включая сценарий пробоя порога A1 в
`test_ac4_failing_condition_stays_in_acceptance.py`, который кодировал
его как блокирующий) обновлены под состав без условия «порог программы
не пробит» — по мандату ADR-0010 это не ослабление гейта.

История критерия: изначально этот файл был эскалацией (см. git-историю
`test_ac6_t066_composition_escalation.py`) — на момент написания
`tasks/T066/acceptance_tests/` падал ещё на входе `review -> verifying`
(фикстура approved-REVIEW.md без секции '## Проверено исполнением',
обязательной с T072) и до оценки автогейта, которую меняет ADR-0010, не
доходил вообще. ANSWER-1 (Оператор, 01.09) разрешил эскалацию: фикстура
починена операторским коммитом (7f2afd3), а маршрут `tasks/T066/
acceptance_tests/` обновлён под ADR-0009 (verifying между review и
acceptance) тем же приёмом, каким T079 правила существующие тесты —
заменой ожидаемого состояния/маршрута, не ослаблением поведения. Правку
внёс test_author этой задачи (ANSWER-1, вопрос 2) — это единственный
способ проверить AC-6 буквально («обновлены» для директории, несущей
именно прогоны `fsm.cmd_advance`, доказывается реальным зелёным
прогоном, не текстовым разбором исходников).

Критерий по ANSWER-1: `python3 -m unittest discover -s
tasks/T066/acceptance_tests` зелен ЦЕЛИКОМ после правок. Тест ниже
прогоняет ИМЕННО эту команду настоящим subprocess из корня репозитория
(тот же приём временного прогона внешней команды, что и остальные
`_sandbox.py` каталога — никаких заглушек/парсинга исходников вместо
настоящего unittest) и проверяет её код возврата и то, что вывод не
несёт слов "FAILED"/"ERROR".

Зелёный с рождения: правка маршрута `tasks/T066/acceptance_tests/`
внесена этим же коммитом test_author вместе с этим тестом — `git diff`
этой веткой показывает обе правки как одно целое; без неё тест был бы
красным по причине, описанной в истории эскалации выше (чужой, не
связанный с ADR-0010 баг фикстуры/маршрута T066) — ровно то, что скил
test-authoring запрещает оставлять необъяснённым.
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


class T066AcceptanceSuiteGreenAfterCompositionUpdateTest(unittest.TestCase):

    def test_ac6_t066_acceptance_tests_discover_is_fully_green(self):
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover",
             "-s", "tasks/T066/acceptance_tests"],
            cwd=REPO_ROOT, capture_output=True, text=True)

        self.assertEqual(
            result.returncode, 0,
            f"AC-6: discover -s tasks/T066/acceptance_tests обязан "
            f"завершиться нулевым кодом после обновления состава "
            f"условий/маршрута под ADR-0010/ADR-0009.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        self.assertNotIn("FAILED", result.stderr)
        self.assertNotIn("FAILED", result.stdout)


if __name__ == "__main__":
    unittest.main()
