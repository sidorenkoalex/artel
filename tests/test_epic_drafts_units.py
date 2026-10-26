"""Черновики эпика: свойства вне долгоживущих файлов задачи
01M5TBFCVFNN95BHH0E9C6KBKB — строка данных файла ссылки и отказ перечня,
ссылающегося на сам черновик, копия префикса ссылки эпика в CI-сценарии."""
import contextlib
import io
import sys
from unittest import mock

from orchestrator import artel, config, epics, store


def cli(*args: str) -> tuple[str, int]:
    buf = io.StringIO()
    code = 0
    with mock.patch.object(sys, "argv", ["artel.py", *args]), \
            contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            artel.main()
        except SystemExit as exc:
            code = exc.code or 0
            if isinstance(code, str):
                buf.write(f"\n{code}")
                code = 1
    return buf.getvalue(), code


def test_data_line_round_trips_and_keeps_comment_closed():
    """Строка данных файла ссылки несёт текст с `-->`, переводами строки и `\\r` и разбирается обратно в те же значения; `-->` в ней — только закрывающий.

    Ловит мутацию: `>` не экранируется — `-->` текста оказывается
    внутри строки данных до её конца; разбор теряет `\\r` или хвостовой
    перевод строки.
    """
    row = {"text": "a --> b\r\nвторая\n", "budget_usd": None, "number": 3}

    line = epics._data_line("draft", row)

    assert "\n" not in line
    assert line.count("-->") == 1 and line.endswith(" -->")
    assert epics._data_of(line + "\n# заголовок\n", "draft") == row
    assert epics._data_of(line, "decisions") is None


def test_draft_edit_refuses_self_reference(light_transition):
    """`epic draft edit E/1 --after E/1`: отказ, называющий ссылку на себя; перечни черновика не меняются.

    Ловит мутацию: адрес самого черновика принимается в его перечень —
    такой черновик не перевести никогда (`promote` ждёт сам себя).
    """
    out, code = cli("epic", "new", config.DEFAULT_TARGET, "Эпик", "--goal",
                    "Цель")
    epic_id = next(r["id"] for r in store.db().execute("SELECT id FROM epics"))
    tz = light_transition.root / "tz.md"
    tz.write_text("# Черновик\n\nТекст.\n", encoding="utf-8")
    out, code = cli("epic", "draft", "add", epic_id, "--tz", str(tz))
    assert code == 0, out

    out, code = cli("epic", "draft", "edit", f"{epic_id}/1", "--after",
                    f"{epic_id}/1")

    assert code != 0 and "ссылается на себя" in out, out
    draft = store.get_draft(store.db(), epic_id, 1)
    assert draft["merge_after"] is None and draft["start_after"] is None


def test_ci_script_epic_prefix_matches_config():
    """Префикс ссылки эпика в CI-сценарии (своя копия правила, без импорта пульта) равен `config.EPIC_REF_NAME_PREFIX`.

    Ловит мутацию: литерал `EPIC_REF_NAME_PREFIX` в `scripts/plan_appendix_ci.py`
    расходится с префиксом пульта — CI принимает ссылку эпика за задачу.
    """
    from scripts import plan_appendix_ci

    assert plan_appendix_ci.EPIC_REF_NAME_PREFIX == config.EPIC_REF_NAME_PREFIX
