"""Гейт исходов мержа в режиме `ci`: запись отчёта головы сопоставляется с тестом базы по ключу отчёта (ANSWER-1 п. 1 задачи 01M5XZSKK8H096FD3CPN05BQNM).

Стенд — `CiGateBox` долгоживущего файла задачи
(`tests/test_01m5xzskk8h096fd3cpn05bqnm_ci_outcome_gate.py`): здесь только
вид находки, который тот файл не утверждает.
"""
from orchestrator.advance_gates import outcome_integrity
from tests.test_01m5xzskk8h096fd3cpn05bqnm_ci_outcome_gate import (  # noqa: F401 — фикстура
    box, refused)


def test_module_missing_in_head_tree_is_broken_not_gone(box):
    """Модуль ключа зелёного теста базы не найден в дереве головы — находка «сломан правкой» по идентификатору базы, не «исчез».

    Сценарий: голова удаляет файл тестов, отчёт головы несёт те же
    точечные ключи `success`. Отказ гейта мержа: строка «сломан правкой:
    <id>» каждого теста, строк «исчез: <id>» нет.

    Ловит мутацию: неразобранный ключ головы отброшен — находка «исчез»
    вместо «сломан правкой».
    """
    project, rel, names = box.scenario()
    t = box.merge_task(project, {rel: None})
    report = box.green(rel, names)
    box.publish(t.base, project.job, "success", report)
    box.publish(t.head, project.job, "success", report)
    run = box.gate(t)
    detail = refused(box, run)
    for name in names:
        cid = box.cid(project, rel, name)
        assert f"{outcome_integrity.BROKEN}: {cid} — " in detail, box.why(run)
        assert f"{outcome_integrity.GONE}: {cid} — " not in detail, box.why(run)
