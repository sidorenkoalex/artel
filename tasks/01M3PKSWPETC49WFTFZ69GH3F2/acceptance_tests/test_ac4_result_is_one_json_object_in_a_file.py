"""AC-4 — 01M3PKSWPETC49WFTFZ69GH3F2: результат процесса клона — один
JSON-объект в файле, путь которого передал пульт.

Группа: разовый

Источник — SPEC.md, «Критерии приёмки»:

AC-4. Процесс клона возвращает пульту результат одним JSON-объектом в
файле, путь которого передал пульт; объект несёт id задачи, шаги,
метрики, исход, фактическую эскалацию и HEAD клона.

Имена полей объекта SPEC оставляет PLAN, поэтому планка их не называет и
проверяет содержимое по значениям: посредник запуска (`_clone_drive.py`)
находит файл результата среди путей, которые пульт передал процессу
(аргументы или окружение), и снимает его копию сразу после завершения
процесса. «Фактическая эскалация» различается сравнением двух прогонов —
без эскалации и с одной эскалацией: в объекте обязано найтись поле
(один и тот же путь ключей), ложное/нулевое в первом и истинное/ненулевое
во втором.

Красен до реализации: процесс клона не запускается вовсе (ведение в
процессе пульта упирается в растяжку песочницы) — файла результата нет.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _clone_drive  # noqa: E402


def _leaves(obj, path=()) -> dict:
    """Путь ключей -> скалярное значение (индексы списков не входят в путь)."""
    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            out.update(_leaves(value, path + (str(key),)))
        return out
    if isinstance(obj, list):
        return {}
    return {path: obj}


class ResultJsonObjectTest(_clone_drive.CloneDriveSandbox):

    def _one_result(self) -> dict:
        found = self.results()
        self.assertEqual(
            len(found), 1,
            f"ожидался ровно один файл результата с JSON-объектом среди путей, "
            f"переданных процессу клона, найдено {len(found)} (зерно "
            f"{self.seed}); запуски {self.launches}\n{self.output}")
        data = json.loads(found[0]["text"])
        self.assertIsInstance(data, dict)
        return data

    def test_ac4_result_object_carries_id_steps_metrics_outcome_head(self):
        """Штатный прогон (роль уводит задачу в merge_gate): файл результата —
        один JSON-объект, в котором есть id задачи из строки `canary_runs`,
        HEAD клона (проверяемый коммит), шаги (запись перехода
        `state -> merge_gate` среди значений), исход `killed` и число шагов
        метрик, совпадающее с записанным пультом в `canary_runs`.

        Ловит мутацию: процесс клона пишет результат не в переданный пультом
        файл (в stdout или по собственному пути — файла среди переданных
        путей нет), пишет несколько JSON-документов подряд (файл не
        разбирается как один объект) либо не кладёт в объект шаги или HEAD
        клона (нет записи перехода либо sha коммита среди значений).
        """
        target = self.commit_code(_clone_drive.SCENARIO_GREEN, self.new_marker("м"))
        self.run_canary(target)
        self.assert_no_crash()
        data = self._one_result()
        values = _clone_drive.json_values(data)
        texts = [str(v) for v in values]
        rows = self.canary_rows()
        self.assertEqual(len(rows), 1, self.output)
        row = rows[0]
        self.assertIn(row["task_id"], texts, f"нет id задачи: {data}")
        self.assertIn(target, texts, f"нет HEAD клона {target}: {data}")
        self.assertTrue(any("state -> merge_gate" in t for t in texts),
                        f"нет шагов (перехода state -> merge_gate): {data}")
        self.assertIn("killed", texts, f"нет исхода killed: {data}")
        self.assertIn(row["steps"], [v for v in values if isinstance(v, int)
                                     and not isinstance(v, bool)],
                      f"нет числа шагов метрик {row['steps']}: {data}")

    def test_ac4_result_object_carries_the_actual_escalation(self):
        """Два прогона, различающиеся только эскалацией: роль сразу уводит
        задачу в merge_gate — либо сперва эскалирует вопросом, а после
        синтетического ANSWER уводит в merge_gate. В объекте результата есть
        поле, ложное/нулевое в первом и истинное/ненулевое во втором, —
        фактическая эскалация.

        Ловит мутацию: процесс клона не передаёт факт эскалации (пульт
        вычислял бы его сам по неполным данным) — ни одно поле объекта не
        различает прогон без эскалации и прогон с ней.
        """
        target = self.commit_code(_clone_drive.SCENARIO_GREEN, self.new_marker("м"))
        self.run_canary(target)
        self.assert_no_crash()
        calm = _leaves(self._one_result())
        for path in self.capture.glob("launch-*.json"):
            path.unlink()
        target = self.commit_code(_clone_drive.SCENARIO_ESCALATED_GREEN,
                                  self.new_marker("м"))
        self.run_canary(target)
        self.assert_no_crash()
        escalated = _leaves(self._one_result())
        flips = [key for key, value in calm.items()
                 if key in escalated and value in (False, 0)
                 and not isinstance(value, float)
                 and escalated[key] not in (False, 0, None, "")]
        self.assertTrue(
            flips,
            f"ни одно поле результата не отличает прогон без эскалации от "
            f"прогона с эскалацией (зерно {self.seed}): {calm} / {escalated}")


if __name__ == "__main__":
    unittest.main()
