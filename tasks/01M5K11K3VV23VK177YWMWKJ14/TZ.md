---
task: 01M5K11K3VV23VK177YWMWKJ14
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: kill --reason: причина ликвидации задачи в записи перехода и в RETRO

# kill --reason: причина ликвидации задачи в записи перехода и в RETRO

## Факты

Находка ревизии кода 22.10 CR-2026-10-22-3 (отчёт `docs/audits/code-revision-2026-10-22.md` копии ревизии, раздел находок и «ТЗ-черновики для топ-★»; строка бэклога «kill --reason: причина ликвидации в журнале и RETRO (CR-2026-10-22-3)»). Ссылки сверены с `origin/main` bd01a928; файлы ниже между пином и `origin/main` не менялись.

- Команда `kill` разбирается в диспетчере `orchestrator/artel.py:2181`: `cleanup.cmd_kill(rest[0], confirmed="--yes" in rest[1:])` — кроме `--yes` флагов нет; строка справки — `orchestrator/artel.py:172` (`kill <id> | release <id> | …`).
- `orchestrator/cleanup.py:447` (`cmd_kill(task_id, session_id=None, *, confirmed=False)`) причины не принимает и передаёт работу в `orchestrator/cleanup.py:558` (`_cmd_kill(conn, task_id, holder_before=None)`); переход пишется с постоянной деталью `detail="kill switch"` — `orchestrator/cleanup.py:587` (`store.set_state(conn, task_id, "killed", "operator", expected_state=state, detail="kill switch")`). Отказ живому циклу без `--yes` — `orchestrator/cleanup.py:434` (`_refuse_live_cycle`), его текст называет `kill <id> --yes`.
- RETRO ликвидированной задачи строит `orchestrator/retro.py:619` (`build_killed`); причина — деталь последней записи `state -> killed`: `orchestrator/retro.py:666` (`_last_step_detail`); строка «Итог: killed — причина: {reason}» — `orchestrator/retro.py:671`. RETRO ликвидации строится при коммите закрытия — `orchestrator/snapshot.py:62` (`build_killed`). Следовательно, причина, записанная в деталь перехода, попадёт в RETRO без правки `retro.py` и `snapshot.py`.
- Готовый разбор флага `--reason` есть: `orchestrator/artel.py:1801` (`_reason_arg(rest)` — `None`, если флага нет; пустая строка возвращается как есть; флаг без значения — отказ «--reason требует основание следующим аргументом.»). Им пользуются `amend-tests` и `ci-rerun`.
- Вызывающие `cmd_kill` вне зон — канарейка: `orchestrator/canary.py:1396`, `:1416`, `:1610`, `:1689` (вызовы `cleanup.cmd_kill(task_id)` без флагов, результат не используют). Подпись с новым необязательным именованным параметром их не ломает.
- `cmd_kill` и `_cmd_kill` сейчас ничего не возвращают; перешёл ли вызов в `killed` или задача уже была терминальной, знает только `_cmd_kill` (флаг `won`, `orchestrator/cleanup.py:583`–`591`).
- Диспетчер вычисляет `confirmed` как `"--yes" in rest[1:]`, поэтому `kill <id> --reason --yes` сегодня дал бы `_reason_arg` значение `--yes` и одновременно подтверждение `--yes`.
- Существующие тесты, закрепляющие деталь «kill switch» по умолчанию: `tests/test_kill_cleanup.py`, `tests/test_retro.py`, `tests/test_retro_artifact_branch_reads.py`, `tests/test_snapshot_closing_outcome.py`, `tests/test_canary.py` — поэтому без флага деталь остаётся прежней побайтно.
- Наблюдение ревизии (SQL по журналу, 30.09–22.10): 24 перехода `state -> killed`, из них 8 — деление задачи, 16 — «kill switch» без причины ($197.67); у 11 из 16 причина есть только в ручных строках `docs/backlog.md`, вне БД.

## Требуется

1. `kill <id> [--yes] [--reason "<текст>"]`: диспетчер `orchestrator/artel.py` передаёт значение флага (разбор — `_reason_arg`) в `cleanup.cmd_kill(task_id, …, confirmed=…, reason=…)` новым необязательным именованным параметром `reason: str | None = None`; `cmd_kill` передаёт его в `_cmd_kill`. Порядок флагов после `<id>` произвольный.
2. С причиной деталь перехода `state -> killed` — `kill switch: <текст>`: в тексте каждый перевод строки (`\r\n`, `\n`, `\r`) заменяется одним пробелом, затем пробелы по краям обрезаются — строка «Итог:» в RETRO остаётся одной строкой. Без флага — прежняя деталь `kill switch` побайтно.
3. Подсказка без флага — одна строка `причина не записана — в следующий раз: artel.py kill <id> --reason "<текст>"`. Её печатает диспетчер `orchestrator/artel.py`, только при вызове `kill` из командной строки и только если этот вызов записал переход в `killed`: для этого `cmd_kill` возвращает `True`, если переход записан, иначе `False` (значение берётся из `_cmd_kill`). При отказе живому циклу (`_refuse_live_cycle`) и для уже терминальной задачи подсказки нет. Сам `cleanup.cmd_kill` подсказку не печатает, поэтому вызовы из `orchestrator/canary.py` (без флагов) её не выводят.
4. Отказы по причине проверяются в диспетчере или в начале `cmd_kill` — до проверки живого цикла (`_refuse_live_cycle`), до взятия lease и до любой записи в журнал; задача и её lease не меняются:
   - `--reason` с пустым или пробельным текстом — отказ «kill: --reason требует непустую причину»;
   - значение `--reason`, начинающееся с `--` (например, `kill <id> --reason --yes`), — отказ «kill: --reason требует причину следующим аргументом, а не флаг».
5. Задача уже терминальна (`done`/`killed`) — перехода нет, причина нигде не пишется, вывод прежний («уже … — kill не требуется»), уборка — как прежде.
6. Подтверждение `--yes`, отказ живому циклу (`_refuse_live_cycle`), уборка ветки, worktree и lease, коммит закрытия — без изменений. Текст отказа `_refuse_live_cycle` не меняется.
7. Справка `orchestrator/artel.py` (строка `kill <id>` в перечне команд) называет `[--yes] [--reason "<текст>"]`.
8. Тесты, детерминированные, без сети (можно подменять `cleanup._commit_closing`, `cleanup.cleanup_killed_task`, `cleanup.cleanup_project_remote`, `cleanup._refuse_unsynced_docs` и `fixation.ref_drift` — по образцу `tests/test_kill_cleanup.py`):
   - `artel.py kill <id> --reason "дубль X" --yes` через `artel.main` — деталь последней записи `state -> killed` равна `kill switch: дубль X`, а `retro.build_killed(conn, <id>)` содержит строку `Итог: killed — причина: kill switch: дубль X` (на текущем коде — красный: деталь «kill switch»);
   - `--yes --reason "дубль X"` (обратный порядок) — тот же результат;
   - без `--reason` через `artel.main` — деталь `kill switch` побайтно, в выводе подсказка требования 3;
   - без `--reason` при живом цикле и без `--yes` — отказ `_refuse_live_cycle`, подсказки требования 3 в выводе нет;
   - терминальная задача без `--reason` через `artel.main` — вывод «kill не требуется», подсказки нет;
   - прямой вызов `cleanup.cmd_kill(task_id)` без флагов (как из `canary.py`) — переход записан, подсказки в выводе нет, возвращено `True`;
   - `--reason ""` и `--reason "   "` — отказ, состояние задачи и записи журнала не изменились;
   - `--reason ""` при живом цикле без `--yes` — отказ о пустой причине; записи журнала «kill отклонён: цикл жив» нет;
   - `kill <id> --reason --yes` — отказ требования 4, задача и журнал не изменились;
   - причина с переводами строк (`"строка 1\nстрока 2"`) — деталь `kill switch: строка 1 строка 2`, строка «Итог:» в `retro.build_killed` одна;
   - терминальная задача с `--reason` — записи перехода нет, вывод «kill не требуется».
   Существующие тесты не правятся и остаются зелёными.

Зоны: orchestrator/cleanup.py, orchestrator/artel.py, tests/

Ограничение зон по смыслу: в `orchestrator/artel.py` — только разбор флагов `kill` и строка справки; в `orchestrator/cleanup.py` — только `cmd_kill` и `_cmd_kill`.

Только чтение: docs/backlog.md, orchestrator/retro.py, orchestrator/snapshot.py, orchestrator/store.py, orchestrator/lease.py, orchestrator/fixation.py, orchestrator/canary.py (вызывающий `cmd_kill` без флагов — не меняется), orchestrator/fsm.py, orchestrator/fsm_merge_gate.py (вызывающий `_commit_closing` — не меняется), orchestrator/canary_drive.py, orchestrator/liveness.py, orchestrator/workspace.py, orchestrator/watch.py (свой разбор `--reason` не меняется), orchestrator/checkpoint.py, orchestrator/advance_gates/tests_writing.py, orchestrator/doctor/ignored_artifacts.py (вызывающие `ref_drift` — не меняются), docs/operator-session.md.

Не входит: причина у ликвидаций канарейки (`canary.py`, находка CR-2026-09-30-17 — отдельная задача); обязательность `--reason` (решение Оператора, после накопления статистики); правка контракта сессии о новом флаге — строкой `note`/`doc-commit` Оператора после мержа; разбор прежних 16 ликвидаций в БД.

Бюджет: $15.
