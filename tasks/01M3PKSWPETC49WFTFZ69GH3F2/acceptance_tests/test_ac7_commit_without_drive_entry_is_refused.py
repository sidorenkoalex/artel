"""AC-7 — 01M3PKSWPETC49WFTFZ69GH3F2: коммит без входа
`orchestrator/canary_drive.py` — именованный отказ без ведения кодом пина.

Группа: разовый

Источник — SPEC.md, «Критерии приёмки»:

AC-7. Проверяемый коммит без входа `orchestrator/canary_drive.py`:
канарейка завершается именованным отказом с текстом, что коммит не умеет
вести учебную задачу своим кодом (ADR-0021, этап 0); учебная задача не
заводится, ведение кодом пина не происходит.

Проверяемый коммит песочницы — без файла входа; пин (HEAD главной копии)
— следующий коммит, в котором вход есть (если он есть в проверяемом коде
вообще): возврат к ведению кодом пина был бы здесь возможен и потому
наблюдаем. Текст отказа сверяется по ссылке «ADR-0021, этап 0», которую
критерий приводит в самом тексте отказа; отказ принимается и как
`SystemExit`, и как напечатанная строка.

Красен до реализации: пульт ведёт учебную задачу сам — `catalog.cmd_new`
процесса пульта зовётся (растяжка песочницы записана), отказа с ссылкой на
ADR-0021 нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _clone_drive  # noqa: E402


class CommitWithoutDriveEntryTest(_clone_drive.CloneDriveSandbox):

    def setUp(self):
        super().setUp()
        self.old = self.commit_code(_clone_drive.SCENARIO_GREEN,
                                    self.new_marker("старый"), drop_drive=True)
        self.pin_mark = self.new_marker("пин")
        self.pin = self.commit_code(_clone_drive.SCENARIO_GREEN, self.pin_mark)
        self.run_canary(self.old)

    def test_ac7_named_refusal_and_no_task_driven(self):
        """Прогон на коммите без входа: вывод (или текст `SystemExit`) несёт
        ссылку «ADR-0021» и «этап 0»; процесс клона не запускался, процесс
        пульта не заводил и не вёл учебную задачу, ни одной строки
        `canary_runs` с вердиктом `green`, метки кода пина в выводе нет.

        Ловит мутацию: отсутствие входа трактуется как повод вести задачу
        кодом пина — молча или с предупреждением (растяжка пульта записана
        либо процесс клона запущен из кода пина, в выводе метка пина) — либо
        отказ не именован (нет ссылки на ADR-0021, этап 0).
        """
        self.assert_no_crash()
        self.assertIn("ADR-0021", self.output,
                      f"отказ не именован (зерно {self.seed}):\n{self.output}")
        self.assertIn("этап 0", self.output)
        self.assert_no_pult_drive()
        self.assertEqual(self.launches, [],
                         f"процесс ведения запускался: {self.launches}")
        self.assertNotIn(self.pin_mark, self.output)
        self.assertEqual(
            [r["verdict"] for r in self.canary_rows() if r["verdict"] == "green"],
            [], "прогон коммита без входа записан зелёным")


if __name__ == "__main__":
    unittest.main()
