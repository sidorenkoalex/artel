# NOTE developer

## Выяснено
- Возврат с merge_gate: нужен тест на остаток требования 2 — дочерний прежнего поколения надзора занимает место. Добавлен `tests/test_epic_supervisor_units.py::PriorGenerationChildTest::test_live_child_of_prior_supervisor_takes_slot` (зовёт `auto._epic_view` напрямую, `lease.process_alive` подменён по pid).
- Мутация «отбор дочерних по started_at текущей блокировки» в `_epic_view` — тест красный; код возвращён, `orchestrator/` не менялся.
- Тесты задачи (долгоживущий + units) 50/50 зелёные; карта регенерирована (новый класс в tests/).
- Ранее: Э2а сверен; реализация — `auto.cmd_auto_epic`/`_epic_view`/`_child_holds`, `artel._launch_epic_supervisor`, `epics.py` parallel/stop/retry, `epic_supervisors`/`epic_children`.

## Не сработало
- `cat`/`ls`, `;`/`for` в Bash отказывают; `pytest -n` запрещён сторожем.

## Где остановился
- Всё сделано, PLAN.md status: ready.

## Чего не хватило
- —
