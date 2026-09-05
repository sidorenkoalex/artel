"""AC-4 (tasks/01M1SD5RHTJ0H0SR0615SVCJM5/SPEC.md): тексты журнала и
`print` совпадают буквально с текущими для путей, проверяемых
существующими тестами. Три записанных смоук-сценария AC-5 кроют штатный
мерж/красный CI/конфликт на защищённом пути; этот файл добавляет
ЧЕТВЁРТЫЙ, самый первый по порядку путь тела гейта — отказ «голова не в
origin» (`orchestrator/fsm_merge_gate.py:313-319`), который ни один из
трёх сценариев AC-5 не проходит (все они стартуют с уже опубликованной
головой).

Зелёный с рождения: тест воспроизводит уже существующее поведение этой
ветки буквально — рефакторинг обязан оставить журнал/печать нетронутыми
(AC-4), не создать их заново, поэтому тест зелёный уже сегодня и обязан
остаться зелёным после разбора тела на шаги.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import catalog, config, fsm_merge_gate, github_adapter, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture, capture_new_task_id  # noqa: E402

TASK = "01AC4PUSHREFUSALTASK0001"
BRANCH = "task/01ac4pushrefusaltask0001-x"


class PushRefusalLiteralTextTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), TASK, "Задача", "merge_gate",
                          BRANCH, config.DEFAULT_TARGET, 25.0)

    def test_ac4_head_not_in_origin_refusal_journal_and_print_are_literal(self):
        """Отказ на первой же проверке тела гейта («голова ветки задачи не
        видна в origin») журналирует и печатает буквально текущий текст, а
        исход — `("stopped",)`, задача остаётся в `merge_gate`.

        Ловит мутацию: разработчик при выносе этой проверки в отдельный
        шаг меняет текст action/print (например убирает префикс
        `[{task_id}]` или переформулирует «approve отклонён» на
        «approve отказан») — `assertEqual` на буквальных строках здесь
        покраснеет; либо шаг перестаёт возвращать `("stopped",)`
        (например возвращает голый `False`) — `assertEqual(outcome, ...)`
        поймает и это.
        """
        t = store.get_task(store.db(), TASK)
        push_detail = "origin не отвечает на git ls-remote (тест)"

        with mock.patch.object(github_adapter, "ensure_head_in_origin",
                               return_value=(False, push_detail)):
            out, outcome = capture_new_task_id(
                fsm_merge_gate._cmd_approve_merge_gate,
                store.db(), TASK, "merge_gate", t)

        self.assertEqual(outcome, ("stopped",))

        row = store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? "
            "ORDER BY id DESC LIMIT 1", (TASK,)).fetchone()
        self.assertEqual(row["action"], "approve отклонён: голова не в origin")
        self.assertEqual(row["detail"], push_detail)

        self.assertEqual(out.strip(),
                         f"[{TASK}] approve отклонён: {push_detail}")

        state = store.db().execute(
            "SELECT state FROM tasks WHERE id=?", (TASK,)).fetchone()["state"]
        self.assertEqual(state, "merge_gate",
                         "задача обязана остаться на гейте merge_gate")


if __name__ == "__main__":
    unittest.main()
