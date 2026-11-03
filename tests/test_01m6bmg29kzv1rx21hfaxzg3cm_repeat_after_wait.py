"""Повтор находки гейта по исходам на `verifying` узнаётся и через опрос ожидания отчёта головы (SPEC 01M6BMG29KZV1RX21HFAXZG3CM, требование 16; ANSWER-2).

Группа: долгоживущий

«Предыдущий отказ гейта по исходам» правила повтора — последняя запись
отказа с находками (`OUTCOME_BROKEN_REFUSAL_ACTION` /
`OUTCOME_INTEGRITY_REFUSAL_ACTION`); записи ожидания отчёта головы и сбоя
подготовки не считаются. Стенд — `VerifyingBox` долгоживущего файла
задачи.
"""
from tests.test_01m6bmg29kzv1rx21hfaxzg3cm_verifying_outcome_gate import (  # noqa: F401
    REPEAT, box, escalated_now, first_return, head_case, waits)


def test_repeat_after_pending_poll_escalates_as_repeat(box):
    """Возврат с набором X, шаг `developer`, снова `verifying`; первый опрос — отчёт головы не готов (ожидание), второй — снова X: `escalated` с причиной «повтор находки гейта по исходам».

    Сценарий: первый возврат по красному тесту X (AC-3). Новый коммит
    `developer`, задача в `verifying`; у новой головы задание `ci_job` в
    `running` — опрос оставляет задачу в `verifying` (запись ожидания).
    Затем задание головы завершается `success` с отчётом, красным ровно по
    X; второй опрос — `escalated`, причина — повтор.

    Ловит мутацию: запись ожидания (`PENDING_ACTION`) или сбоя подготовки
    засчитана «предыдущим отказом» правила повтора — набор находок
    предыдущего отказа пуст, повтор не узнан, эскалация по пределу
    возвратов с другой причиной.
    """
    t, comp, red, _detail, _rows, _output = first_return(box)
    box.to_verifying(t, {f"lib/f{box.word()}.py": f"FIX = '{box.word()}'\n"})
    words = head_case(box, t, comp, "задание running")
    rows, output = box.poll(t)
    waits(box, t, rows, output, words)
    box.forge.jobs[t.sent] = [j for j in box.forge.jobs[t.sent]
                              if j.name != comp.job]
    box.ci_reports(t, {comp.comp: box.red(comp, red)})
    rows, output = box.poll(t)
    detail = escalated_now(box, t, rows, output)
    assert REPEAT in detail, box.why(rows, output)
