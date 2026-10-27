"""Существующие тесты `tests/` ветка задачи правит только по мандату требования 22.

Группа: разовый
Зелёный с рождения: до работы разработчика ветка задачи не меняет ни одного существующего файла `tests/` — тест держит, чтобы правка существующих тестов не вышла за мандат (кортеж `FSM_STATES` в `tests/test_auto_cycle.py`, перечни модели доски, перечни `tests/test_report.py`).

Зелёность самих существующих тестов на ветке держит пульт полным
прогоном набора (CI ветки и автогейт) — повторять его здесь не нужно;
планка фиксирует часть критерия, которую полный прогон не видит: тест,
подогнанный правкой под новое поведение, тоже зелёный. Дифф задачи —
`branch_diff()` помощника пульта (от точки расхождения с `origin`).
`tests/test_invariants.py` меняется приложением PLAN (требование 21),
не диффом ветки, поэтому в мандат дифф-правок не входит.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import branch_diff  # noqa: E402

MANDATED = {
    "tests/test_auto_cycle.py",
    "tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py",
    "tests/test_report.py",
}


def touched_existing(diff: str) -> list[str]:
    """Пути `tests/` из диффа, которые существовали до ветки: изменённые,
    удалённые и переименованные (блоки без `new file mode`)."""
    found = []
    for block in diff.split("\ndiff --git "):
        head, _, rest = block.partition("\n")
        head = head.removeprefix("diff --git ")
        if " b/" not in head:
            continue
        old = head.split(" b/", 1)[0].removeprefix("a/")
        if not old.startswith("tests/"):
            continue
        if "new file mode" in rest.split("\n@@", 1)[0]:
            continue
        found.append(old)
    return found


def test_ac20_existing_tests_changed_only_by_mandate():
    """Ветка задачи меняет из существующих файлов `tests/` только файлы мандата.

    Сценарий: из закоммиченного диффа задачи выбираются блоки по путям
    `tests/`, у которых нет `new file mode` (файл был до ветки:
    правка, удаление, переименование); каждый такой путь обязан быть в
    мандате требования 22. Новые файлы задачи (`tests/test_<id>_…`) не
    проверяются.

    Ловит мутацию: разработчик подгоняет под новое состояние чужой тест
    (например `tests/test_zone_lock.py` или
    `tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py`) — путь
    появится в списке и тест покраснеет.
    """
    outside = sorted(set(touched_existing(branch_diff())) - MANDATED)
    assert outside == [], (
        f"существующие тесты изменены вне мандата требования 22: {outside}")
