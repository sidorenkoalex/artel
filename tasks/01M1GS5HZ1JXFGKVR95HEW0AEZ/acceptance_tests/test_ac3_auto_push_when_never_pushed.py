"""AC-3 (tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/SPEC.md): если голова ветки
задачи отсутствует в origin, конвейер выполняет push ветки задачи тем
же механизмом, которым ветка публикуется штатно (`git push -u origin
<branch>`); успешный push журналируется, и переход в `verifying`
продолжается в рамках того же вызова `advance`.

Источник — tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/SPEC.md, «Критерии
приёмки», AC-3.

Origin ветки задачи здесь ЛОМАЕТСЯ с самого начала (до входа в
`spec_gate`) — это гасит и best-effort push самого Draft MR
(`github_adapter.ensure_draft_mr`, побочный эффект входа в `in_dev`,
best-effort и не блокирует), так что к моменту REVIEW.md ветка задачи
НЕ ИМЕЕТ вовсе ни одной записи в origin — не «устарела», а отсутствует
целиком. origin чинится непосредственно перед вызовом `advance`,
проверяемым этим тестом (SPEC требование 2: сеть уже восстановлена к
моменту перехода).

Красен до реализации: сегодня `orchestrator/fsm_advance.py::review` не
делает push вовсе — переход в `verifying` происходит безусловно, а
origin остаётся без единой записи о ветке задачи. Проверено прогоном на
немодифицированном коде при подготовке файла.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import HeadInOriginSandbox  # noqa: E402
from orchestrator import fsm  # noqa: E402


class Ac3AutoPushWhenNeverPushedTest(HeadInOriginSandbox):

    def test_ac3_head_absent_from_origin_triggers_auto_push_and_advances(self):
        """Голова ветки задачи никогда не пушилась — переход обязан
        сам её опубликовать (`git push -u origin <branch>`) и
        продолжить тем же вызовом `advance` без нового захода Оператора.

        Ловит мутацию: код, который решает НЕ пушить при отсутствии
        головы в origin (например, инвертированное условие проверки) —
        origin остался бы без записи о ветке, а `origin_branch_sha()`
        не совпал бы с `branch_head()` после перехода.
        """
        self.break_origin_remote()
        self.enter_review()
        new_head = self.write_review_approved()
        self.assertEqual(
            self.origin_branch_sha(), "",
            "предпосылка теста: origin никогда не видел ветку задачи")
        self.restore_origin_remote()
        since = len(self.steps())

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "verifying",
            "AC-3: успешный авто-push обязан продолжить переход в "
            "verifying тем же вызовом advance")
        self.assertEqual(
            self.origin_branch_sha(), new_head,
            "AC-3: origin обязан получить push именно текущей головы "
            "ветки задачи")
        tail = self.journal_tail(since)
        self.assertIn("push", tail,
                      f"AC-3: успешный push обязан быть журналирован: "
                      f"{tail!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
