"""AC-7, AC-11 — 01M3FQ2Z2PY0E9T5F5WQ207NP5: бейзлайн ключуется парой
(шаблон, набор), отклонение считается против бейзлайна своего набора.

Источник — SPEC.md, «Критерии приёмки»:

AC-7. Бейзлайн ключуется парой (имя шаблона, имя набора): первый штатный
прогон набора заводит его бейзлайн с пометкой «бейзлайн создан»; прогон
набора A по тому же шаблону не читает и не перезаписывает бейзлайн
набора B.

AC-11. Отклонение считается против бейзлайна того же набора: метрика в
пределах `CANARY_DEVIATION_RATIO` от бейзлайна СВОЕГО набора не поднимает
ни предупреждения, ни алерта, даже если она вне порога бейзлайна другого
набора по тому же шаблону; превышение порога своего набора — поднимает.

Прогоны настоящие (эфемерный клон, запись прогона, сверка с бейзлайном),
синтетическое в них одно — вождение задачи вместо шагов ролей
(`_util.CanarySetSandbox.run_canary`): живой CLI провайдера не зовётся ни
разу, а исход прогона — тот же штатный kill на `merge_gate`, на котором
бейзлайн и заводится.

Пороговые значения стоимости считаются ОТ `config.CANARY_DEVIATION_RATIO`,
а не литералами: порог — крутилка Оператора, и его поворот не должен
красить планку.

Имя колонки набора планка не угадывает: это единственная колонка
`canary_baseline`, которой не было до задачи (`_util.new_columns`).

Красен до реализации: `canary.cmd_canary` не знает параметра набора, а
бейзлайн ключуется одним `title` — прогон второго набора перезаписал бы
бейзлайн первого.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import config, store  # noqa: E402


class BaselinePerSetTest(_util.CanarySetSandbox):

    def _baselines(self):
        return self.conn.execute("SELECT * FROM canary_baseline").fetchall()

    def _set_columns(self):
        columns = _util.new_columns(self.conn, "canary_baseline",
                                    _util.BASELINE_COLUMNS_BEFORE)
        self.assertTrue(
            columns,
            "у canary_baseline нет ни одной новой колонки — бейзлайн "
            "по-прежнему ключуется одним именем шаблона")
        return columns

    def _baseline_of(self, set_name):
        columns = self._set_columns()
        rows = [row for row in self._baselines()
                if any(row[column] == set_name for column in columns)]
        self.assertEqual(1, len(rows),
                         f"бейзлайн набора {set_name}: строк {len(rows)} "
                         f"({[_util.row_values(r) for r in self._baselines()]})")
        return rows[0]

    def _threshold_alerts(self):
        return len(store.open_alerts(self.conn, "threshold"))

    def test_ac7_first_run_of_a_set_creates_its_own_baseline(self):
        """Первый штатный прогон набора печатает «бейзлайн создан» и
        заводит строку бейзлайна на пару (шаблон, набор).

        Ловит мутацию: бейзлайн заводится по-прежнему одним `title` — имя
        набора в строку не попадает, и прогон следующего набора по тому же
        шаблону нашёл бы «свой» бейзлайн уже заведённым.
        """
        out = self.run_canary(set_name=_util.SET_NAME, spent=1.0, steps=3)

        self.assertIn("бейзлайн создан", out)
        row = self._baseline_of(_util.SET_NAME)
        self.assertEqual(_util.POOL_TEMPLATE_TITLE, row["title"])
        self.assertEqual(3, row["steps"])
        self.assertEqual(1.0, row["cost_usd"])

    def test_ac7_run_of_another_set_neither_reads_nor_rewrites_the_first(self):
        """Прогон набора B по тому же шаблону заводит СВОЙ бейзлайн
        («бейзлайн создан», без сверки с бейзлайном A), а бейзлайн A
        остаётся с прежними значениями.

        Ловит мутацию: бейзлайн читается/пишется по одному `title` (имя
        набора добавлено в строку, но не в ключ поиска) — прогон набора B
        сравнился бы с бейзлайном A и поднял бы отклонение сверх порога на
        ровно ожидаемой разнице моделей, а затем затёр бы его своими
        значениями.
        """
        self.run_canary(set_name=_util.SET_NAME, spent=1.0, steps=3)

        out = self.run_canary(set_name=_util.OTHER_SET_NAME, spent=7.0, steps=9)

        self.assertIn("бейзлайн создан", out)
        self.assertNotIn("ВНИМАНИЕ", out)
        first = self._baseline_of(_util.SET_NAME)
        self.assertEqual((3, 1.0), (first["steps"], first["cost_usd"]),
                         "бейзлайн первого набора перезаписан прогоном второго")
        second = self._baseline_of(_util.OTHER_SET_NAME)
        self.assertEqual((9, 7.0), (second["steps"], second["cost_usd"]))

    def test_ac11_metric_within_its_own_baseline_raises_nothing(self):
        """Метрика в пределах порога от бейзлайна СВОЕГО набора не даёт ни
        предупреждения в выводе, ни алерта — при том что от бейзлайна
        другого набора по тому же шаблону она за порогом.

        Ловит мутацию: сверка с бейзлайном идёт по шаблону без учёта
        набора (или берёт «первый бейзлайн этого шаблона») — исправный
        прогон Codex-набора поднимал бы алерт отклонения на каждом
        прогоне, а именно этот алерт и есть вход гейта сдвига пина.
        """
        ratio = config.CANARY_DEVIATION_RATIO
        # Порядок важен: бейзлайн ЧУЖОГО набора заводится ПЕРВЫМ — иначе
        # сверка «по шаблону без учёта набора» нашла бы свой же бейзлайн
        # первым и мутация осталась бы невидимой.
        self.run_canary(set_name=_util.OTHER_SET_NAME,
                        spent=1.0 * (1 + ratio * 4), steps=3)
        self.run_canary(set_name=_util.SET_NAME, spent=1.0, steps=3)
        alerts_before = self._threshold_alerts()

        out = self.run_canary(set_name=_util.SET_NAME,
                              spent=1.0 * (1 + ratio / 2), steps=3)

        self.assertNotIn("ВНИМАНИЕ", out)
        self.assertNotIn("отклонение", out)
        self.assertEqual(alerts_before, self._threshold_alerts(),
                         "поднят алерт отклонения на метрике в пределах "
                         "порога своего набора")

    def test_ac11_metric_beyond_its_own_baseline_raises_the_deviation(self):
        """Метрика сверх порога от бейзлайна своего набора поднимает и
        предупреждение в выводе, и алерт.

        Ловит мутацию: сверка с бейзлайном набора выключена вовсе («набор
        всегда сравнивается сам с собой, значит сравнивать нечего») —
        регрессия конвейера на Codex-наборе прошла бы молча, и канарейка
        перестала бы быть сигналом для этого набора.
        """
        ratio = config.CANARY_DEVIATION_RATIO
        self.run_canary(set_name=_util.SET_NAME, spent=1.0, steps=3)
        alerts_before = self._threshold_alerts()

        out = self.run_canary(set_name=_util.SET_NAME,
                              spent=1.0 * (1 + ratio * 2), steps=3)

        self.assertIn("отклонение", out)
        self.assertGreater(self._threshold_alerts(), alerts_before)


if __name__ == "__main__":
    unittest.main()
