"""Модульные свойства проверки порядка и рамки частей деления (SPEC
01M5TB6VDVV6AM8DWPGVQE8CDW, требования 4, 5, 8): `merge_after.
division_order` и `guard.division_frame` без вызова `approve`.

Сквозные сценарии деления держит долгоживущий файл задачи
`tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_division_finish.py`; здесь — то,
чего он не задевает: выбор преемника из нескольких равных кандидатов,
повтор элемента «части N», «после» без перечня, префикс id родителя,
пустое поле «Рамка:».
"""
import pytest

from orchestrator import catalog, config, merge_after, store
from scripts import guard
from tests.sandbox import capture_new_task_id

FIRST = "первая, без зависимостей"


def new_task(title: str) -> str:
    _, task_id = capture_new_task_id(catalog.cmd_new, title)
    return task_id


def order(parent: str, orders: list[str]):
    parts = [(f"Часть {n}", value) for n, value in enumerate(orders, 1)]
    return merge_after.division_order(store.db(), parent, config.DEFAULT_TARGET,
                                      parts)


def test_successor_of_two_tops_is_greater_number(light_transition):
    """Части 1 и 2 обе «после части 3», часть 3 первая: от последней по номеру зависят обе, ни от одной не зависит никто — преемник часть 2 (больший номер).

    Ловит мутацию: из нескольких верхних частей берётся первая
    (`min` вместо `max`) — преемником становится часть 1.
    """
    parent = new_task("Родитель")
    found, reasons = order(parent, ["после части 3", "после части 3", FIRST])
    assert reasons == []
    assert found.deps == [[2], [2], []]
    assert found.successor == 1


def test_successor_is_last_when_nobody_depends_on_it(light_transition):
    """Части 1 и 3 первые, часть 2 «после части 3», часть 4 «после части 1»: от части 4 не зависит никто — преемник она, хотя часть 2 тоже ни у кого не в зависимостях; часть 3 — нецепочка.

    Ловит мутацию: преемник выбирается среди всех частей, от которых не
    зависит никто, без условия «зависит от последней» и с наименьшим
    номером — выбрана часть 2.
    """
    parent = new_task("Родитель")
    found, reasons = order(parent, [FIRST, "после части 3", FIRST,
                                    "после части 1"])
    assert reasons == []
    assert found.successor == 3
    assert found.loose == [3]


def test_repeated_part_and_empty_list_refused(light_transition):
    """«после части 1, части 1» и «после» без перечня — отказ, называющий часть и элемент.

    Ловит мутацию: повтор «части N» не отсеивается (дубль ребра молча
    принимается); «после» без элементов читается как «без зависимостей».
    """
    parent = new_task("Родитель")
    found, reasons = order(parent, [FIRST, "после части 1, части 1"])
    assert found is None
    assert any("часть 2" in r and "«части 1» указан повторно" in r
               for r in reasons), reasons
    found, reasons = order(parent, [FIRST, "после"])
    assert found is None
    assert any("часть 2" in r and "без элементов" in r for r in reasons), (
        reasons)


def test_parent_prefix_is_dead_dependency(light_transition):
    """Однозначный префикс id родителя в «Порядок: после …» — отказ мёртвой зависимости, как и полный id.

    Ловит мутацию: родитель узнаётся только по полному id — префикс
    проходит `check` как живая задача.
    """
    parent = new_task("Родитель")
    others = [r["id"] for r in store.all_tasks(store.db()) if r["id"] != parent]
    length = next(n for n in range(1, len(parent))
                  if not any(o.startswith(parent[:n]) for o in others))
    found, reasons = order(parent, [FIRST, f"после {parent[:max(length, 8)]}"])
    assert found is None
    assert any("мёртвая зависимость" in r for r in reasons), reasons


@pytest.mark.parametrize("raw, value", [
    (None, None), ("$30", 30.0), ("30,5", 30.5),
    (f"${config.ROLE_BUDGET_CAP:.2f}", config.ROLE_BUDGET_CAP)])
def test_division_frame_accepts(raw, value):
    """Нет поля — без рамки; «$N», «N» с запятой и ровно потолок ролей — сумма.

    Ловит мутацию: `$` не снимается до `spend.cli_number`; граница
    сравнивается `>=`.
    """
    assert guard.division_frame(raw) == (value, "")


@pytest.mark.parametrize("raw", ["", "$", "-5", "$nan"])
def test_division_frame_refuses_empty_and_non_positive(raw):
    """Пустое поле, голый «$», отрицательная сумма и nan — отказ.

    Ловит мутацию: пустое «Рамка:» приравнено к отсутствию поля;
    проверка «≤ 0» снята.
    """
    value, refused = guard.division_frame(raw)
    assert value is None and refused
