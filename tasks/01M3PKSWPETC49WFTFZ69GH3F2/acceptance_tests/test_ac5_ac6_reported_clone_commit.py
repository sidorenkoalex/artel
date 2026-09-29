"""AC-5, AC-6 — 01M3PKSWPETC49WFTFZ69GH3F2: запись прогона и сводка несут
коммит, сообщённый процессом клона; расхождение с проверяемым коммитом
красит прогон.

Группа: разовый

Источник — SPEC.md, «Критерии приёмки»:

AC-5. Строка `canary_runs` и строка сводки прогона несут коммит,
сообщённый процессом клона, и при штатном прогоне он равен проверяемому
коммиту.

AC-6. Если сообщённый процессом клона коммит не равен проверяемому,
вердикт прогона не `green`, а сводка называет причину расхождения и оба
коммита.

«Сообщённый коммит, не равный проверяемому» изображается посредником
запуска (`_clone_drive.py`, режим `rehead`): процесс клона отрабатывает
по-настоящему, после чего в его файле результата каждое вхождение
проверяемого sha заменяется sha другого настоящего коммита песочницы
(первого коммита кода) — ровно то, что пульт увидел бы от клона,
исполнившего чужой код. Штатный прогон отличить «сообщённый» от
«проверяемого» не даёт (они равны), поэтому AC-5 проверяется на обоих.

Красен до реализации: процесса клона нет, ведение идёт в процессе пульта
и упирается в растяжку песочницы — ни строки `canary_runs`, ни сводки.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _clone_drive  # noqa: E402


class _ReportedCommitTest(_clone_drive.CloneDriveSandbox):

    def setUp(self):
        super().setUp()
        self.target = self.commit_code(_clone_drive.SCENARIO_GREEN,
                                       self.new_marker("метка"))
        # Пин песочницы (HEAD главной копии) — следующий коммит: пин,
        # проверяемый коммит и первый коммит кода — три разных sha.
        self.pin = self.commit_code(_clone_drive.SCENARIO_GREEN,
                                    self.new_marker("пин"))

    def only_row(self):
        rows = self.canary_rows()
        self.assertEqual(len(rows), 1,
                         f"строк canary_runs: {len(rows)} (зерно {self.seed})\n"
                         f"{self.output}")
        return rows[0]


class NormalRunCommitTest(_ReportedCommitTest):

    def test_ac5_normal_run_records_the_target_commit(self):
        """Штатный прогон на коммите, отличном от пина главной копии:
        `canary_runs.main_sha` и строка сводки задачи несут проверяемый
        коммит (он же сообщённый клоном), и вердикт — `green`.

        Ловит мутацию: пульт пишет в `main_sha` HEAD главной копии
        (`gitcmd.head_sha()` — пин песочницы, другой коммит) вместо коммита,
        сообщённого клоном, либо теряет его при разборе результата (пустая
        строка или `NULL` в `main_sha`).
        """
        self.run_canary(self.target)
        self.assert_no_crash()
        row = self.only_row()
        self.assertEqual(row["main_sha"], self.target)
        self.assertIn(f"sha={self.target}", self.summary_line(row["task_id"]))
        self.assertEqual(row["verdict"], "green")


class MismatchedCommitTest(_ReportedCommitTest):

    def setUp(self):
        super().setUp()
        self.other = self.init_sha
        self.assertNotEqual(self.other, self.target)
        self.run_canary(self.target, mode="rehead", fake_head=self.other)
        self.assert_no_crash()
        self.row = self.only_row()

    def test_ac5_record_and_summary_carry_the_reported_commit(self):
        """Процесс клона сообщил коммит, отличный от проверяемого: в
        `canary_runs.main_sha` и в строке сводки задачи — сообщённый
        коммит, не проверяемый.

        Ловит мутацию: пульт пишет в `main_sha`/сводку свой проверяемый sha
        (`target_sha` из `_resolve_target_sha`), а сообщённый процессом
        клона HEAD игнорирует — запись прогона утверждала бы код, которым
        задача не велась.
        """
        self.assertEqual(self.row["main_sha"], self.other,
                         f"main_sha — не сообщённый клоном коммит (зерно {self.seed})")
        self.assertIn(self.other, self.summary_line(self.row["task_id"]))

    def test_ac6_mismatch_is_not_green_and_names_both_commits(self):
        """Тот же прогон с расхождением: вердикт строки `canary_runs` не
        `green`, а в выводе прогона есть строка, называющая и проверяемый,
        и сообщённый клоном коммит.

        Ловит мутацию: расхождение HEAD клона с проверяемым коммитом не
        сверяется (вердикт штатного исхода — `green`, `pin-update` принял бы
        прогон кода, которого не проверяли) либо сводка называет только
        один из двух коммитов.
        """
        self.assertNotEqual(self.row["verdict"], "green",
                            f"расхождение коммитов дало green (зерно {self.seed})")
        both = [line for line in self.output.splitlines()
                if self.target[:7] in line and self.other[:7] in line]
        self.assertTrue(both, f"ни одна строка вывода не называет оба коммита "
                              f"{self.target} и {self.other}:\n{self.output}")


if __name__ == "__main__":
    unittest.main()
