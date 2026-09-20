"""Приёмочные тесты AC-6, AC-7, AC-8 (tasks/01M2XJKV84SQ9VEVR0VNVKDNGJ/
SPEC.md): предполётная сверка модели роли с версией CLI — именованный
отказ шага до запуска агента, остановка цикла `auto` с подсказкой,
одно предупреждение на шаг для модели вне таблицы.

Красен до реализации: предполётной проверки модели нет вовсе (шаг
читает `roles.model` в `runner._refuse_before_start` и идёт запускать
агента), а `stack.MODEL_MIN_CLI_VERSION`, от которой тесты берут
минимальную версию, ещё не существует — обращение к ней падает
`AttributeError`.

Установленная версия CLI задаётся ответом подпроцесса `claude
--version` (см. «ГРАНИЦА УПРАВЛЕНИЯ ВЕРСИЕЙ CLI» в `_sandbox.py`), а
заниженность считается от самой таблицы, не от сегодняшнего числа:
`(минимум[0], минимум[1], минимум[2] - 1)` остаётся ниже минимума и
после того, как Оператор поправит запись таблицы.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (INCIDENT_MODEL, NOT_IN_TABLE_WARNING,  # noqa: E402
                      REFUSAL_PREFIX, StepRunSandbox, UNKNOWN_MODEL,
                      UPGRADE_HINT, expected_flags, version_text)
from orchestrator import config, stack  # noqa: E402


class ModelBelowCliMinimumTest(StepRunSandbox):
    """Модель роли есть в таблице, установленный CLI её не тянет."""

    def setUp(self):
        super().setUp()
        self.minimum = stack.MODEL_MIN_CLI_VERSION[INCIDENT_MODEL]
        self.installed = (self.minimum[0], self.minimum[1],
                          self.minimum[2] - 1)
        self.set_model(INCIDENT_MODEL)
        self.set_cli_version(version_text(self.installed))

    def test_ac6_step_refuses_before_the_agent_without_retries_or_escalation(self):
        """Шаг не запускает агента ни разу, журнал называет модель и обе
        версии, попыток и эскалации нет.

        Ловит мутацию: сверка поставлена ПОСЛЕ старта агента (или отказ
        оформлен обычным провалом попытки) — агент стартует, шаг крутит
        `config.AGENT_ATTEMPTS` попыток и уводит задачу в `escalated`.
        """
        self.run_step()

        self.spawn.assert_not_called()
        named = self.entries_containing(REFUSAL_PREFIX)
        self.assertEqual(len(named), 1, self.journal_rows())
        self.assertIn(f"{REFUSAL_PREFIX}: {INCIDENT_MODEL}", named[0])
        self.assertIn(f"требует claude ≥ {version_text(self.minimum)}", named[0])
        self.assertIn(f"установлен {version_text(self.installed)}", named[0])
        self.assertEqual(self.journal_details("agent run retry"), [])
        self.assertEqual(self.pauses, [])
        self.assertNotEqual(self.state(), "escalated")

    def test_ac7_auto_stops_on_the_refusal_and_prints_the_upgrade_hint(self):
        """Тот же отказ останавливает цикл `auto` на первой же попытке, и
        в выводе цикла есть подсказка «обнови CLI либо смени model роли в
        roles.yaml».

        Ловит мутацию: отказ оформлен так, что `auto` его не замечает
        (`return` вместо `sys.exit`) — цикл крутит шаги до потолка; либо
        подсказка потеряна и Оператор видит голое «модель не
        поддерживается» без указания, что делать.
        """
        out = self.run_auto()

        self.spawn.assert_not_called()
        self.assertIn(UPGRADE_HINT, out)
        self.assertEqual(len(self.entries_containing(REFUSAL_PREFIX)), 1,
                         "отказ повторён — цикл пошёл на второй круг")
        self.assertNotIn(f"лимит {config.AUTO_MAX_STEPS} шагов исчерпан", out)


class ModelOutsideTheTableTest(StepRunSandbox):
    """Модель роли в таблице отсутствует: предупреждение, не отказ."""

    def setUp(self):
        super().setUp()
        self.set_min_versions({INCIDENT_MODEL: (2, 1, 251)})
        self.set_model(UNKNOWN_MODEL)
        self.set_cli_version("2.1.267")

    def test_ac8_unknown_model_warns_once_and_the_step_runs_as_before(self):
        """Ровно одна запись предупреждения на шаг, агент запускается,
        argv прежний.

        Ловит мутацию: модель вне таблицы отказывает шагу (fail-closed),
        либо предупреждение пишется на каждую попытку/дважды за шаг, либо
        предупреждение молчит вовсе и Оператор не узнаёт, что модель не
        сверена ни с чем.
        """
        self.run_step()

        self.assertEqual(self.spawn.call_count, 1)
        warnings = self.entries_containing(NOT_IN_TABLE_WARNING)
        self.assertEqual(len(warnings), 1, self.journal_rows())
        self.assertEqual(self.entries_containing(REFUSAL_PREFIX), [])
        self.assertEqual(self.argv()[1:],
                         expected_flags() + ["--model", UNKNOWN_MODEL])
        self.assertNotEqual(self.state(), "escalated")


if __name__ == "__main__":
    unittest.main()
