"""Приёмочные тесты AC-18, AC-19 — tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/SPEC.md,
требование 4: открытый алерт `kind=attention` задачи закрывается
автоматически на следующем успешном переходе состояния этой задачи, кем
бы он ни был вызван (`ANSWER-1.md`, вопрос 1, вариант B, мандат на
расширение зон на общую точку перехода — `store.set_state` либо
обработчики `fsm.py`/`fsm_advance.py`). AC-18 — переход изнутри цикла
`auto`; AC-19 — переход ручной командой Оператора вне цикла.

Красен до реализации: ДА, весь файл. Сегодня `alerts.KINDS` не несёт
`"attention"` — открыть алерт этого вида для проверки закрытия сегодня
нечем: сценарии открытия (AC-7/AC-8, эскалация и стоп-кран) сами по
себе уже рабочие, но шаг «алерт открыт» не выполняется вовсе — тесты
падают на `assertEqual(len(...), 1)` ПОСЛЕ первого вызова (получат 0),
до того, как вообще дойти до проверки закрытия.

ВАЖНО: закрывающий переход обязан быть НАСТОЯЩИМ (через реальный
`fsm.cmd_advance`/`cmd_approve`/`cmd_reject`, а не через `self.
set_state()` — тот приём сандбокса написан «в обход переходов»,
буквально не проходит ту точку, где по мандату ANSWER-1 обязан висеть
хук закрытия). Открывающий стоп-кран/эскалацию сценарии по-прежнему
используют `self.set_state()`/`FakeAdvance` — там это ЗАВОДИТ причину
остановки для `auto`, а не имитирует закрывающий переход, поэтому приём
уместен ровно как и в AC-7/AC-8.

Песочница — `_sandbox.StallDetectionSandbox`, тот же приём, что и в
остальных файлах этой задачи; для настоящего перехода `in_dev ->
review` — тот же приём, что и `tasks/T034/acceptance_tests/
test_auto_guard_refusal.py::Ac4NonGuardStateKeepsRunningTest.
test_ac4_valid_ready_plan_still_advances_the_task` (ready PLAN.md,
записанный агентом/тестом напрямую, продвигает задачу дальше `in_dev`
БЕЗ дополнительных патчей git/guard — тот же минимальный набор
подмен `config`, что и здесь).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import fsm, gitcmd, store  # noqa: E402
from tests.sandbox import (disk_backed_ls_tree_files,  # noqa: E402
                           disk_backed_show)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import FakeAdvance, StallDetectionSandbox  # noqa: E402


class Ac18AlertClosesOnATransitionInsideTheAutoCycleTest(StallDetectionSandbox):
    """AC-18: открытый алерт закрывается на следующем успешном переходе,
    инициированном самим `auto` (`run`+`advance` внутри цикла)."""

    def setUp(self):
        super().setUp()
        self.write_plan()
        self.set_state("in_dev")

    def _force_real_transition_to(self, target_state: str):
        """Подмена `fsm.cmd_advance`, которая двигает состояние ЧЕРЕЗ
        настоящий `store.set_state` (не через `self.set_state()` —
        тот в обход переходов и не проходит точку, где по мандату
        ANSWER-1 обязан висеть хук закрытия требования 4) — ловит
        закрытие ровно на факте «состояние сменилось настоящим
        переходом», не завязываясь на конкретный гейт-путь `in_dev ->
        review` (тот, продолженный дальше в `review` без REVIEW.md,
        сам упёрся бы в НОВЫЙ порог холостых требования 2 внутри ТОГО
        ЖЕ вызова `auto()` и завёл бы свой алерт — посторонний для AC-18
        шум). `target_state` — гейт (`spec_gate`/`acceptance`/
        `merge_gate`): роли у него нет, `_cmd_auto` останавливается
        сразу на нём, без дальнейших холостых шагов (AC-14 — такая
        остановка своего алерта не заводит)."""
        def _advance(task_id: str, session_id: str | None = None) -> bool:
            conn = store.db()
            t = store.get_task(conn, task_id)
            store.set_state(conn, task_id, target_state, "fsm",
                            expected_state=t["state"], detail="тестовый переход")
            return False
        return _advance

    def test_ac18_alert_opened_by_the_stop_crane_closes_on_the_next_auto_transition(self):
        """Ловит мутацию: хук закрытия висит там, где переход
        инициирован НАПРЯМУЮ ручной командой (`fsm.cmd_advance` верхнего
        уровня, вызванной Оператором), но не срабатывает, когда тот же
        `fsm.cmd_advance` вызван ИЗНУТРИ `_cmd_auto` — тогда именно
        переход, добытый самим циклом, оставил бы алерт висеть ложно до
        следующего ручного вмешательства Оператора (ровно тот класс
        ложных сигналов, который ANSWER-1 называет доводом против
        варианта A).
        """
        advance = FakeAdvance()
        action = "переход отклонён: гейт ёмкости diff"
        advance.script = [(action, "деталь 1"), (action, "деталь 2")]
        with mock.patch.object(fsm, "cmd_advance", advance):
            self.auto()
        self.assertEqual(self.state(), "in_dev")
        opened = self.open_attention_alerts()
        self.assertEqual(len(opened), 1,
                         f"алерт стоп-крана не открылся: {len(opened)}")

        with mock.patch.object(fsm, "cmd_advance",
                               self._force_real_transition_to("acceptance")):
            self.auto()

        self.assertEqual(
            self.state(), "acceptance",
            "второй вызов auto должен был продвинуть задачу настоящим "
            "переходом — состояние не сменилось")
        self.assertEqual(
            self.open_attention_alerts(), [],
            "алерт остался открытым после успешного перехода auto")


class Ac19AlertClosesOnAManualOperatorTransitionOutsideAutoTest(
        StallDetectionSandbox):
    """AC-19: открытый алерт закрывается на следующем успешном переходе,
    инициированном ручной командой Оператора (`advance`, `approve` или
    `reject`) вне цикла `auto`."""

    def setUp(self):
        super().setUp()
        # A7: `artifact_source.resolve` всегда `foreign=True` — ручной
        # `advance` читает PLAN.md через `gitcmd.show`/`gitcmd.
        # ls_tree_files`; заглушка `fake_git` песочницы вернула бы
        # пустышку вместо PLAN.md, который `write_plan()` кладёт на диск.
        # Подмены — по образцу tests/test_auto_cycle.py::AutoCycleTest,
        # только для этого класса (ANSWER-2, ADR-0012: правка Оператора,
        # утверждения тестов не меняются).
        self.patch_object(gitcmd, "show", disk_backed_show)
        self.patch_object(gitcmd, "ls_tree_files", disk_backed_ls_tree_files)
        self.write_plan()
        self.set_state("in_dev", draft_mr_created=1)

    def _open_alert_via_escalation(self) -> None:
        """Общий способ открыть алерт для всех трёх тестов этого класса
        (AC-7): причина остановки развязана с последующим ручным
        переходом — какой бы командой Оператор ни закрыл её, алерт
        обязан закрыться (SPEC требование 4 не различает команды)."""
        self.agent.script = [lambda: self.set_state("escalated")]
        self.auto()
        opened = self.open_attention_alerts()
        self.assertEqual(len(opened), 1, f"алерт не открылся: {len(opened)}")

    def test_ac19_manual_advance_outside_auto_closes_the_alert(self):
        """Ловит мутацию: хук закрытия висит только внутри `auto.py`
        (например, сам цикл проверяет и ack'ает алерт после своего
        `fsm.cmd_advance`) вместо общей точки перехода — тогда ручной
        `artel.py advance`, вызванный Оператором САМ ПО СЕБЕ, вне
        `auto`, не закрыл бы алерт вовсе.
        """
        self._open_alert_via_escalation()
        # Возврат из эскалации — дело approve (см. соседние тесты);
        # здесь нужен переход, доступный именно `advance`: возвращаем
        # задачу в `in_dev` в обход (это не тестируемый переход) и
        # проверяем закрытие на настоящем `advance` (PLAN.md уже ready).
        self.set_state("in_dev")

        fsm.cmd_advance(self.TASK)

        self.assertEqual(self.state(), "review")
        self.assertEqual(self.open_attention_alerts(), [])

    def test_ac19_manual_approve_outside_auto_closes_the_alert(self):
        """`approve` из `escalated` (без `answer_baseline` — эскалация
        класса «упавший агент», не эскалация с вопросом) возвращает
        задачу в `in_dev` — переход, инициированный НЕ `auto` (auto
        никогда не проходит гейт эскалации сама, требование 1).

        Ловит мутацию: хук закрытия алерта перенесён из общей точки
        перехода (`store.set_state`) в `auto.py` — тогда `approve`
        вне цикла оставит алерт открытым, `open_attention_alerts()`
        вернёт непустой список."""
        self._open_alert_via_escalation()

        fsm.cmd_approve(self.TASK)

        self.assertEqual(self.state(), "in_dev")
        self.assertEqual(self.open_attention_alerts(), [])

    def test_ac19_manual_reject_outside_auto_closes_the_alert(self):
        """`reject` из `merge_gate` возвращает задачу в `in_dev` —
        состояние сюда доставлено в обход (не тестируемый переход),
        чтобы проверить закрытие именно на `reject`, а не на пути к
        `merge_gate`.

        Ловит мутацию: хук закрытия алерта срабатывает только на
        переходах «вперёд» (пропускает возвраты `reject`) — тогда
        алерт останется открытым после `reject`."""
        self._open_alert_via_escalation()
        self.set_state("merge_gate")

        fsm.cmd_reject(self.TASK, "причина теста")

        self.assertEqual(self.state(), "in_dev")
        self.assertEqual(self.open_attention_alerts(), [])


if __name__ == "__main__":
    unittest.main()
