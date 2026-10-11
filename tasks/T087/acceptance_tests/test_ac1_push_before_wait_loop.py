"""AC-1 (tasks/T087/SPEC.md): после исхода "pulled" сверки свежести
внутри `merge_gate`, `approve` пушит новый head ветки задачи в origin
ДО начала цикла ожидания CI.

Источник — tasks/T087/SPEC.md, «Критерии приёмки», AC-1.

Проверка размещена ВНУТРИ первого же вызова `ci.branch_status` (единственная
точка, которую зовёт цикл ожидания на каждой итерации, SPEC требование
12/«Материалы») — это и есть операционное определение «до начала цикла
ожидания»: если бы push случался позже (например, только после
получения зелёного статуса), origin к моменту ПЕРВОГО чтения статуса
ещё не видел бы новый head.

Красен до реализации: сегодня `_cmd_approve_merge_gate` после исхода
"pulled" не пушет ветку задачи вовсе и просто печатает "дождись
зелёного CI... и повтори" (`orchestrator/fsm.py`, ветка `pull_outcome ==
"pulled"`) — до первого вызова `ci.branch_status` дело в этом же вызове
не доходит, а `origin` не содержит ветку задачи вообще (assertNotEqual
на пустую строку упадёт первым, до сравнения head'ов). Проверено
прогоном на немодифицированном коде при подготовке файла.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import GREEN, MergeGateCiWaitTest  # noqa: E402


class Ac1PushBeforeWaitLoopTest(MergeGateCiWaitTest):

    def setUp(self):
        super().setUp()
        self.enter_merge_gate()
        self.pre_push_origin_sha = self.origin_branch_sha()

    def test_ac1_branch_pushed_to_origin_before_first_ci_check(self):
        self.add_main_commit()

        checked = {"n": 0}

        def branch_status_checks_push_happened(branch):
            checked["n"] += 1
            new_head = self.branch_head()
            origin_sha = self.origin_branch_sha()
            self.assertNotEqual(
                origin_sha, "",
                f"AC-1: origin обязан уже видеть ветку {branch} к моменту "
                f"первого чтения статуса CI (итерация {checked['n']}) — "
                f"push обязан случиться ДО начала цикла ожидания")
            self.assertEqual(
                origin_sha, new_head,
                f"AC-1: origin обязан видеть ИМЕННО новый (подтянутый) "
                f"head ветки {branch}, а не устаревший, к моменту первого "
                f"чтения статуса CI")
            return GREEN

        self.patch_branch_status(branch_status_checks_push_happened)

        self.approve()

        self.assertGreaterEqual(
            checked["n"], 1,
            "предпосылка теста: цикл ожидания обязан хотя бы раз "
            "прочитать статус CI (иначе проверка внутри мока не "
            "выполнилась ни разу)")
        self.assertNotEqual(
            self.pre_push_origin_sha, self.origin_branch_sha(),
            "предпосылка теста: origin не имел ветки задачи до подтяжки "
            "— после неё обязан её получить")


if __name__ == "__main__":
    import unittest
    unittest.main()
