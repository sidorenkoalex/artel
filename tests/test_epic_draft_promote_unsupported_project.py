"""`epic draft promote` черновика эпика неподдержанного проекта (`forge: gitlab` или `merge_gate: target-human`) отказывает причиной `targets.unsupported_reason`: проверка стоит в `catalog.cmd_new`, а не в CLI-обёртке `new`, и путь черновика её не обходит (SPEC 01M5W27CY7K7NR9347NKD8F0NX, требование 3; решение гейта SPEC).

Песочница — `initialized_tmp_root`: `subprocess.run` подменён шпионом
`git_spy`, который записывает каждую команду процесса. Эпик и черновик
заводятся прямо в БД, команда — публичный `artel.py epic draft promote`.
Имя проекта порождается модулем `random`; зерно печатается и входит в
текст провала.
"""
import contextlib
import io
import os
import random
import sys
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import artel, config, epics, repo_context, store, targets
from tests.sandbox import artel_target_entry

LETTERS = "abcdefghijkmnopqrstuvwxyz"
# (forge, merge_gate) — две неподдержанные записи.
UNSUPPORTED = [("gitlab", "operator"), ("github", "target-human")]


def declare(name: str, forge: str, gate: str) -> None:
    text = (config.TARGETS.read_text(encoding="utf-8")
            if config.TARGETS.exists() else "targets:\n" + artel_target_entry())
    entry = (f"  {name}:\n    forge: {forge}\n"
             f"    url: https://localhost/team/{name}\n"
             f"    base: {config.MAIN_BRANCH}\n"
             f"    token_slot: {name}-token\n    no_paths: []\n"
             f"    project_skills: []\n    merge_gate: {gate}\n")
    config.TARGETS.write_text(text.rstrip("\n") + "\n" + entry, encoding="utf-8")


def cli(*args: str) -> tuple[str, int]:
    """`artel.py <args>`: (весь вывод вместе с текстом выхода, код выхода)."""
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


def table(name: str) -> list:
    return [tuple(r) for r in store.db().execute(f"SELECT * FROM {name} ORDER BY rowid")]


@pytest.mark.parametrize("forge,gate", UNSUPPORTED, ids=["gitlab", "target-human"])
def test_draft_promote_of_unsupported_project_refuses(initialized_tmp_root, forge, gate):
    """`epic draft promote` черновика эпика неподдержанного проекта: код выхода 1, в выводе — причина `unsupported_reason`; строки `tasks` не изменились, черновик остался `draft`, клона проекта нет, шпион процессов не видел ни одной команды git.

    Ловит мутацию: проверку `unsupported_reason` перенесли из
    `catalog.cmd_new` в CLI-обёртку `catalog.new_cli_target` — `promote`
    зовёт `cmd_new` мимо обёртки, доходит до клона (шпион видит git) и
    заводит задачу (строки `tasks` меняются, черновик — `promoted`);
    проверку сняли вовсе — то же.
    """
    seed = random.randrange(1 << 30)
    rng = random.Random(seed)
    name = "p" + "".join(rng.choice(LETTERS) for _ in range(7))
    declare(name, forge, gate)
    reason = targets.unsupported_reason(name)
    assert reason, f"зерно: {seed}; {name}: причины нет"
    conn = store.db()
    epic_id = epics.new_epic_id()
    store.insert_epic(conn, epic_id, name, "Эпик", "цель", None)
    number = store.insert_draft(conn, epic_id, "Черновик", "ТЗ черновика", None,
                                None, None)
    conn.commit()
    spy = initialized_tmp_root.git_spy
    before_tasks, start = table("tasks"), len(spy.calls)

    out, code = cli("epic", "draft", "promote", epics.draft_address(epic_id, number))

    note = f"зерно: {seed}; проект {name}; код {code}\n{out}"
    assert code == 1, note
    assert reason in out, note
    assert table("tasks") == before_tasks, note
    assert store.get_draft(store.db(), epic_id, number)["state"] == epics.DRAFT, note
    assert not repo_context.clone_path(name).exists(), note
    git = [list(c) for c in spy.calls[start:]
           if c and Path(os.fsdecode(c[0])).name == "git"]
    assert git == [], note
