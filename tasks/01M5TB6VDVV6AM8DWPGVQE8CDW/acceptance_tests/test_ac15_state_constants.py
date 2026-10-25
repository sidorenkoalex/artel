"""Один список состояний: `fsm.STATES` и `fsm.TERMINAL_STATES`, из которых
берут значения `report.STATE_ORDER`, `cleanup.TERMINAL_STATES` и
константа окончательных состояний `watch.py`.

Группа: разовый
Красен до реализации: в `orchestrator/fsm.py` нет ни `STATES`, ни `TERMINAL_STATES` — обращение к атрибуту падает AttributeError.

Разовый, а не долгоживущий файл: критерий называет закрытое имя
`watch._TERMINAL_STATES`, а долгоживущему файлу `tests/` чтение закрытых
имён пакета запрещено. Ожидаемый состав и порядок — нынешний (на базе
ветки задачи) `report.STATE_ORDER`, записанный литералом: после мержа
список может законно развиваться, сверять факт этой задачи будет не с
чем.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402

sys.path.insert(0, str(CODE_ROOT))
from orchestrator import cleanup, fsm, report, watch  # noqa: E402

STATE_ORDER_AT_BASE = (
    "spec_writing", "spec_audit", "spec_gate", "tests_writing", "in_dev",
    "review", "verifying", "acceptance", "merge_gate", "escalated", "done",
    "killed",
)


def test_ac15_fsm_constants_are_the_one_list():
    """`fsm.STATES` — нынешний список показа с `verifying`, `fsm.TERMINAL_STATES` — `done` и `killed`; константы `report`, `cleanup` и `watch` — те же объекты.

    Ловит мутацию: `report.STATE_ORDER` оставлен собственным литералом
    (значение равно, но объект другой — `is` ложно); `STATES` собран без
    `verifying` или в порядке объявления переходов FSM; в `watch.py`
    константа переписана копией `tuple(fsm.TERMINAL_STATES)` — равна, но
    не тот же объект.
    """
    assert "verifying" in fsm.STATES
    assert tuple(fsm.STATES) == STATE_ORDER_AT_BASE
    assert len(fsm.TERMINAL_STATES) == 2
    assert set(fsm.TERMINAL_STATES) == {"done", "killed"}
    assert report.STATE_ORDER is fsm.STATES
    assert cleanup.TERMINAL_STATES is fsm.TERMINAL_STATES
    assert watch._TERMINAL_STATES is fsm.TERMINAL_STATES
