"""AC-5 (SPEC): «Существует команда пульта `artel doctor --fix`, которая
убирает игнорируемые файлы из артефактных веток живых задач и оставляет
запись в журнале (`store.journal`) каждой затронутой задачи; `main` этой
командой не изменяется».

Три пункта критерия — три проверки одного прогона: (1) `.pyc` пропадает
из артефактной ветки живой задачи, обычный файл рядом (`PLAN.md`)
переживает уборку; (2) `steps`/журнал задачи несёт новую запись; (3)
голова `main` не сдвигается и не появляется новых незакоммиченных правок
рабочего дерева пульта.

Красен до реализации: сегодня `orchestrator/artel.py` разбирает только
`"--restore" in rest` для команды `doctor` (`"doctor": lambda: doctor.
cmd_doctor("--restore" in rest)`) — флаг `--fix` не воспринимается вовсе,
`doctor.cmd_doctor` не несёт ни одного шага уборки артефактных веток;
`.pyc`, посеянный в `setUp`, переживёт вызов CLI без изменений —
`assertNotIn` в первой проверке упадёт.
"""
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import config  # noqa: E402
from _sandbox import DoctorFixSandbox  # noqa: E402

PYC_REL = ("acceptance_tests/__pycache__/test_ac1.cpython-311.pyc")


class DoctorFixCleansArtifactBranchesTest(DoctorFixSandbox):

    def test_ac5_pyc_removed_normal_file_kept_journaled_main_untouched(self):
        """`artel.py doctor --fix` над песочницей с одной живой задачей,
        чья артефактная ветка уже несёт `.pyc` (посеян в `setUp`, тот же
        класс инцидента, что реальный `artifact/01m1kt0792125j9znjnzj86e9q`
        — семь `.pyc` в артефактной ветке hotfix-задачи 03.09 сегодня).

        Ловит мутацию: реализация `--fix`, которая коммитит уборку прямо в
        `main` вместо артефактной ветки задачи, — `main_head_before`
        разойдётся с головой `main` после вызова, третья проверка
        (`assertEqual` sha) покраснеет даже если первые две пройдут.
        """
        self.run_doctor_fix()

        files = self.artifact_branch_files()
        self.assertNotIn(f"tasks/{self.TASK}/{PYC_REL}", files,
                         "игнорируемый файл обязан пропасть из ветки")
        self.assertIn(f"tasks/{self.TASK}/PLAN.md", files,
                      "обычный файл не должен пострадать от уборки")

        self.assertTrue(self.journal_entries(),
                        "уборка обязана оставить запись в журнале задачи")

        main_head_after = self.git("rev-parse", config.MAIN_BRANCH).strip()
        self.assertEqual(main_head_after, self.main_head_before,
                         "main не должен измениться командой doctor --fix")
        self.assertEqual(self.git("status", "--porcelain").strip(), "",
                         "рабочее дерево пульта обязано остаться чистым")


if __name__ == "__main__":
    unittest.main()
