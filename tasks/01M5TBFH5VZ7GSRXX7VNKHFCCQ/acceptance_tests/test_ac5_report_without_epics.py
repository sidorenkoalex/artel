"""«report без эпиков»: доска `report` на богатой фикстуре и на пустой БД
побайтно равна эталону, снятому кодом main до правки задачи.

Группа: разовый
Зелёный с рождения: до внесения эталона тест сверяет форму доски, которую текущий `report` уже даёт (порядок колонок FSM, неизвестное состояние в конце, метки проектов, эскалация, «Задач нет»); после `amend-tests` с эталоном он держит побайтное равенство доски кода задачи виду main до правки.

Эталон — литералы `GOLDEN_BOARD`/`GOLDEN_EMPTY` ниже: их вносит сессия при
Операторе командой `amend-tests`, сняв раздел «Борд задач» файла
`.artel/report.html` кодом main до правки на этой же фикстуре (разработчик
эталон не пишет). Пока литерал `None`, тест проверяет форму доски.
Факт задачи (вид доски main до её правки), поэтому файл разовый.

Фикстура детерминирована — эталону нужен один и тот же вход: id, названия,
бюджеты и расходы — литералы. Песочница `initialized_tmp_root` без
посеянных задач; внешний проект `vega` заявлен `declare_target`, проект
`ghostproj` в `targets.yaml` не заявлен.
"""
import contextlib
import html as html_lib
import io
import re

from orchestrator import config, report, store
from tests.sandbox import declare_target

# Эталоны вносит `amend-tests` (SPEC AC-5): раздел доски между заголовком
# «Борд задач — состояния FSM» и закрывающим `</section>`.
GOLDEN_BOARD = '<div class="board"><div class="col"><div class="col-head"><span class="state-tag">spec_writing</span></div><div class="tile"><span class="tile-id">01M00000000000000000000007</span><span class="tile-title">Спека &amp; ТЗ</span><div class="tile-field">Статус: spec_writing</div><div class="tile-field">Бюджет: $25.00 · Расход: $0.10</div><div class="tile-field">Итерации ревью: 0/3</div></div></div><div class="col"><div class="col-head"><span class="state-tag">in_dev</span></div><div class="tile"><span class="tile-id">01M00000000000000000000001</span><span class="tile-title">Альфа первая</span><div class="tile-field">Статус: in_dev</div><div class="tile-field">Бюджет: $25.00 · Расход: $0.00</div><div class="tile-field">Итерации ревью: 0/3</div></div><div class="tile"><span class="tile-id">01M00000000000000000000002</span> [<span class="tile-project">vega</span>]<span class="tile-title">Бета внешняя</span><div class="tile-field">Статус: in_dev</div><div class="tile-field">Бюджет: $25.00 · Расход: $0.50</div><div class="tile-field">Итерации ревью: 1/3</div></div><div class="tile"><span class="tile-id">01M00000000000000000000003</span><span class="tile-title">Альфа вторая</span><div class="tile-field">Статус: in_dev</div><div class="tile-field">Бюджет: $25.00 · Расход: $1.25</div><div class="tile-field">Итерации ревью: 2/3</div></div></div><div class="col"><div class="col-head"><span class="state-tag">review</span></div><div class="tile"><span class="tile-id">01M00000000000000000000004</span> [<span class="tile-project">ghostproj</span>]<span class="tile-title">Призрак &lt;незаявленный&gt;</span><div class="tile-field">Статус: review</div><div class="tile-field">Бюджет: $25.00 · Расход: $3.00</div><div class="tile-field">Итерации ревью: 0/3</div></div></div><div class="col"><div class="col-head"><span class="state-tag">escalated</span></div><div class="tile"><span class="tile-id">01M00000000000000000000005</span><span class="tile-title">Эскалированная</span><div class="tile-field">Статус: escalated</div><div class="tile-field">Бюджет: $25.00 · Расход: $7.75</div><div class="tile-field">Итерации ревью: 3/3</div><div class="tile-field tile-escalation">Эскалация (из in_dev)</div></div></div><div class="col"><div class="col-head"><span class="state-tag">zz_custom_state</span></div><div class="tile"><span class="tile-id">01M00000000000000000000006</span> [<span class="tile-project">vega</span>]<span class="tile-title">Неизвестное состояние</span><div class="tile-field">Статус: zz_custom_state</div><div class="tile-field">Бюджет: $25.00 · Расход: $0.00</div><div class="tile-field">Итерации ревью: 0/3</div></div></div></div>'
GOLDEN_EMPTY = '<p class="empty">Задач нет.</p>'

BOARD_HEAD = "<h2>Борд задач — состояния FSM</h2>"
EXTERNAL = "vega"
UNDECLARED = "ghostproj"
UNKNOWN_STATE = "zz_custom_state"
# (id, проект, состояние, название, итерации ревью, эскалация из, расход)
TASKS = (
    ("01M00000000000000000000001", config.DEFAULT_TARGET, "in_dev",
     "Альфа первая", 0, None, 0.0),
    ("01M00000000000000000000002", EXTERNAL, "in_dev",
     "Бета внешняя", 1, None, 0.5),
    ("01M00000000000000000000003", config.DEFAULT_TARGET, "in_dev",
     "Альфа вторая", 2, None, 1.25),
    ("01M00000000000000000000004", UNDECLARED, "review",
     "Призрак <незаявленный>", 0, None, 3.0),
    ("01M00000000000000000000005", config.DEFAULT_TARGET, "escalated",
     "Эскалированная", 3, "in_dev", 7.75),
    ("01M00000000000000000000006", EXTERNAL, UNKNOWN_STATE,
     "Неизвестное состояние", 0, None, 0.0),
    ("01M00000000000000000000007", config.DEFAULT_TARGET, "spec_writing",
     "Спека & ТЗ", 0, None, 0.1),
)
BUDGET = 25.0


def seed_rich() -> None:
    declare_target(EXTERNAL)
    conn = store.db()
    for task_id, project, state, title, iters, escalated, spent in TASKS:
        store.insert_task(conn, task_id, title, state, f"task/{task_id.lower()}-x",
                          project, BUDGET)
        store.update_task(conn, task_id, review_iters=iters, spent_usd=spent,
                          escalated_from=escalated)


def board_section() -> str:
    with contextlib.redirect_stdout(io.StringIO()):
        report.cmd_report()
    page = (config.ROOT / ".artel" / "report.html").read_text(encoding="utf-8")
    start = page.index(BOARD_HEAD) + len(BOARD_HEAD)
    return page[start:page.index("</section>", start)]


def text_of(fragment: str) -> str:
    plain = html_lib.unescape(re.sub(r"<[^>]+>", " ", fragment))
    return re.sub(r"\s+", " ", plain).strip()


def column_heads(section: str) -> list:
    return [html_lib.unescape(s) for s in
            re.findall(r'class="state-tag">([^<]*)<', section)]


def tile_texts(section: str) -> dict:
    """{id задачи: текст её плитки}."""
    found = {}
    for chunk in section.split('<div class="tile">')[1:]:
        text = text_of(chunk)
        for task_id, *_ in TASKS:
            if text.startswith(task_id):
                found[task_id] = text
    return found


def test_ac5_rich_board_equals_golden_or_keeps_form(initialized_tmp_root):
    """Богатая фикстура без эпиков (артель и `vega`, чередование id проектов в колонке `in_dev`, задача незаявленного `ghostproj`, эскалированная, неизвестное состояние): доска равна `GOLDEN_BOARD`; до эталона — колонки в порядке FSM с неизвестным состоянием в конце, метка `[vega]` у плитки внешнего проекта, плитка `ghostproj` с его меткой, маркер «Эскалация (из in_dev)».

    Ловит мутацию: `report` из модели строит колонки только из
    `fsm.STATES` (колонка неизвестного состояния пропадает); множество
    проектов — только `targets.yaml` (задача `ghostproj` пропадает);
    карточка без `project` — метки `[vega]` нет; без `escalated_from`
    маркера эскалации нет; при эталоне — любой сдвиг разметки плитки или
    порядка карточек.
    """
    seed_rich()
    section = board_section()
    if GOLDEN_BOARD is not None:
        assert section == GOLDEN_BOARD, section
        return
    present = {state for _, _, state, *_ in TASKS}
    known = [s for s in report.STATE_ORDER if s in present]
    unknown = sorted(s for s in present if s not in report.STATE_ORDER)
    assert unknown == [UNKNOWN_STATE]
    assert column_heads(section) == known + unknown, section
    tiles = tile_texts(section)
    assert set(tiles) == {t[0] for t in TASKS}, f"плитки {sorted(tiles)}:\n{section}"
    ext = TASKS[1][0]
    assert f"[ {EXTERNAL} ]" in tiles[ext] or f"[{EXTERNAL}]" in tiles[ext], tiles[ext]
    ghost = TASKS[3][0]
    assert f"[ {UNDECLARED} ]" in tiles[ghost] or f"[{UNDECLARED}]" in tiles[ghost], \
        tiles[ghost]
    assert "Эскалация (из in_dev)" in tiles[TASKS[4][0]], tiles[TASKS[4][0]]


def test_ac5_empty_board_equals_golden_or_says_no_tasks(initialized_tmp_root):
    """Пустая БД: доска равна `GOLDEN_EMPTY`; до эталона — доска говорит «Задач нет» и не несёт ни одной колонки.

    Ловит мутацию: `report` из модели на пустой БД строит колонки всех
    состояний FSM из `columns` модели (пустые колонки вместо «Задач нет»).
    """
    section = board_section()
    if GOLDEN_EMPTY is not None:
        assert section == GOLDEN_EMPTY, section
        return
    assert "Задач нет" in section, section
    assert column_heads(section) == [], section
