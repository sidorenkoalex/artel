"""AC-11 (tasks/T087/SPEC.md): ветка задачи, не отставшая от main на
входе в `merge_gate` (freshness "fresh"), проходит гейт без пуша и без
цикла ожидания CI — поведение перехода не меняется относительно
сегодняшнего (один мьютекс-держащий проход, одна проверка CI).

Источник — tasks/T087/SPEC.md, «Критерии приёмки», AC-11.

Эта задача касается ТОЛЬКО исхода "pulled" (SPEC «Не входит»: «путь
без подтяжки не трогается»); этот тест — регрессионный контроль
обратного случая, тем же приёмом, что и
`tasks/T053/acceptance_tests/test_ac4_not_behind_merge_unchanged.py`
для T053. Ветка не отстаёт от main вовсе — `ci.branch_status` обязан
быть вызван РОВНО один раз (без цикла повторов), паузы не должно быть
ни одной, и origin не должен получить push ветки ЗАДАЧИ (эта задача не
вводит его для свежей ветки — только `git push` main внутри самого
merge, как и раньше).

Зелёный с рождения: свежая ветка не проходит через код, который эта
задача добавляет (условие "pulled" не выполняется) — сегодняшнее
поведение уже соответствует критерию буквально; тест ловит будущую
РЕГРЕССИЮ (код push/цикла ожидания случайно зацепит и путь "fresh"),
не текущий дефект.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import MergeGateCiWaitTest  # noqa: E402


class Ac11FreshBranchUnchangedTest(MergeGateCiWaitTest):

    def setUp(self):
        super().setUp()
        self.enter_merge_gate()

    def test_ac11_fresh_branch_skips_push_and_wait_loop(self):
        calls = {"n": 0}

        def counted_green(branch):
            calls["n"] += 1
            return True, "CI коммита abc12345 зелёный (1 проверок) (тест)"

        self.patch_branch_status(counted_green)

        self.approve()

        self.assertEqual(
            self.state(), "done",
            "предпосылка теста: свежая ветка с зелёным CI обязана дойти "
            "до done одним approve, как и раньше")
        self.assertEqual(
            calls["n"], 1,
            f"AC-11: свежая ветка обязана проверяться РОВНО одним "
            f"чтением статуса CI, без цикла повторов — прочитано "
            f"{calls['n']} раз(а)")
        self.assertEqual(
            self.clock.sleep_calls, [],
            f"AC-11: свежая ветка не имеет права ждать (пауза цикла "
            f"ожидания предназначена только для исхода 'pulled') — "
            f"зафиксированы паузы {self.clock.sleep_calls!r}")
        self.assertEqual(
            self.origin_branch_sha(), "",
            "AC-11: свежая ветка не имеет права пушить СВОЮ ветку в "
            "origin (этот механизм — только для исхода 'pulled', "
            "требование 1)")


if __name__ == "__main__":
    import unittest
    unittest.main()
