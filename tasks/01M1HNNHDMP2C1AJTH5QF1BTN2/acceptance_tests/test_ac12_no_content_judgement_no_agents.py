"""AC-12 (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md): «Команда не
оценивает существо правки по содержанию и не запускает агентов.»

Красен до реализации: `_sandbox.discover_amend_command_name()` падает
`AssertionError` — новой команды правки планки в таблице диспетчера ещё
нет.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import runner  # noqa: E402

from _sandbox import AmendSandbox  # noqa: E402

# Правка, которая содержательно ОСЛАБЛЯЕТ покрытие AC-1 (было два
# метода — стало снова один): проверка неослабления по существу — зона
# ревьювера по чек-листу (ADR-0012 п.4, SPEC «Не входит»), не этой
# команды; команда обязана принять такую правку технически (коммит,
# лок), раз прогон формально «OK» и путь/основание/лок в порядке.
WEAKENED_CONTENT = '''"""Красен до реализации: фикстура — правка, которая
содержательно ослабляет тест (убирает вторую проверку), но остаётся
формально «OK»."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)  # раньше было ещё и assertEqual(1+1, 2)


# AC-2: manual — Оператор проверяет глазами на приёмке
'''


class NoContentJudgementNoAgentsTest(AmendSandbox):

    def test_ac12_command_does_not_spawn_agents(self):
        """Вызов команды на валидной успешной правке не порождает ни
        одного агентного процесса — `runner.spawn_agent`, единственная
        точка запуска `claude` в кодовой базе, не должна быть вызвана ни
        разу.

        Ловит мутацию: команда по ошибке заведена через тот же путь, что
        роли (`runner.run_agent_once`/`spawn_agent`) — например, чтобы
        «попросить» модель проверить правку.
        """
        self.enter_in_dev()
        self.write_acceptance_tests(WEAKENED_CONTENT)

        with mock.patch.object(runner, "spawn_agent") as spawn:
            self.run_amend(reason="ослабляющая правка, агентов быть не должно")

        spawn.assert_not_called()

    def test_ac12_content_weakening_amend_is_accepted_without_judgement(self):
        """Правка, которая по существу ОСЛАБЛЯЕТ тест (убирает одну из
        двух проверок), но остаётся формально «OK», технически ПРИНИМАЕТСЯ
        командой — команда не читает семантику диффа, только запускает
        прогон и проверяет области/основание/лок (AC-1..AC-11); оценка
        существа — зона ревьювера (ADR-0012 п.4).

        Ловит мутацию: команда пытается эвристически detектить
        «ослабление» (например, по числу тестовых методов до/после) и
        отказывает — тогда легитимные технические правки (переименование,
        рефакторинг тела теста без потери проверок) тоже стали бы
        заложниками эвристики, которой в SPEC нет.
        """
        locked = self.enter_in_dev()
        self.write_acceptance_tests(WEAKENED_CONTENT)

        self.run_amend(reason="ослабляющая правка, команда её не оценивает")

        new_locked = self.row()["tests_locked_sha"]
        self.assertNotEqual(
            new_locked, locked,
            "формально валидная (прогон OK) правка обязана пройти "
            "технически, даже если содержательно ослабляет тест")


if __name__ == "__main__":
    unittest.main()
