"""Гейт мержа `target-human`: шпион закрытого `_await_main_ci`, названного критерием AC-3, не видит вызова.

Группа: разовый
Красен до реализации: гейт мержа `target-human` сегодня не открывает MR — `forge.open_mr` не зван, задача не уходит в `awaiting_human` (слияние в `base` отказывает белый список отправок).

Наблюдаемые свойства AC-3 (нет слияния, отправки `base`, закрытия,
уборки) держит долгоживущий файл задачи
`tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py::test_ac3_no_merge_no_base_push_no_closing`.
Здесь — только шпион закрытого имени `fsm_merge_gate._await_main_ci`,
которое критерий называет прямо: долгоживущему файлу подмена закрытых
имён пульта запрещена. Стенд — тот же `Stand` долгоживущего файла.
Провалидировано временным стабом ветви `target-human` гейта мержа (см.
докстринг долгоживущего файла, удалён): зелёный.
"""
from unittest import mock

import pytest

from orchestrator import fsm_merge_gate
from tests.test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery import Stand, opened_ok


@pytest.fixture
def stand(real_git):
    return Stand(real_git)


def test_ac3_await_main_ci_not_called(stand):
    """Успешный `approve` записи `target-human` не зовёт `_await_main_ci`.

    Сценарий: запись `target-human`, `draft_mr: false`, задача на
    `merge_gate`, ветка на сервере; `fsm_merge_gate._await_main_ci`
    подменён шпионом. `approve` открывает MR (задача в `awaiting_human`),
    шпион не вызван ни разу.

    Ловит мутацию: ветвь `target-human` после открытия MR проходит хвост
    прежнего пути мержа, включая ожидание CI base — шпион вызван.
    """
    stand.record(draft_mr="false")
    task = stand.new_task(state="merge_gate", published=True)
    with mock.patch.object(fsm_merge_gate, "_await_main_ci") as spy:
        out = stand.approve(task)
    opened_ok(stand, task, out)
    assert spy.call_count == 0, stand.context(task, out)
