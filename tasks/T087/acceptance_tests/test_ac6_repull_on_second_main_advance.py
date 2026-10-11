"""AC-6 (tasks/T087/SPEC.md): если к моменту перезахвата мьютекса (AC-5)
main снова ушёл вперёд относительно только что подтянутой ветки,
`approve` повторяет подтяжку, прогон приёмочных тестов, пуш нового head,
освобождение мьютекса и цикл ожидания CI для этого нового head, в
пределах общего потолка AC-4.

Источник — tasks/T087/SPEC.md, «Критерии приёмки», AC-6.

Сценарий: main уходит вперёд ДВАЖДЫ — первый раз до входа в цикл
ожидания (обычная подтяжка AC-1), второй раз ПОКА первый цикл ожидания
ещё идёт (внедряется побочным эффектом внутри первого ответа
`ci.branch_status`, ДО того как он вернёт зелёный статус, завершающий
первый цикл) — к моменту перезахвата мьютекса ветка снова отстала.
Наблюдаемая точка второго цикла — второй вызов `ci.branch_status`:
к этому моменту ветка обязана УЖЕ нести второй коммит main И УЖЕ быть
запушена в origin (тот же контракт, что AC-1 проверяет для первого
цикла).

Красен до реализации: сегодня цикла ожидания и повторной подтяжки внутри
одного вызова `approve` нет вовсе — первая же подтяжка останавливает
`approve` сообщением "дождись зелёного CI... и повтори", `ci.branch_
status` не вызывается в этом вызове вообще, а второй коммит main,
добавленный тестом внутри мока, никогда не появится на входе в
`ci.branch_status`, потому что мок не будет вызван.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import GREEN, MergeGateCiWaitTest  # noqa: E402


class Ac6RepullOnSecondMainAdvanceTest(MergeGateCiWaitTest):

    def setUp(self):
        super().setUp()
        self.enter_merge_gate()

    def test_ac6_second_main_advance_during_wait_triggers_second_cycle(self):
        c2 = self.add_main_commit()
        state = {"n": 0, "c3": None}

        def sequenced(branch):
            state["n"] += 1
            if state["n"] == 1:
                # Пока первый цикл ожидания ещё идёт (первый ответ — тот
                # самый первый вызов), main снова уходит вперёд — дыра,
                # которую AC-6 обязана закрыть при перезахвате.
                state["c3"] = self.add_main_commit(
                    "main-progress-2.txt", "второй прогресс main\n")
                return GREEN
            if state["n"] == 2:
                # Второй цикл ожидания: к этому моменту AC-6 обязана была
                # уже повторить подтяжку И пуш нового head (тот же
                # контракт, что AC-1 для первого цикла).
                self.assertTrue(
                    self.is_ancestor(state["c3"], self.branch_head()),
                    "AC-6: перед вторым циклом ожидания ветка обязана "
                    "снова нести подтяжку main (второй коммит)")
                self.assertEqual(
                    self.origin_branch_sha(), self.branch_head(),
                    "AC-6: перед вторым циклом ожидания новый head "
                    "обязан быть уже запушен в origin")
                return GREEN
            return GREEN

        self.patch_branch_status(sequenced)

        self.approve()

        self.assertGreaterEqual(
            state["n"], 2,
            f"AC-6: второй уход main вперёд обязан вызвать ВТОРОЙ цикл "
            f"ожидания CI (минимум два чтения статуса), фактически "
            f"{state['n']}")
        self.assertEqual(
            self.state(), "done",
            "AC-6: после второго цикла подтяжки/ожидания задача обязана "
            "всё равно дойти до done в том же вызове approve")
        self.assertTrue(
            self.is_ancestor(c2, self.main_head()),
            "первый коммит main обязан остаться предком итогового main")
        self.assertTrue(
            self.is_ancestor(state["c3"], self.main_head()),
            "второй коммит main обязан остаться предком итогового main")


if __name__ == "__main__":
    import unittest
    unittest.main()
