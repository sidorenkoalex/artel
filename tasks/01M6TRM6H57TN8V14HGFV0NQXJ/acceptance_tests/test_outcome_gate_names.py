"""Закрытые имена гейта исходов, которые называют критерии: `outcome_integrity._ci_report` на сценарии перезапуска задания GitHub во время чтения (AC-7) и ожидающие статусы `outcome_integrity._CI_PENDING_STATUSES` для негодных значений check run (AC-4).

Группа: разовый
Красен до реализации: у реализации GitHub реестра `forge` нет `job_result`/`job_test_report`, а запись GitHub с `full_suite: ci` отказывает при загрузке — `job_result` отвечает статусом `None` с причиной «не реализовано» или «запись не прочитана», `_ci_report` — «статус не прочитан» вместо «перезапущено во время чтения»; `Job.id` у check runs не заполнен.

Файл — в планке, а не в `tests/`: оба проверяемых имени закрыты
(подчёркивание), а правила долгоживущего файла запрещают чтение закрытых
имён `orchestrator`. Публичная часть тех же критериев — в долгоживущем
файле задачи `tests/test_01m6trm6h57tn8v14hgfv0nqxj_github_ci_report.py`;
отсюда из него берутся стенд (подменная программа `gh`, вымышленная запись
GitHub во временном `config.TARGETS`) и сценарий перезапуска.
"""
import pytest

from orchestrator import ci
from orchestrator.advance_gates import outcome_integrity
from tests.test_01m6trm6h57tn8v14hgfv0nqxj_github_ci_report import (  # noqa: F401
    odd_value, restart_scene, scene)


def test_ac7_ci_report_restart_during_read_is_none(scene, monkeypatch):
    """Новая попытка задания GitHub между чтением статуса и чтением отчёта — `outcome_integrity._ci_report` возвращает `None` с причиной «перезапущено во время чтения».

    Сценарий: при первом чтении попытка — check run N (`success`, зелёный
    отчёт); в момент вызова `forge.job_test_report` у коммита появляется
    check run того же имени с номером больше N, `success`, с зелёным
    отчётом своего окна (тот же сценарий, что у `ci.job_full_suite` в
    долгоживущем файле).

    Ловит мутацию: `_GitHub.pipeline_status` не заполняет `Job.id` — номера
    попытки до и после чтения оба `None`, `_ci_report` отдаёт годный отчёт
    вместо `None`.
    """
    sc = scene
    plan = restart_scene(sc, monkeypatch)
    found = outcome_integrity._ci_report(sc.name, sc.sha, sc.job)
    note = sc.note(f"{found}")
    assert plan["state"]["switched"], note
    assert found[0] is None, note
    assert "перезапущено во время чтения" in found[1], note


@pytest.mark.parametrize("status,conclusion", [
    ("completed", "neutral"), ("completed", "action_required"),
    ("completed", "stale"), ("completed", "invented"), ("invented", None)])
def test_ac4_unfit_values_not_pending(scene, status, conclusion):
    """Заключения `neutral`, `action_required`, `stale` и вымышленное значение дают в `forge.job_result` статус вне `ci.JOB_FINISHED` и вне ожидающих статусов гейта исходов.

    Сценарий: единственный check run задания с состоянием и заключением
    из параметров; «invented» — значение, порождённое зерном.

    Ловит мутацию: негодное значение переводится в `running` или
    `pending` (или в `None` — «статус не прочитан», который гейт исходов
    считает проходящим) — статус среди ожидающих, задача ждала бы на
    `verifying` вместо эскалации.
    """
    sc = scene
    if status == "invented":
        status = odd_value(sc, status)
    if conclusion == "invented":
        conclusion = odd_value(sc, conclusion)
    run = sc.gh.check_run(sc.job, sc.gh.new_id(), status=status,
                          conclusion=conclusion)
    if status != "completed":
        run["conclusion"] = None
        run["completed_at"] = None
    sc.gh.commit(sc.sha, [run, sc.noise()])
    result = sc.result()
    note = sc.note(f"{status}/{conclusion}: {result}")
    assert result.status is not None, note
    assert result.status not in ci.JOB_FINISHED, note
    assert result.status not in outcome_integrity._CI_PENDING_STATUSES, note
