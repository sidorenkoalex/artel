"""AC-3 (tasks/T095/SPEC.md): `artel report` показывает блок с метрикой
трения — значения по последним задачам и тренд.

Разметку SPEC не фиксирует (см. `_sandbox.py`) — «трение» проверяется
как буквальное слово (это имя метрики во всём SPEC/ТЗ, «Метрика
«трение»» — не абстрактная формулировка требования, а собственное имя,
которое естественно ожидать в заголовке блока), «по последним задачам»
— как присутствие данных НЕСКОЛЬКИХ разных задач внутри найденного
блока, «тренд» — как то же буквальное слово (второе собственное имя
раздела рядом с «трение» в тексте требования 3 SPEC).

Допущение об источнике данных (файлы `.artel/logs/...`, доступные к
моменту генерации) — см. докстринг `test_ac2_aggregation_task_and_corpus.py`.

Красен до реализации: `orchestrator.report` не несёт метрику трения.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (FrictionSandboxTest, bash_call, edit_call,  # noqa: E402
                      friction_section, read_call)


class ReportFrictionBlockTest(FrictionSandboxTest):

    def setUp(self):
        super().setUp()
        self.mk_task("T001", "Первая задача-фикстура")
        self.write_log("T001", "developer", 1, [
            read_call("t1", "a.py"),
            read_call("t2", "b.py"),
            bash_call("t3", "pytest tests/"),
            edit_call("t4", "c.py"),
        ])
        self.mk_task("T002", "Вторая задача-фикстура")
        self.write_log("T002", "developer", 1, [
            read_call("t1", "z.py"),
            read_call("t2", "z.py"),
            bash_call("t3", "pytest tests/"),
            edit_call("t4", "c.py"),
        ])
        self.html = self.run_report_html()
        self.block = friction_section(self.html)

    def test_ac3_report_has_a_friction_block(self):
        self.assertNotEqual(
            self.block, "",
            "в сгенерированном отчёте нет блока со словом «трение» — "
            "метрика не отображается")

    def test_ac3_block_shows_values_for_more_than_one_recent_task(self):
        self.assertIn("T001", self.block,
                      "T001 не упомянута внутри блока трения")
        self.assertIn("T002", self.block,
                      "T002 не упомянута внутри блока трения — блок "
                      "показывает не «по последним задачам», а одну "
                      "задачу")

    def test_ac3_block_mentions_a_trend(self):
        self.assertIn(
            "тренд", self.block.lower(),
            "в блоке трения не найдено слово «тренд» — SPEC требование "
            "3 явно называет его отдельно от значений по задачам")


if __name__ == "__main__":
    unittest.main()
