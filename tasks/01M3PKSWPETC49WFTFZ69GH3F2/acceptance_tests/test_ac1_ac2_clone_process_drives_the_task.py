"""AC-1, AC-2 — 01M3PKSWPETC49WFTFZ69GH3F2: учебную задачу ведёт процесс
интерпретатора из эфемерного клона кодом проверяемого коммита.

Группа: разовый

Источник — SPEC.md, «Критерии приёмки»:

AC-1. При прогоне канарейки учебная задача заводится и ведётся процессом
интерпретатора, запущенным из эфемерного клона с рабочим каталогом —
клоном; процесс пульта не вызывает `catalog.cmd_new`, `workspace.ensure`,
`auto.cmd_auto` и помощники гейтов учебной задачи.

AC-2. Сценарий, где код клона на проверяемом коммите отличается от кода
пульта (вспомогательная метка в модуле клона): результат прогона несёт
метку клона, а не пульта.

Группа — разовый: сценарий держится на песочнице `_clone_drive.py` (копия
кода пульта в git-песочнице с подменой `auto`/`runner` в коммите,
растяжки на приватных помощниках `orchestrator.canary`, обёртка запуска
процесса) — по правилам долгоживущего файла `tests/` такое не пишется;
долгоживущие тесты нового устройства разработчик пишет в `tests/` по
требованию 8 SPEC.

Красен до реализации: учебную задачу заводит и ведёт процесс пульта —
`canary._run_task_in_ephemeral_clone` зовёт `catalog.cmd_new` сам, прогон
упирается в растяжку песочницы, процесса клона не запускается ни одного.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _clone_drive  # noqa: E402


class CloneProcessDrivesTheTaskTest(_clone_drive.CloneDriveSandbox):

    def setUp(self):
        super().setUp()
        # Проверяемый коммит несёт свою метку; пин песочницы (HEAD) —
        # следующий коммит с ДРУГОЙ меткой: и код пульта, и код пина
        # отличаются от кода проверяемого коммита.
        self.clone_mark = self.new_marker("метка-клона")
        self.target = self.commit_code(_clone_drive.SCENARIO_GREEN, self.clone_mark)
        self.pin_mark = self.new_marker("метка-пина")
        self.pin = self.commit_code(_clone_drive.SCENARIO_GREEN, self.pin_mark)
        self.run_canary(self.target)

    def test_ac1_task_is_driven_by_interpreter_process_in_the_clone(self):
        """Прогон канарейки на коммите с сценарием «шаг роли уводит задачу в
        merge_gate»: процесс пульта не тронул ни заведения, ни ведения
        учебной задачи, а запущен ровно один процесс интерпретатора, чей
        рабочий каталог — эфемерный клон на проверяемом коммите с входом
        `orchestrator/canary_drive.py`; клон к концу прогона убран.

        Ловит мутацию: `_run_task_in_ephemeral_clone` по-прежнему зовёт
        `catalog.cmd_new`/`workspace.ensure`/`_drive_task` в процессе пульта
        (растяжка записана, процесса клона нет) — либо процесс клона
        запускается с рабочим каталогом главной копии, а не клона (его
        `cwd` — не клон на проверяемом коммите).
        """
        self.assert_no_crash()
        self.assert_no_pult_drive()
        self.assertEqual(
            len(self.launches), 1,
            f"ожидался ровно один запуск процесса клона, было "
            f"{len(self.launches)} (зерно {self.seed})\n{self.output}")
        launch = self.launches[0]
        first = Path(launch["args"][0]).name
        self.assertTrue(
            first.startswith("python") or launch["args"][0] == sys.executable,
            f"процесс клона — не интерпретатор: {launch['args']}")
        cwd = launch["cwd"]
        self.assertNotEqual(cwd, self.root.resolve(),
                            "рабочий каталог процесса — главная копия пульта")
        self.assertNotEqual(cwd, _clone_drive.CODE_ROOT.resolve(),
                            "рабочий каталог процесса — код пульта")
        self.assertTrue(launch["drive_in_cwd"],
                        f"в рабочем каталоге процесса нет входа "
                        f"{_clone_drive.DRIVE_ENTRY}: {cwd}")
        self.assertEqual(launch["head"], self.target,
                         f"рабочий каталог процесса стоит не на проверяемом "
                         f"коммите (зерно {self.seed})")
        self.assertIn(cwd, [p.resolve() for p in self.canary_dirs],
                      f"рабочий каталог процесса {cwd} — не эфемерный клон "
                      f"прогона {self.canary_dirs}")
        self.assert_clone_dirs_removed()

    def test_ac2_run_result_carries_the_clone_mark_not_the_pult_one(self):
        """Код проверяемого коммита метит свои переходы меткой клона, код пина —
        другой меткой, код процесса пульта меток не ставит вовсе: вывод
        прогона несёт метку клона и не несёт метки пина, а исход задачи —
        штатный kill на merge_gate, до которого её довела подмена клона.

        Ловит мутацию: ведение учебной задачи в процессе пульта (переходы
        делает код пульта — метки клона в результате нет, прогон упирается
        в растяжку) либо процесс клона исполняет код пина (checkout не на
        проверяемом коммите — в выводе метка пина).
        """
        self.assert_no_crash()
        self.assertIn(self.clone_mark, self.output,
                      f"в результате прогона нет метки кода клона (зерно "
                      f"{self.seed})\n{self.output}")
        self.assertNotIn(self.pin_mark, self.output,
                         f"в результате прогона метка кода пина (зерно {self.seed})")
        rows = self.canary_rows()
        self.assertEqual(len(rows), 1, f"строк canary_runs: {len(rows)}\n{self.output}")
        self.assertEqual(rows[0]["outcome"], "killed")
        self.assertIn("штатно", self.summary_line(rows[0]["task_id"]))


if __name__ == "__main__":
    unittest.main()
