"""AC-2 (tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/SPEC.md): переход `review ->
verifying` перед сменой состояния машинно проверяет присутствие sha
головы ветки задачи в origin (сравнением с `git ls-remote` либо
эквивалентным push-состоянием).

Источник — tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/SPEC.md, «Критерии
приёмки», AC-2.

Сценарий отличает эту проверку от более грубой (и неверной) «ветка
существует в origin вообще»: origin здесь ЗНАЕТ о ветке задачи (была
запушена раньше, до REVIEW.md) — но на СТАРОМ коммите, не на текущей
голове. Правильная проверка обязана сравнивать именно SHA головы, не
факт присутствия имени ветки в origin, и восстановить origin до
актуальной головы. `git ls-remote origin <branch>` вернул бы непустой
ответ и на старом коммите — критерий проверяет, что реализация читает
его СОДЕРЖИМОЕ (sha), а не сам факт непустого ответа.

Красен до реализации: сегодня `orchestrator/fsm_advance.py::review`
никак не сверяет sha головы с origin — переход в `verifying` происходит
безусловно, а origin как был на старом коммите, так и остаётся (никакой
push не происходит). Проверено прогоном на немодифицированном коде при
подготовке файла.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import HeadInOriginSandbox  # noqa: E402
from orchestrator import fsm  # noqa: E402


class Ac2CheckComparesExactHeadShaTest(HeadInOriginSandbox):

    def test_ac2_stale_origin_sha_is_detected_and_updated(self):
        """origin знает ветку задачи, но на устаревшем коммите (до
        REVIEW.md) — переход обязан обнаружить расхождение именно по sha
        головы и довести origin до актуальной головы.

        Ловит мутацию: сверка, которая считает "голова в origin" любым
        непустым ответом `git ls-remote`/наличием ветки в origin (не
        сравнивая конкретный sha) — такая сверка сочла бы устаревший
        коммит "уже там", пропустила бы push, и `origin_branch_sha()`
        после перехода остался бы РАВЕН устаревшему значению, а не
        новой голове.
        """
        self.enter_review()
        self.push_branch_to_origin()
        stale_origin_sha = self.origin_branch_sha()
        new_head = self.write_review_approved()
        self.assertNotEqual(
            stale_origin_sha, "",
            "предпосылка теста: origin обязан уже знать ветку задачи "
            "(запушена до REVIEW.md)")
        self.assertNotEqual(
            stale_origin_sha, new_head,
            "предпосылка теста: голова после коммита REVIEW.md обязана "
            "разойтись с тем, что уже в origin")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "verifying")
        self.assertEqual(
            self.origin_branch_sha(), new_head,
            "AC-2: проверка обязана сравнивать именно sha головы, не "
            "факт присутствия ветки в origin — расхождение обязано "
            "было запустить push актуальной головы")


if __name__ == "__main__":
    import unittest
    unittest.main()
