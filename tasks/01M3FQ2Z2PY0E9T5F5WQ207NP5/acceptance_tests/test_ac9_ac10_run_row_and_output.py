"""AC-9, AC-10 — 01M3FQ2Z2PY0E9T5F5WQ207NP5: строка прогона и вывод
`canary` называют набор и модели ролей.

Источник — SPEC.md, «Критерии приёмки»:

AC-9. Строка `canary_runs` прогона несёт имя набора и сводку «роль →
модель», по которой прогон шёл.

AC-10. Вывод `canary` по прогону и строка журнала называют имя набора и
модели ролей набора.

Имена колонок планка не угадывает: и имя набора, и сводка ищутся среди
колонок `canary_runs`, которых не было до задачи (`_util.new_columns`) —
по значению, а не по названию.

Прогон настоящий, синтетическое в нём одно — вождение задачи вместо шагов
ролей (`_util.CanarySetSandbox.run_canary`): живой CLI провайдера не
зовётся.

Красен до реализации: у `canary.cmd_canary` нет параметра набора, в
`canary_runs` нет ни имени набора, ни сводки моделей, а вывод прогона о
наборе не говорит.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402


class RunRowAndOutputTest(_util.CanarySetSandbox):

    def _run_row(self):
        rows = self.conn.execute("SELECT * FROM canary_runs").fetchall()
        self.assertEqual(1, len(rows), "строк прогона в журнале не одна")
        return rows[0]

    def _new_values(self, row):
        columns = _util.new_columns(self.conn, "canary_runs",
                                    _util.RUN_COLUMNS_BEFORE)
        self.assertTrue(columns,
                        "у canary_runs нет ни одной новой колонки — ни имени "
                        "набора, ни сводки моделей строка прогона не несёт")
        return {column: row[column] for column in columns}

    def test_ac9_run_row_carries_the_set_name(self):
        """Строка `canary_runs` прогона несёт имя набора, которым прогон
        шёл.

        Ловит мутацию: имя набора доезжает до сборки слоя клона, но в
        строку прогона не пишется — журнал прогонов перестал бы различать
        наборы, и метрики Codex-прогона были бы неотличимы от метрик
        прогона «как пульт» при разборе истории.
        """
        self.run_canary(set_name=_util.SET_NAME, spent=2.0, steps=3)

        values = self._new_values(self._run_row())

        self.assertIn(_util.SET_NAME, list(values.values()),
                      f"новые колонки строки прогона: {values}")

    def test_ac9_run_row_carries_the_role_to_model_summary(self):
        """Строка `canary_runs` несёт сводку «роль → модель»: в одном
        значении названы и роль набора, и её модель.

        Ловит мутацию: в строку пишется только имя набора — по журналу
        нельзя было бы сказать, какие модели за ним стояли В ТОТ прогон, а
        локальный слой пульта к тому времени уже переписан (сам набор —
        файл вне git, его правка следа не оставляет).
        """
        self.run_canary(set_name=_util.SET_NAME, spent=2.0, steps=3)

        values = self._new_values(self._run_row())

        summaries = [str(value) for value in values.values()
                     if value is not None
                     and _util.SET_MODEL in str(value)
                     and "developer" in str(value)]
        self.assertTrue(summaries,
                        "ни одна новая колонка не называет пару «роль → "
                        f"модель»: {values}")

    def test_ac10_output_names_the_set_and_the_models(self):
        """Вывод `canary` по прогону называет имя набора и модель его
        ролей.

        Ловит мутацию: печать итога прогона оставлена прежней — Оператор,
        глядя в вывод, не отличал бы прогон Codex-набора от прогона «как
        пульт», а именно по этому выводу он решает, считать ли прогон
        зелёной канарейкой для сдвига пина.
        """
        out = self.run_canary(set_name=_util.SET_NAME, spent=2.0, steps=3)

        self.assertIn(_util.SET_NAME, out)
        self.assertIn(_util.SET_MODEL, out)


if __name__ == "__main__":
    unittest.main()
