"""Приёмочные тесты AC-11/AC-12 (tasks/01M1NKTF173WV5CPDZ1C3WW69K/SPEC.md):
guard отклоняет артефакт `type: plan`/`review`/`spec` со статусом,
отличным от `escalate` (включая `draft`/`ready`/`approved`), но
содержащий раздел «Эскалация» с непустой подсекцией «Вопросы» либо
пометкой «Блокирует» — причина называет «эскалация текстом без статуса
escalate» (AC-11). `status: escalate` — валидный статус для `type: plan`
(наравне с уже валидным для `type: review`), и такой PLAN с заполненной
секцией «Эскалация» проходит guard без нарушений (AC-12, позитивный
кейс к AC-11).

Красен до реализации: `scripts/guard.py::check_content` сегодня раздел
«Эскалация» вообще не разбирает (только состав обязательных секций и
допустимость `status`) — PLAN/SPEC/REVIEW с текстом эскалации без смены
статуса проходит без единого нарушения (AC-11 падает на пустом списке
ошибок); `RULES["plan"]["statuses"]` сегодня не содержит `"escalate"` —
тот же PLAN со `status: escalate` отклоняется банальным «недопустимый
status» (AC-12 падает и на прямой проверке `RULES`, и на непустом
списке ошибок).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts import guard  # noqa: E402

# Формат раздела «Эскалация» — из skills/escalation-rules.md («Как
# эскалировать»): подпункты «- **Вопросы** — …», «- **Контекст** — …»,
# «- **Блокирует** — …» одним списком под заголовком `## Эскалация`.
QUESTIONS_ESCALATION = (
    "## Эскалация\n\n"
    "- **Вопросы** — 1. Продолжать так или эдак? Дефолт — «так».\n"
    "- **Контекст** — что успел сделать/выяснить.\n"
    "- **Блокирует** — дальнейшую работу над задачей.\n"
)

BLOCKS_ONLY_ESCALATION = (
    "## Эскалация\n\n"
    "- **Контекст** — что успел сделать/выяснить.\n"
    "- **Блокирует** — дальнейшую работу над задачей целиком.\n"
)

REASON_SNIPPET = "эскалация текстом без статуса escalate"


def plan_text(status: str, escalation_body: str = "") -> str:
    return (
        "---\n"
        f"task: x\ntype: plan\nauthor_role: developer\nstatus: {status}\n"
        "---\n\n"
        "## Подход\n\nТекст подхода.\n\n"
        "## Шаги\n\n1. Шаг.\n\n"
        "## Покрытие требований\n\n| Требование | Шаг |\n|---|---|\n| 1 | 1 |\n\n"
        "## Влияние на систему\n\nТекст влияния.\n\n"
        f"{escalation_body}"
    )


def review_text(status: str, escalation_body: str = "") -> str:
    return (
        "---\n"
        f"task: x\ntype: review\nauthor_role: reviewer\nstatus: {status}\n"
        "---\n\n"
        "## Соответствие SPEC\n\nТекст.\n\n"
        "## Замечания\n\nТекст.\n\n"
        "## Вердикт\n\nТекст.\n\n"
        f"{escalation_body}"
    )


def spec_text(status: str, escalation_body: str = "") -> str:
    return (
        "---\n"
        f"task: x\ntype: spec\nauthor_role: analyst\nstatus: {status}\n"
        "---\n\n"
        "## Контекст\n\nТекст.\n\n"
        "## Требования\n\nТекст.\n\n"
        "## Критерии приёмки\n\nТекст.\n\n"
        "## Не входит\n\nТекст.\n\n"
        f"{escalation_body}"
    )


class EscalationTextWithoutStatusTest(unittest.TestCase):
    """AC-11: во всех трёх типах, несущих канал эскалации по требованию 6
    SPEC (PLAN/REVIEW/SPEC), текстовая эскалация без статуса escalate —
    нарушение guard'а с одной и той же названной причиной."""

    def test_ac11_plan_with_questions_and_wrong_status_is_rejected(self):
        """PLAN.md со `status: ready` несёт непустую подсекцию «Вопросы» в
        разделе «Эскалация» — guard обязан отклонить его этой причиной.

        Ловит мутацию: проверка раздела «Эскалация» не реализована вовсе
        (или реализована, но не подключена к `check_content`) — список
        нарушений остаётся пустым для явно неправильного состояния.
        """
        errors = guard.check_content("PLAN.md",
                                     plan_text("ready", QUESTIONS_ESCALATION))

        self.assertTrue(
            any(REASON_SNIPPET in e for e in errors),
            f"нарушение с причиной «{REASON_SNIPPET}» не найдено среди: {errors}")

    def test_ac11_review_with_blocks_marker_and_wrong_status_is_rejected(self):
        """REVIEW.md со `status: approved` несёт непустую пометку
        «Блокирует» без непустых «Вопросы» — этого одного достаточно для
        отказа guard'а той же причиной (критерий: «Вопросы» ЛИБО
        «Блокирует»).

        Ловит мутацию: проверка распознаёт только подсекцию «Вопросы»,
        игнорируя самостоятельную пометку «Блокирует» — REVIEW.md с
        реальным блокером проходит guard молча.
        """
        errors = guard.check_content(
            "REVIEW.md", review_text("approved", BLOCKS_ONLY_ESCALATION))

        self.assertTrue(
            any(REASON_SNIPPET in e for e in errors),
            f"нарушение с причиной «{REASON_SNIPPET}» не найдено среди: {errors}")

    def test_ac11_spec_with_questions_and_wrong_status_is_rejected(self):
        """SPEC.md со `status: draft» несёт непустую подсекцию «Вопросы» в
        разделе «Эскалация» — та же причина отказа, что и у PLAN/REVIEW.

        Ловит мутацию: проверка подключена только к `type: plan`/
        `review`, не к `type: spec` (SPEC.md — страховочный случай по
        «Контексту» SPEC, но AC-11 буквально называет все три типа).
        """
        errors = guard.check_content(
            "SPEC.md", spec_text("draft", QUESTIONS_ESCALATION))

        self.assertTrue(
            any(REASON_SNIPPET in e for e in errors),
            f"нарушение с причиной «{REASON_SNIPPET}» не найдено среди: {errors}")

    def test_ac11_plan_without_an_escalation_section_is_not_flagged(self):
        """Обычный PLAN.md без раздела «Эскалация» вовсе — новое правило
        не имеет права его зацепить.

        Ловит мутацию: правило срабатывает по одному лишь `status !=
        escalate`, без проверки наличия и содержательности раздела
        «Эскалация» — любой обычный PLAN.md со `status: ready` (подавляющее
        большинство существующих) ловил бы ложное нарушение.
        """
        errors = guard.check_content("PLAN.md", plan_text("ready"))

        self.assertFalse(
            any(REASON_SNIPPET in e for e in errors),
            f"PLAN.md без секции «Эскалация» не должен ловить это "
            f"правило: {errors}")


class PlanEscalateStatusValidTest(unittest.TestCase):
    """AC-12: `escalate` — валидный статус `type: plan`, позитивный кейс
    к AC-11."""

    def test_ac12_escalate_is_a_valid_plan_status(self):
        """`RULES["plan"]["statuses"]` буквально содержит `"escalate"`.

        Ловит мутацию: расширение enum'а забыто или откачено — прямая
        проверка множества статусов ловит это независимо от поведения
        `check_content`.
        """
        self.assertIn("escalate", guard.RULES["plan"]["statuses"])

    def test_ac12_plan_with_escalate_status_and_filled_escalation_passes(self):
        """PLAN.md со `status: escalate` и заполненным разделом
        «Эскалация» (непустые «Вопросы») проходит guard без единого
        нарушения — ни по статусу, ни по правилу AC-11.

        Ловит мутацию: `escalate` добавлен в `RULES`, но правило AC-11
        всё равно срабатывает на артефактах СО статусом escalate (не
        сузили условие «status != escalate» при подключении проверки).
        """
        errors = guard.check_content(
            "PLAN.md", plan_text("escalate", QUESTIONS_ESCALATION))

        self.assertEqual(
            errors, [],
            f"PLAN.md status: escalate с заполненной секцией «Эскалация» "
            f"обязан проходить guard без нарушений: {errors}")


if __name__ == "__main__":
    unittest.main()
