"""AC-4/AC-5 (tasks/01M1P9QCHPHSCEA6TK13PV85SP/SPEC.md): отказ по AC-1
реализован как дополнительное условие на существующем переходе
`in_dev -> review` (по образцу `budget_block`/отказов свежести), без
введения нового состояния FSM (AC-4); отказ доносится до следующего
запуска роли developer по действующей механике доставки отказа advance
(T078) — `store.refusal_history`/`brief.advance_refusal_history`
(AC-5).

Красен до реализации: сегодня дифф вне зон не отказывает вовсе (см.
test_ac1_ac2_out_of_zone_diff_refuses.py) — задача либо не остаётся в
`in_dev` (если бы гейт был реализован новым состоянием), либо, при
верной реализации по образцу существующих гейтов, не производит
никакого отказа для T078 подхватить (нечего доставлять). Оба теста
ниже требуют кода задачи.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import ZonesGateSandbox  # noqa: E402

from orchestrator import brief, store  # noqa: E402


class Ac4NoNewFsmStateTest(ZonesGateSandbox):

    def test_ac4_refusal_leaves_the_task_in_the_existing_in_dev_state(self):
        """Отказ по AC-1 возвращает задачу РОВНО в `in_dev` —
        существующее состояние FSM, которое уже несут гейт ёмкости
        диффа и лок `acceptance_tests/` на этом же переходе, а не в
        новое, отдельно заведённое под зоны состояние (например
        `zones_blocked`).

        Ловит мутацию: реализация заводит новое состояние FSM для
        отказа зон (`store.set_state(conn, task_id, "zones_blocked",
        ...)` вместо простого `return False` без смены состояния) —
        `state()` вернул бы что-то отличное от `"in_dev"`, нарушая
        требование «без введения нового состояния FSM» дословно."""
        self.set_zones("orchestrator/store.py")

        self.advance_with_diff_files(["docs/unrelated_note.md"])

        self.assertEqual(
            self.state(), "in_dev",
            "отказ гейта зон обязан оставить задачу в СУЩЕСТВУЮЩЕМ "
            "состоянии in_dev, не в новом состоянии FSM (AC-4)")


class Ac5RefusalReachesNextDeveloperRunTest(ZonesGateSandbox):

    def test_ac5_refusal_detail_surfaces_via_advance_refusal_history(self):
        """Текст отказа гейта зон, ЗАВЕДОМО называющий конкретный файл
        вне зон (AC-2), доходит до `brief.advance_refusal_history` для
        роли developer в состоянии `in_dev` — тем же путём, каким уже
        доставляются отказы лока/свежести/ёмкости на этом переходе
        (T078), а не теряется между запусками.

        Ловит мутацию: отказ гейта зон журналируется действием, не
        начинающимся с `"переход отклонён"` (например собственным
        именем действия вроде `"дифф вне зон"`) — `store.
        refusal_history` фильтрует записи именно по этому префиксу
        (`orchestrator/store.py::REFUSAL_ACTION_PREFIX`), и такая
        запись осталась бы невидимой следующему запуску роли, даже
        если AC-1/AC-2 внешне выглядят рабочими."""
        self.set_zones("orchestrator/store.py")

        self.advance_with_diff_files(["docs/unrelated_note.md"])

        conn = store.db()
        text = brief.advance_refusal_history(conn, self.TASK, "developer",
                                             "in_dev")

        self.assertIn("docs/unrelated_note.md", text,
                     "бриф следующего запуска developer обязан нести "
                     "конкретный файл вне зон из отказа гейта (T078)")


if __name__ == "__main__":
    unittest.main()
