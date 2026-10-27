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
# AC-15: escalate — положительную половину AC-15 («описание называет изменённые веткой защищённые пути») при действующих гейтах проверить нельзя: ветку с правкой пути из `no_paths` проекта (`repo_context.protected_paths`) гейт зон на выходе из `in_dev` (`advance_gates/zones.py:265`, «отказывает БЕЗУСЛОВНО») отклоняет до отправки и до чернового MR, а гейт мержа (`fsm_merge_gate._protected_path_diff_gate`, по требованию 1 исполняется без изменений) эскалирует её до открытия MR — ни на одном пути описание MR с изменённым защищённым путём не возникает. Варианты: (а, умолчание) планка проверяет отрицательную половину (нет неизменённых защищённых путей, мутация «все защищённые пути проекта» краснит) и последнюю фразу критерия — тесты `test_ac15_*` долгоживущего файла уже написаны; (б) тест обходит гейты подменой их закрытых обёрток (`_zones_gate_refuses`, `_protected_path_diff_gate`) и проверяет положительную половину — навязывает устройство кода; (в) подсветку снять из требования 6 и AC-15.
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
