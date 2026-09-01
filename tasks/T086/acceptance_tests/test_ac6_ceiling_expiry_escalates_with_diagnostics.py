"""AC-6 (tasks/T086/SPEC.md): исчерпание потолка по времени в `verifying`
переводит задачу в `escalated` с диагностикой последнего известного
статуса CI в `detail` записи перехода.

Задача входит в `verifying` (`updated_at`, отодвинутый на 6 часов назад
— на порядок больше, чем «порядка 90 минут» требования 3, тем же
приёмом запаса, что и `tasks/T079/acceptance_tests/
test_ac9_verifying_wait_ceiling_escalates.py` берёт 200 попыток против
разумных «десятков»: конкретное значение потолка SPEC не называет, и
тест не имеет права угадывать его число — только заведомо перекрыть
любое разумное толкование «порядка 90 минут»). CI при этом незавершённо
идёт (`RUNNING_RUNS`) — не зелёный (иначе эскалировать нечему) и не
завершённо-красный (тот стоп специфичен для цикла `auto`, требование 2,
не имеет отношения к тому, эскалирует ли ОДИН ручной опрос по истечении
потолка, — смешивать два независимых требования в одном тесте значило
бы не различать причину провала).

Единственный опрос — через `fsm.cmd_advance` напрямую (не через `auto`):
требование 4 говорит о потолке вообще, не привязывая эскалацию к тому,
кто зовёт `advance` — ручной Оператор с уже истёкшим потолком обязан
получить тот же исход.

Красен до реализации: `_cmd_advance` (orchestrator/fsm.py) не содержит
ветки `state == "verifying"` время-осведомлённой (сегодняшний код читает
`t["verifying_attempts"]`, не `updated_at`) — при `updated_at`,
отодвинутом на 6 часов, но `verifying_attempts == 0`, сегодняшний код
просто увеличивает счётчик до 1 и остаётся в `verifying`; `self.state()`
не станет `"escalated"` за один вызов, первый ассерт красный.
"""
import sys
import unittest
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fsm  # noqa: E402
from _sandbox import RUNNING_RUNS, VerifyingTest  # noqa: E402


class VerifyingCeilingExpiryEscalatesTest(VerifyingTest):

    def test_ac6_expired_ceiling_escalates_on_a_single_advance(self):
        self.enter_verifying(RUNNING_RUNS, "[]")
        self.age_verifying_entry(timedelta(hours=6))
        since = self.last_step_id()

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "escalated",
            "потолок ожидания CI, истёкший по времени с момента входа в "
            "verifying, обязан эскалировать задачу")

        details = "\n".join(self.journal_details_since(since))
        self.assertIn(
            "python", details,
            "эскалация обязана нести диагностику ПОСЛЕДНЕГО известного "
            "статуса CI (проверка 'python' ещё идёт, фикстура "
            "RUNNING_RUNS), не безадресное сообщение")


if __name__ == "__main__":
    unittest.main()
