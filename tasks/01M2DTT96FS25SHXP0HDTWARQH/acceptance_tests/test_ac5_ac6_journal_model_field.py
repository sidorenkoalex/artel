"""AC-5/AC-6 задачи 01M2DTT96FS25SHXP0HDTWARQH: запись журнала «agent run
started» несёт `model=<идентификатор>` (либо `model=дефолт CLI`, если
поле роли не задано); записи «agent cost KNOWN» и «agent cost PARTIAL»
несут ТОТ ЖЕ `model=`, что и «agent run started» того же шага.

Красен до реализации: ни одна из трёх записей сегодня не несёт `model=`
вовсе — подстрока не найдётся ни при каком сценарии.
"""
import sys
# AC-7: manual — дубль пометки из markers.py (amend-tests читает разметку только из test_*.py)
# AC-8: manual — дубль пометки из markers.py (amend-tests читает разметку только из test_*.py)
# AC-9: manual — дубль пометки из markers.py (amend-tests читает разметку только из test_*.py)
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pipeline import (ModelFlagPipelineTest, assistant_event, result_event,  # noqa: E402
                       timeout_then_killed_proc)

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tests.sandbox import FakeProc  # noqa: E402


class RunStartedModelTest(ModelFlagPipelineTest):

    def test_ac5_run_started_carries_the_configured_model(self):
        """Роль `developer` несёт `model: claude-opus-5` — запись «agent
        run started» этого шага содержит `model=claude-opus-5`.

        Ловит мутацию: запись журнала не несёт `model=` вовсе, либо несёт
        имя роли/скила вместо идентификатора модели.
        """
        self.set_roles_yaml(developer="claude-opus-5")

        self.run_agent("developer")

        details = self.journal_details("agent run started")
        self.assertEqual(len(details), 1)
        self.assertIn("model=claude-opus-5", details[0])

    def test_ac5_run_started_carries_default_cli_marker_when_unset(self):
        """Поле `model` роли `developer` не задано — запись «agent run
        started» несёт `model=дефолт CLI` (не пустую строку и не
        `model=None`).

        Ловит мутацию: при отсутствии поля запись вовсе не несёт `model=`,
        либо несёт `model=None`/`model=`.
        """
        self.set_roles_yaml(developer=None)

        self.run_agent("developer")

        details = self.journal_details("agent run started")
        self.assertEqual(len(details), 1)
        self.assertIn("model=дефолт CLI", details[0])


class CostJournalModelTest(ModelFlagPipelineTest):

    def test_ac6_cost_known_carries_the_same_model_as_run_started(self):
        """Финальное событие потока несёт usage (разбивку по видам) —
        «agent cost KNOWN» журналируется (см. `spend.charge_step`) и
        несёт ТОТ ЖЕ `model=`, что и «agent run started» того же шага.

        Ловит мутацию: «agent cost KNOWN» не несёт `model=` вовсе, либо
        несёт значение, расходящееся с «agent run started» (например,
        модель роли на момент учёта денег читается заново и по-другому,
        а не переносится из того же запуска шага).
        """
        self.set_roles_yaml(reviewer="claude-opus-5")
        proc = FakeProc([result_event(
            usd=0.2, usage={"input_tokens": 10, "output_tokens": 5})])

        self.run_agent("reviewer", proc=proc)

        started = self.journal_details("agent run started")
        known = self.journal_details("agent cost KNOWN")
        self.assertEqual(len(known), 1,
                         "разбивка usage была в финальном событии — запись обязана лечь")
        self.assertIn("model=claude-opus-5", known[0])
        self.assertIn("model=claude-opus-5", started[0])

    def test_ac6_cost_partial_carries_the_same_model_as_run_started(self):
        """Таймаут шага `developer` с usage-событиями в потоке до обрыва —
        курс роли известен (`config.TOKEN_RATES["developer"]`), «agent
        cost PARTIAL» журналируется (см. `spend.charge_missing_result`) и
        несёт ТОТ ЖЕ `model=`, что и «agent run started» того же шага;
        поле `model` не задано — оба несут `model=дефолт CLI`.

        Ловит мутацию: «agent cost PARTIAL» не несёт `model=` вовсе, либо
        несёт значение, отличное от записи «agent run started» того же
        шага.
        """
        self.set_roles_yaml(developer=None)
        proc = timeout_then_killed_proc([
            assistant_event(usage={"input_tokens": 100, "output_tokens": 50}),
        ])

        self.run_agent("developer", proc=proc)

        started = self.journal_details("agent run started")
        partial = self.journal_details("agent cost PARTIAL")
        self.assertEqual(len(partial), 1,
                         "usage-события были, курс роли известен — запись обязана лечь")
        self.assertIn("model=дефолт CLI", partial[0])
        self.assertIn("model=дефолт CLI", started[0])


if __name__ == "__main__":
    unittest.main()
