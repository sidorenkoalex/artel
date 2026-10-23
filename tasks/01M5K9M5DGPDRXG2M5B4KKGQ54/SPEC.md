---
task: 01M5K9M5DGPDRXG2M5B4KKGQ54
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/pin.py, orchestrator/artel.py, tests/
budget_usd: 25
---

# SPEC: pin-update --wait-ci — ожидание CI головы main командой пульта

## Контекст
Находка ревизии CR-2026-10-22-4. `pin-update <sha>` (`orchestrator/pin.py::cmd_pin_update`)
при незавершённом или неизвестном CI головы main только отказывает
(`_refuse_unless_main_ci_green`: «пин не сдвинут, повтори, когда CI
завершится»), поэтому сессии Оператора ждут CI циклом оболочки
(`until gh run list …; sleep …`) — обходной сценарий вместо команды. Готовое
ожидание с потолком уже есть на гейте мержа
(`orchestrator/fsm_merge_gate.py::_wait_for_branch_ci_green`, константы
`config.MERGE_GATE_CI_WAIT_POLL_SEC`/`MERGE_GATE_CI_WAIT_CEILING_SEC`).
Кроме того, диспетчер (`orchestrator/artel.py`, `pin.cmd_pin_update(rest[0])`)
без аргумента падает исключением индекса вместо отказа с формой команды.

## Требования
1. Диспетчер `orchestrator/artel.py` для `pin-update <sha> [--wait-ci]`
   берёт sha — первый аргумент, не начинающийся с `--`; флаг — по наличию
   `--wait-ci`; вызывает `pin.cmd_pin_update(sha, wait_ci=…)`. У
   `cmd_pin_update` — новый именованный параметр `wait_ci: bool = False`.
2. Нет sha (`pin-update` без аргументов, `pin-update --wait-ci`) — отказ
   «pin-update: нужен полный sha main артели — artel.py pin-update <sha>
   [--wait-ci]», без `fetch` и без записи журнала, не исключение индекса.
3. Любой аргумент, начинающийся с `--`, кроме `--wait-ci`, и лишний второй
   sha — отказ «pin-update: неизвестный аргумент <арг> — artel.py pin-update
   <sha> [--wait-ci]», без `fetch` и без записи журнала.
4. Без `--wait-ci` — прежнее поведение побайтно, включая порядок проверок и
   тексты отказов `_refuse_unless_main_ci_green`.
5. С `--wait-ci` ожидание стоит на месте `_refuse_unless_main_ci_green` —
   после `fetch` и после гейта канарейки; отказ канарейки — сразу, без
   ожидания и без опроса CI.
6. Ожидание опрашивает `ci.main_line_status(sha, repo=config.ROOT)`:
   - `MAIN_GREEN` — дальше к `merge --ff-only`;
   - `MAIN_RED` — тот же отказ, что сейчас («CI коммита … красный — …; пин
     не сдвинут, сначала почини main»), без дальнейших опросов;
   - `MAIN_RUNNING` и `MAIN_UNKNOWN` — в порядке `_wait_for_branch_ci_green`:
     сначала строка вывода `[pin-update] <note> (ожидание N сек)`, затем
     проверка потолка — если `time.monotonic() - start >=
     config.MERGE_GATE_CI_WAIT_CEILING_SEC` (`start` — момент первого
     опроса), отказ «pin-update: потолок ожидания CI main истёк (N сек) —
     <последний note>; пин не сдвинут»; иначе пауза
     `time.sleep(config.MERGE_GATE_CI_WAIT_POLL_SEC)` и новый опрос. После
     последнего незелёного опроса перед отказом паузы нет.
   Неизвестный цвет зелёным не считается ни на одном опросе (инвариант 19).
7. Гейт CI в `pin-update` не ослабляется: пин сдвигается только при
   `MAIN_GREEN` на последнем опросе; `pin --to` не меняется.
8. Справка `orchestrator/artel.py` (строка перечня команд с `pin-update` и
   абзац описания `pin-update <sha>`) называет `[--wait-ci]` и его смысл
   одной фразой.
9. `orchestrator/pin.py` получает `import time` на уровне модуля; ожидание
   требования 6 вызывает паузу и часы через этот импорт (`pin.time.sleep`,
   `pin.time.monotonic`).
10. Тесты детерминированные, без сети и без реального ожидания: подменяются
    `ci.main_line_status`, `pin.time.sleep`, `pin.time.monotonic`,
    `canary.merges_since_last_green_run`, константы
    `config.MERGE_GATE_CI_WAIT_POLL_SEC` и `config.MERGE_GATE_CI_WAIT_CEILING_SEC`;
    песочницы — по образцу `tests/test_pin.py`. Подмена `pin.time.sleep`
    (тот же объект модуля `time` на весь процесс) снимается в конце каждого
    теста — контекстным менеджером или декоратором.

## Критерии приёмки
AC-1. `artel.main` с `pin-update <sha> --wait-ci`: первый опрос
`MAIN_RUNNING`, второй `MAIN_GREEN` — пин сдвинут после второго опроса,
`sleep` вызван один раз с `MERGE_GATE_CI_WAIT_POLL_SEC`, в выводе строка
«(ожидание … сек)». (На текущем коде — красный: отказ на первом опросе.)

AC-2. С `--wait-ci`: `MAIN_UNKNOWN`, затем `MAIN_GREEN` — пин сдвинут.

AC-3. С `--wait-ci`: `MAIN_RUNNING`, затем `MAIN_RED` — отказ с текстом
красного CI («CI коммита … красный — …; пин не сдвинут, сначала почини
main»), пин на месте, третьего опроса нет.

AC-4. С `--wait-ci`: всё время `MAIN_RUNNING` до потолка — отказ с текстом
«потолок ожидания CI main истёк», пин на месте.

AC-5. С `--wait-ci`, потолок: `monotonic` после второго незелёного опроса
даёт значение не меньше `MERGE_GATE_CI_WAIT_CEILING_SEC` — отказ, `sleep`
вызван ровно один раз, строка «(ожидание … сек)» напечатана дважды.

AC-6. Без `--wait-ci` и `MAIN_RUNNING` — прежний отказ «повтори, когда CI
завершится», `sleep` не вызван.

AC-7. Нет зелёного прогона канарейки и `--wait-ci` — отказ канарейки,
`main_line_status` не вызван.

AC-8. `pin-update` без аргументов и `pin-update --wait-ci` без sha — отказ
«pin-update: нужен полный sha main артели — artel.py pin-update <sha>
[--wait-ci]», не исключение индекса; `fetch` не вызван, журнал не изменился.

AC-9. `pin-update <sha> --wait` и `pin-update <sha> --wait-ci --force` —
отказ «pin-update: неизвестный аргумент <арг> — artel.py pin-update <sha>
[--wait-ci]», `fetch` не вызван, журнал не изменился.

## Оценка объёма и деление
Сработавшие сигналы: «число затрагиваемых модулей/файлов» и, вслед за ним,
«прогноз диффа не дан». Первый guard считает по всем путям
`orchestrator/*.py`, упомянутым в тексте SPEC, и здесь его поднимает перечень
файлов только для чтения из ТЗ (раздел «Не входит»). Меняются три зоны:
`orchestrator/pin.py`, `orchestrator/artel.py` (только разбор аргументов
`pin-update` и строки справки) и `tests/`.

Прогноз диффа: 12 КиБ

Обоснование монолита: делить нечего. Разбор `--wait-ci` в диспетчере
передаёт параметр `wait_ci`, у которого без ожидания в `pin.py` нет смысла,
а ожидание без разбора флага нельзя вызвать из CLI. Тесты AC-1..AC-9 проверяют
оба места через `artel.main`. Отказы без sha и с неизвестным аргументом —
та же правка разбора аргументов той же команды. Сама задача на 9 критериев
и 3 зоны.

## Не входит
- Событие CI main в `watch --exit-on` (второй вариант находки).
- Общая проверка числа аргументов для всех команд диспетчера (`amend-tests`
  без аргументов и прочие `rest[0]`) — отдельная задача.
- Новые константы ожидания для пина — берутся константы гейта мержа
  `MERGE_GATE_CI_WAIT_POLL_SEC`/`MERGE_GATE_CI_WAIT_CEILING_SEC`.
- В `orchestrator/artel.py` — ничего, кроме разбора аргументов `pin-update` и
  строк справки.
- Изменения в файлах только для чтения: `orchestrator/ci.py`,
  `orchestrator/config.py`, `orchestrator/fsm_merge_gate.py`,
  `orchestrator/canary.py`, `orchestrator/doctor/*` (в том числе
  `doctor/main_ci.py` — вызывающий `main_line_status`), `orchestrator/merge_queue.py`,
  `orchestrator/merge_lock.py`, `orchestrator/fsm.py`, `orchestrator/watch.py`,
  `orchestrator/gitcmd.py`, `orchestrator/store.py`, `docs/operator-session.md`.
- Правка памяти сессии `check-main-ci-after-merge.md` — делает сессия Оператора.
- Две фразы контракта сессии `docs/operator-session.md` о `pin-update <sha>
  --wait-ci` — вносит Оператор через `doc-commit` после мержа.
- Правка существующих тестов: они не меняются и остаются зелёными
  (зелёный полный набор `tests/` держит пульт).

## Материалы
- `docs/audits/code-revision-2026-10-22.md` (копия ревизии), находка CR-2026-10-22-4.
- Образец ожидания: `orchestrator/fsm_merge_gate.py::_wait_for_branch_ci_green`.
- ТЗ: бюджет Оператора $15–20; поставлен минимум планки $25 (skills/spec-authoring.md).
