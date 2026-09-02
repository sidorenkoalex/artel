"""AC-1 (tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/SPEC.md): переход `review ->
verifying` при уже допушенной в origin голове ветки задачи не меняет
поведения относительно текущего — нет попытки push и нет новых
журнальных записей сверх существующих.

Источник — tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/SPEC.md, «Критерии
приёмки», AC-1.

Зелёный с рождения: сегодняшний `orchestrator/fsm_advance.py::review`
никакого push вообще не делает — сценарий «голова уже в origin»
уже проходит буквально так, как требует AC-1, безо всякой новой ветки
кода. Тест ловит будущую РЕГРЕССИЮ (код проверки origin/push, который
эта задача добавляет, случайно зацепит и путь «уже допушено»), не
сегодняшний дефект — тем же приёмом, что
`tasks/T087/acceptance_tests/test_ac11_fresh_branch_unchanged.py`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import HeadInOriginSandbox  # noqa: E402
from orchestrator import fsm  # noqa: E402


class Ac1HeadAlreadyPushedUnchangedTest(HeadInOriginSandbox):

    def test_ac1_no_push_and_no_extra_journal_when_head_already_in_origin(self):
        """Голова ветки уже полностью совпадает с origin к моменту
        approve-ревью — переход в `verifying` не делает push и не
        добавляет журнальных записей о push/проверке origin.

        Ловит мутацию: код, который добавляет БЕЗУСЛОВНЫЙ push (или
        безусловную запись в журнал про проверку origin) на каждый
        вход в `verifying`, даже когда голова уже в origin — тест
        поймает и лишний git-push (сравнением sha origin до/после), и
        лишнюю журнальную запись про push.
        """
        self.enter_review()
        self.write_review_approved()
        self.push_branch_to_origin()
        pre_origin_sha = self.origin_branch_sha()
        self.assertEqual(
            pre_origin_sha, self.branch_head(),
            "предпосылка теста: голова ветки задачи обязана совпадать "
            "с origin до вызова advance")
        since = len(self.steps())

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "verifying")
        self.assertEqual(
            self.origin_branch_sha(), pre_origin_sha,
            "AC-1: origin не должен был измениться — push не должен "
            "был случиться, когда голова уже там")
        tail = self.journal_tail(since)
        self.assertNotIn("push", tail,
                         f"AC-1: переход не должен журналировать push, "
                         f"когда голова уже в origin: {tail!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
