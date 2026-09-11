"""Приёмочный тест AC-8 задачи 01M290PP4KBTG1KYS1PWKQJH6T — отказ
предварительного advance класса «роль ещё не закончила» (тексты
`auto._pre_advance_step`: «переход отклонён: замечания ревью не
отработаны» и «переход отклонён: дерево не на ветке задачи») не
печатается классом `refusals` дозора; отказ ДРУГОГО текста (тот же
`REFUSAL_ACTION_PREFIX`, но не из `_pre_advance_step`) по-прежнему
печатается.

Красен до реализации: `orchestrator/watch.py::_matches_class` сегодня
считает классом `refusals` ЛЮБУЮ запись с префиксом `"переход
отклонён"` без исключений — обе строки `auto._pre_advance_step`
появились бы в потоке наравне с прочими отказами, `assertNotIn` по их
маркерам покраснеет.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import WatchTestCase  # noqa: E402


class PreAdvanceRefusalsExcludedTest(WatchTestCase):

    def test_ac8_pre_advance_role_not_finished_texts_are_not_printed_as_refusals(self):
        """Две записи ровно теми текстами, что производит
        `auto._pre_advance_step` (см. `orchestrator/auto.py`,
        `REWORK_REFUSAL_ACTION` и литерал «дерево не на ветке задачи»),
        не попадают в поток при `--events refusals`; третья запись —
        отказ ДРУГОГО текста (тот же префикс `REFUSAL_ACTION_PREFIX`) —
        по-прежнему печатается, доказывая, что фильтр не выключил класс
        `refusals` целиком.

        Ловит мутацию: фильтр сравнивает ТОЛЬКО префикс
        `REFUSAL_ACTION_PREFIX` без учёта конкретного текста
        `_pre_advance_step` (то есть вырезает класс `refusals` целиком)
        — третий маркер (отказ другого класса) тоже не появится, и
        финальный `assertIn` по нему покраснеет; либо фильтр не введён
        вовсе — первые два маркера появятся, `assertNotIn` покраснеет.
        """
        conn = store.db()
        self._insert_task("T801")

        self._start(["--tasks", "T801", "--events", "refusals",
                    "--interval", "1"])
        self._settle()

        store.journal(
            conn, "T801", "fsm",
            "переход отклонён: замечания ревью не отработаны",
            "маркер-rework-скрыт")
        store.journal(
            conn, "T801", "fsm",
            "переход отклонён: дерево не на ветке задачи",
            "маркер-tree-missing-скрыт")
        store.journal(
            conn, "T801", "fsm",
            f"{store.REFUSAL_ACTION_PREFIX}: другая причина",
            "маркер-другой-отказ-виден")

        self._wait_until(
            lambda: "маркер-другой-отказ-виден" in self._stream.getvalue())

        out = self._stream.getvalue()
        self.assertNotIn("маркер-rework-скрыт", out)
        self.assertNotIn("маркер-tree-missing-скрыт", out)

        self._set_state("T801", "killed", "in_dev")
        self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


if __name__ == "__main__":
    unittest.main()
