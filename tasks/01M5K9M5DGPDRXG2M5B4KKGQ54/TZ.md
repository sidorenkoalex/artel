---
task: 01M5K9M5DGPDRXG2M5B4KKGQ54
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: pin-update --wait-ci: ожидание CI головы main командой пульта вместо цикла оболочки

# pin-update --wait-ci: ожидание CI головы main командой пульта вместо цикла оболочки

## Факты

Находка ревизии кода 22.10 CR-2026-10-22-4 (отчёт `docs/audits/code-revision-2026-10-22.md` копии ревизии; строка бэклога «pin-update --wait-ci и проверка аргументов в диспетчере (CR-2026-10-22-4)»). Ссылки сверены с `origin/main` bd01a928; файлы ниже между пином и `origin/main` не менялись.

- `orchestrator/pin.py:96` (`cmd_pin_update`): получение origin/main, затем гейт канарейки (`canary.merges_since_last_green_run`), затем сверка CI `orchestrator/pin.py:72` (`_refuse_unless_main_ci_green`), затем перемотка пина. Цвет — `orchestrator/ci.py:1422` (`main_line_status(sha, repo=config.ROOT)`), исходы — `orchestrator/ci.py:1279`–`1282` (`MAIN_GREEN`, `MAIN_RED`, `MAIN_RUNNING`, `MAIN_UNKNOWN`). Незавершённый или неизвестный CI — только отказ «пин не сдвинут, повтори, когда CI завершится»; ожидания нет.
- Диспетчер: `orchestrator/artel.py:2235` — `pin.cmd_pin_update(rest[0])`, флагов нет; без аргумента команда падает с исключением индекса вместо отказа с формой команды. Справка — `orchestrator/artel.py:189` и описание `orchestrator/artel.py:291`.
- Готовое ожидание с потолком на гейте мержа: константы `orchestrator/config.py:178`–`179` (`MERGE_GATE_CI_WAIT_POLL_SEC = 90`, `MERGE_GATE_CI_WAIT_CEILING_SEC = 3600`); цикл `orchestrator/fsm_merge_gate.py:325` (`_wait_for_branch_ci_green`: опрос, печать «(ожидание N сек)», `time.sleep(config.MERGE_GATE_CI_WAIT_POLL_SEC)`, потолок по `time.monotonic()`, «неизвестен» — ждать дальше, красный — выход); общий потолок — `orchestrator/fsm_merge_gate.py:1567` (`_cmd_approve_merge_gate_cycle`; `deadline` вычисляется на `:1651`). Порядок внутри итерации `_wait_for_branch_ci_green`: опрос, печать строки «(ожидание N сек)», выход при зелёном или красном, затем проверка потолка (отказ), затем `time.sleep`.
- `orchestrator/pin.py:51`–`54` импортирует `sys`, `datetime` и модули пакета; модуля `time` в `pin.py` сейчас нет.
- `watch` класс событий `ci` видит только CI ветки задачи (`orchestrator/watch.py`, `_EVENT_CLASSES`), не CI main.
- Контракт сессии: `docs/operator-session.md:983` — «`pin-update` только по зелёному CI origin/main»; урок 30.09 — `docs/operator-session.md:810`–`819` (после мержа задачи — разовая проверка `gh run list --branch main --limit 3`); перечень команд — `docs/operator-session.md:156`; урок «`pin-update` — только с полным sha» — `docs/operator-session.md:761`. Правило 06.09 «обходной сценарий вместо команды — только со строкой копилки» — `docs/operator-session.md:167`–`172`; сессии ждут CI головы main циклом оболочки (`until gh run list …; sleep …`) без такой строки (ревизия: 43 цикла со словом main за 11 дней, 12 — вместе с `pin-update`).

## Требуется

1. `pin-update <sha> [--wait-ci]`: диспетчер `orchestrator/artel.py` берёт sha — первый аргумент, не начинающийся с `--`, флаг — по наличию; передаёт в `pin.cmd_pin_update(sha, wait_ci=…)` (новый именованный параметр `wait_ci: bool = False`). Нет sha — отказ «pin-update: нужен полный sha main артели — artel.py pin-update <sha> [--wait-ci]» без `fetch` и без записи журнала (вместо исключения индекса). Любой аргумент, начинающийся с `--`, кроме `--wait-ci`, и лишний второй sha — отказ с той же формой команды («pin-update: неизвестный аргумент <арг> — artel.py pin-update <sha> [--wait-ci]»), тоже без `fetch` и без записи журнала.
2. Без `--wait-ci` — прежнее поведение побайтно, включая порядок проверок и тексты отказов `_refuse_unless_main_ci_green`.
3. С `--wait-ci` ожидание стоит на месте `_refuse_unless_main_ci_green` — после `fetch` и после гейта канарейки (отказ канарейки — сразу, без ожидания). Опрос `ci.main_line_status(sha, repo=config.ROOT)`: `MAIN_GREEN` — дальше к `merge --ff-only`; `MAIN_RED` — тот же отказ, что сейчас («CI коммита … красный — …; пин не сдвинут, сначала почини main»), без дальнейших опросов; `MAIN_RUNNING` и `MAIN_UNKNOWN` — в таком порядке, как в `_wait_for_branch_ci_green`: сначала строка вывода `[pin-update] <note> (ожидание N сек)`, затем проверка потолка — если `time.monotonic() - start >= config.MERGE_GATE_CI_WAIT_CEILING_SEC` (`start` — момент первого опроса), отказ «pin-update: потолок ожидания CI main истёк (N сек) — <последний note>; пин не сдвинут»; иначе пауза `time.sleep(config.MERGE_GATE_CI_WAIT_POLL_SEC)` и новый опрос. После последнего незелёного опроса перед отказом паузы нет. Неизвестный цвет зелёным не считается ни на одном опросе (инвариант 19).
4. Гейт CI в `pin-update` не ослабляется: пин сдвигается только при `MAIN_GREEN` на последнем опросе; `pin --to` не меняется.
5. Справка `orchestrator/artel.py` (строки 189 и 291) называет `[--wait-ci]` и его смысл одной фразой.
6. В `orchestrator/pin.py` добавить `import time` на уровне модуля (сейчас его нет, `orchestrator/pin.py:51`–`54`). Ожидание требования 3 вызывает функции паузы и часов через этот импорт.
7. Тесты, детерминированные, без сети и без реального ожидания: подменяются `ci.main_line_status`, `pin.time.sleep`, `pin.time.monotonic` (через импорт требования 6; `pin.time` — тот же объект модуля `time`, поэтому подмена `pin.time.sleep` действует на весь процесс и обязана сниматься в конце каждого теста — подменой через контекстный менеджер или декоратор), `canary.merges_since_last_green_run`, константы `config.MERGE_GATE_CI_WAIT_POLL_SEC` и `config.MERGE_GATE_CI_WAIT_CEILING_SEC`; песочницы — по образцу `tests/test_pin.py`. Случаи:
   - `artel.main` с `pin-update <sha> --wait-ci`: первый опрос `MAIN_RUNNING`, второй `MAIN_GREEN` — пин сдвинут после второго опроса, `sleep` вызван один раз с `MERGE_GATE_CI_WAIT_POLL_SEC`, в выводе строка «(ожидание … сек)» (на текущем коде — красный: отказ на первом опросе);
   - `MAIN_UNKNOWN`, затем `MAIN_GREEN` — пин сдвинут;
   - `MAIN_RUNNING`, затем `MAIN_RED` — отказ с текстом красного CI, пин на месте;
   - всё время `MAIN_RUNNING` до потолка — отказ с именем «потолок ожидания CI main истёк», пин на месте;
   - без флага и `MAIN_RUNNING` — прежний отказ «повтори, когда CI завершится», `sleep` не вызван;
   - нет зелёного прогона канарейки и `--wait-ci` — отказ канарейки, `main_line_status` не вызван;
   - потолок: `monotonic` после второго незелёного опроса даёт значение не меньше потолка — отказ, `sleep` вызван ровно один раз, строка «(ожидание … сек)» напечатана дважды;
   - `pin-update` без аргументов и `pin-update --wait-ci` без sha — отказ требования 1, не исключение индекса;
   - `pin-update <sha> --wait` и `pin-update <sha> --wait-ci --force` — отказ с формой команды требования 1, `fetch` не вызван, журнал не изменился.
   Существующие тесты не правятся и остаются зелёными.

Зоны: orchestrator/pin.py, orchestrator/artel.py, tests/

Ограничение зон по смыслу: в `orchestrator/artel.py` — только разбор аргументов `pin-update` и строки справки.

Только чтение: orchestrator/ci.py, orchestrator/config.py, orchestrator/fsm_merge_gate.py, orchestrator/canary.py, orchestrator/doctor/cli.py, orchestrator/doctor/main_ci.py (вызывающий `main_line_status` — не меняется), orchestrator/doctor/canary_pool.py, orchestrator/doctor/stale_cycles.py, orchestrator/merge_queue.py, orchestrator/merge_lock.py, orchestrator/fsm.py, orchestrator/watch.py, orchestrator/gitcmd.py, orchestrator/store.py, docs/operator-session.md.

Не входит: событие CI main в `watch --exit-on` (второй вариант находки); общая проверка числа аргументов для всех команд диспетчера (`amend-tests` без аргументов и прочие `rest[0]`) — отдельная задача; новые константы ожидания для пина (берутся константы гейта мержа); правка памяти сессии `check-main-ci-after-merge.md` — делает сессия Оператора; две фразы контракта сессии `docs/operator-session.md` о `pin-update <sha> --wait-ci` вносит Оператор через `doc-commit` после мержа, как в CR3.

Бюджет: $15–20.
