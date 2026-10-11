"""AC-4/AC-5 (tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/SPEC.md):

AC-4. Если push из AC-3 не удался, переход отказывает с именованной
причиной «голова ветки не в origin, push не удался: <ошибка>», отказ
журналируется, и задача не входит в `verifying`.

AC-5. Отказ по AC-4 не переводит задачу в `escalated` — задача
остаётся в прежнем состоянии, и последующий `advance` после устранения
причины отказа штатно продолжает переход в `verifying`.

Источник — tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/SPEC.md, «Критерии
приёмки», AC-4, AC-5.

SPEC требование 3 называет это ТЕМ ЖЕ приёмом, что и прочие отказы
`orchestrator/fsm_advance.py` («переход отклонён» без смены
состояния) — то есть graceful-возврат (`store.journal` + `return
False`), а не `sys.exit`: остальные отказы этого же файла (реестр
замечаний, красные acceptance_tests, guard) все следуют этому приёму,
ни один не завершает процесс.

origin ветки задачи ломается НЕПОСРЕДСТВЕННО перед вызовом `advance`,
после того как голова уже разошлась с origin (REVIEW.md ещё не
запушен) — push реально пытается случиться и реально проваливается
(настоящий git, не заглушка).

Красен до реализации: сегодня `orchestrator/fsm_advance.py::review` не
пытается push вовсе — сломанный origin никак не влияет на переход,
задача безусловно уходит в `verifying`, хотя реальный push для неё
провалился бы. Проверено прогоном на немодифицированном коде при
подготовке файла.

Ловушка реализации AC-5 (проверено самопроверкой на временном стабе,
см. скил test-authoring, «Перед завершением»): `review()` сегодня
безусловно вызывает `store.update_task(conn, task_id,
reviewed_iter=iteration)` СРАЗУ после проверки свежести вердикта
(строка перед `if status == "approved":`), ДО регистра замечаний,
прогона acceptance_tests и (после этой задачи) проверки push. Если
push-проверку добавить строго «непосредственно перед `store.set_state
(..., "verifying", ...)»`, не тронув место этого `update_task`, то
ПОВТОРНЫЙ `advance` после починки origin упрётся в «вердикт REVIEW.md
уже учтён» (freshness по `reviewed_iter` уже потрачен первым вызовом)
и не продвинется — AC-5 не выполнится. Чтобы повтор работал, бамп
`reviewed_iter` обязан произойти только после того, как push (и все
остальные условия ветки `approved`) реально прошли, не раньше.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import HeadInOriginSandbox  # noqa: E402
from orchestrator import fsm  # noqa: E402


class Ac4Ac5PushFailureTest(HeadInOriginSandbox):

    def setUp(self):
        super().setUp()
        self.enter_review()
        self.push_branch_to_origin()
        self.stale_origin_sha = self.origin_branch_sha()
        self.new_head = self.write_review_approved()
        self.break_origin_remote()

    def test_ac4_failed_push_is_a_named_refusal_task_stays_in_review(self):
        """Push проваливается по-настоящему (origin указывает на
        несуществующий путь) — переход отказывает именованной причиной,
        задача остаётся в `review`, а не эскалирует.

        Ловит мутацию: код, который на провале push либо тихо
        пропускает ошибку и всё равно входит в verifying (задача
        оказалась бы там с невидимым для CI sha — ровно тот дефект,
        который эта задача чинит), либо эскалирует вместо мягкого
        отказа (следующий advance не смог бы просто повторить
        переход).
        """
        since = len(self.steps())

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "review",
            "AC-4: задача не имеет права войти в verifying с головой, "
            "невидимой для CI")
        self.assertNotEqual(
            self.state(), "escalated",
            "AC-5: провал push сам по себе не эскалирует задачу")
        tail = self.journal_tail(since)
        self.assertIn(
            "голова ветки не в origin, push не удался", tail,
            f"AC-4: отказ обязан быть именован ровно так, как называет "
            f"SPEC: {tail!r}")

    def test_ac5_retry_after_fixing_origin_advances_normally(self):
        """После восстановления origin повторный `advance` (без новых
        коммитов) доводит переход до конца тем же путём, что и штатный
        случай.

        Ловит мутацию: состояние, «залипшее» после первого отказа
        (например, флаг «push уже пробовали» блокирует повтор) —
        второй advance не сдвинул бы задачу дальше review.
        """
        self.capture(fsm.cmd_advance, self.TASK)
        assert self.state() == "review", (
            "предпосылка теста: первый advance обязан был отказать")
        self.restore_origin_remote()

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "verifying")
        self.assertEqual(self.origin_branch_sha(), self.new_head)


if __name__ == "__main__":
    import unittest
    unittest.main()
