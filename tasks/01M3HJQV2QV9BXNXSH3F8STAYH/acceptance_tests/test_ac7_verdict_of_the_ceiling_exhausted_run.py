"""AC-7 — 01M3HJQV2QV9BXNXSH3F8STAYH: вердикт прогона, снятого исчерпанием
потолка, не зелёный и отличается от вердикта несошедшейся задачи.

Источник — SPEC.md, «Критерии приёмки»:

AC-7. Вердикт строки `canary_runs` такого прогона не равен `green` и
отличается от вердикта прогона, снятого как «задача не сходится»;
`store.green_canary_runs` эту строку не возвращает,
`canary.merges_since_last_green_run` её не считает, а модуль
`orchestrator/pin.py` не изменён.

Два прогона в одной БД: режим `exhaust` (исчерпан поднятый потолок) и режим
`stall` (прежняя стагнация, исход «не сошлась»). Оба пишут строку
`canary_runs` настоящим `canary._record_canary_run` — сравниваются именно
те значения, по которым гейт сдвига пина отличает прогоны.

«`orchestrator/pin.py` не изменён» — дословное сравнение с общим предком
ветки и main (`_util.main_source`): условие ADR-0013 не ослабляется даже
тем изменением, которое кажется безобидным.

Красен до реализации: исхода «исчерпан потолок задачи» нет, и оба сценария
дают сегодня один и тот же вердикт `red` — диагноз «шаблон не уложился в
потолок» и диагноз «конвейер не сошёлся» по строке `canary_runs` неразличимы.
Три остальных утверждения этого файла (зелёные прогоны, возраст зелёного
прогона, неизменность `orchestrator/pin.py`) на сегодняшнем коде выполняются
и остаются регрессионными: они краснеют ровно тогда, когда новый вердикт
заводится ослаблением входа гейта сдвига пина.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import canary, store  # noqa: E402

PIN_MODULE = "orchestrator/pin.py"


class CeilingExhaustedVerdictTest(_util.ClonelessRunSandbox):

    def setUp(self):
        super().setUp()
        self.run_one_task(mode="exhaust")
        self.exhausted_task = self.task_id
        self.exhausted = self.run_row(_util.POOL_TITLES[0])
        self.run_one_task(mode="stall")
        self.inconclusive = self.run_row(_util.POOL_TITLES[1])

    def test_ac7_verdict_is_not_green_and_differs_from_the_inconclusive_one(self):
        """Вердикт строки прогона, снятого исчерпанием потолка, не `green` и
        не равен вердикту прогона, снятого как «не сошлась».

        Ловит мутацию: новый исход оставлен на прежней формуле вердикта
        («штатный исход без расхождения — green, иначе red») — по журналу
        прогонов нельзя было бы отличить «шаблон не уложился в потолок» от
        «конвейер не сошёлся», то есть красный вердикт снова обвинял бы код.
        """
        self.assertNotEqual("green", self.exhausted["verdict"])
        self.assertNotEqual(
            self.inconclusive["verdict"], self.exhausted["verdict"],
            "вердикт исчерпанного потолка совпал с вердиктом несошедшейся "
            f"задачи: {self.exhausted['verdict']!r}")

    def test_ac7_green_canary_runs_does_not_return_the_row(self):
        """`store.green_canary_runs` эту строку не возвращает.

        Ловит мутацию: новый вердикт заведён, но выборка зелёных прогонов
        отбирает «всё, кроме red» — прогон, у которого задача не уложилась в
        потолок, стал бы зелёной канарейкой и разрешил бы сдвиг пина.
        """
        green = store.green_canary_runs(self.conn)

        self.assertNotIn(self.exhausted["id"], [row["id"] for row in green],
                         "строка исчерпанного потолка попала в зелёные прогоны")
        self.assertNotIn(self.inconclusive["id"], [row["id"] for row in green])

    def test_ac7_merges_since_last_green_run_does_not_count_the_row(self):
        """`canary.merges_since_last_green_run` на целевом sha этих прогонов
        отвечает «сравнивать не с чем».

        Ловит мутацию: возраст зелёного прогона считается по всем строкам
        `canary_runs` целевого sha, а не только по зелёным — гейт
        `pin-update` получил бы возраст 0 и пустил бы сдвиг пина по прогону,
        который зелёным не был.
        """
        self.assertIsNone(
            canary.merges_since_last_green_run(self.conn, self.head))

    def test_ac7_pin_module_is_not_changed(self):
        """`orchestrator/pin.py` в ветке дословно совпадает с версией общего
        предка ветки и main.

        Ловит мутацию: условие сдвига пина «подправлено» под новый вердикт
        (например, гейт начинает принимать прогон с исчерпанным потолком) —
        это ослабление условия ADR-0013, прямо запрещённое разделом «Не
        входит» SPEC.
        """
        local = (_util.REPO_ROOT / PIN_MODULE).read_text(encoding="utf-8")

        self.assertEqual(_util.main_source(PIN_MODULE), local,
                         f"{PIN_MODULE} изменён в ветке задачи")


if __name__ == "__main__":
    unittest.main()
