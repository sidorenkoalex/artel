---
task: 01M290Q1VK21V0X2VKC7WS6K1K
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: note --drop, --set-state, --set-priority

## Подход
Три новых вида заметки (`drop`, `set-state`, `set-priority`) заводятся в
`orchestrator/notes.py` тем же приёмом, что уже несут `insert`/`append`:
чистая функция `_apply_*(original, key, ...) -> (new_text, section_key[,
extra])`, поиск строки — общим для `append`/`drop`/`set-state`/
`set-priority` хелпером `_find_unique_row` (вынесен из тела
`_apply_append`, используется всеми четырьмя, чтобы не тройить один и
тот же цикл "нашли 1 совпадение или отказ"), диспетчер `_build_for`
добавляет три новые ветки `request["kind"]`, `_commit_message` — три
новых формата сообщения. Само тело `_attempt` (fetch → правка → commit
→ push с повтором non-fast-forward → `_hold_pending` при отказе) не
меняется вовсе — ради этого вся правка идёт через `_build_for`/
`_commit_message`, а не отдельным циклом на каждый вид.

`_apply_drop` возвращает третьим элементом кортежа строку-наблюдение
(`" | ".join(cells)` найденной строки ДО удаления) — `_commit_message`
режет её до 80 символов для сообщения «снята: …» (AC-3). Остальные
`_apply_*` этот третий элемент не используют — `_build_for` подставляет
`None` для них, `_commit_message` смотрит на `request["kind"]`, не на
сам факт наличия `extra`.

Валидация диапазона `--set-priority` (1..4) — внутри `_apply_set_priority`,
т.е. исполняется КАЖДУЮ попытку `_attempt` до первой записи в файл и до
первого push, тем же путём, что уже несёт проверка числа колонок
`_apply_insert` (см. докстрока `_attempt`: валидационные `sys.exit`
происходят до push и не удерживаются как сетевой отказ) — не отдельная
предпроверка в `cmd_note`, чтобы не заводить второй источник истины по
диапазону.

`doctor.check_pending_notes()`/`notes.pending_notes()` не трогаются —
уже читают файлы `.artel/notes-pending/*.json` одним общим форматом
независимо от `kind` (SPEC «Не входит»); новые виды видны без правки.

## Шаги

1. `orchestrator/notes.py`: хелпер `_find_unique_row`, рефакторинг
   `_apply_append` на него, три новые функции `_apply_drop`/
   `_apply_set_state`/`_apply_set_priority`, расширение `_build_for` и
   `_commit_message`, три новых флага argparse (`--drop`, `--set-state`,
   `--set-priority`) и ветки диспетчеризации `cmd_note`.
2. `tests/test_notes.py`: юнит-тесты чистых функций нового кода
   (`_apply_drop`/`_apply_set_state`/`_apply_set_priority`,
   `_find_unique_row` через существующее поведение `_apply_append`) и
   разбора аргументов (`--drop`/`--set-state`/`--set-priority` без
   `--text`, где применимо) — тем же стилем и той же песочницей
   (`TmpRootTest`), что уже несёт файл для `insert`/`append`. Полный
   сценарий git (fetch/push/retry/hold/flush) для всех трёх видов уже
   закрыт залоченными `tasks/01M290Q1VK21V0X2VKC7WS6K1K/acceptance_tests/`
   (AC-1..AC-8) — не дублируется здесь.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (`--drop`) | 1 |
| 2 (`--set-state`) | 1 |
| 3 (`--set-priority`) | 1 |
| 4 (общий формат pending, `doctor` без правки) | 1 (не меняется — уже общий) |
| 5 (тестовый слой) | 2 (плюс залоченные acceptance_tests) |

## Влияние на систему
Правка целиком в `orchestrator/notes.py` (зона задачи) и
`tests/test_notes.py`. `_attempt`/`_hold_pending`/`pending_notes`/
`_flush_pending` — тело цикла fetch/правка/push и хранилище pending — не
меняются: три новых вида проходят через тот же путь, что и
`insert`/`append`, включая повтор non-fast-forward и удержание при
отказе сети — никакого нового класса риска гонки не добавляется.
`_apply_append` меняет форму (использует общий `_find_unique_row`
вместо своего инлайн-цикла) при неизменном внешнем поведении —
покрыто существующими `ApplyAppendTest` (tests/test_notes.py) и
`tasks/01M1VBEHTDYPK3E4RRFHWYYYW3/acceptance_tests/` (та задача, не
трогается). `doctor.py` не правится (SPEC «Не входит») — читает
`pending_notes()` уже сегодня, новые `kind` видны автоматически.
`scripts/codebase_map.py` не перегенерируется: публичная поверхность
`orchestrator/notes.py` (`cmd_note`, `pending_notes`) не меняется, только
внутренние функции модуля (карта фиксирует только публичные функции
пакета верхнего уровня, не приватные `_`-функции модуля — сверено по
существующей карте `docs/codebase-map.md`, запись `orchestrator/notes.py`
уже не перечисляет `_apply_insert`/`_apply_append`/`_build_for` и
остальные приватные функции модуля).
Откат: правка одного файла + одного тестового файла, `git revert`.

## Риски
`--set-priority` не специфицирует формат сообщения коммита (SPEC не
даёт AC на этот счёт, только на диапазон 1..4) — выбран аналогичный
`--set-state` формат «оператор: <раздел> — приоритет: <значение>»;
приёмочные тесты (AC-8) проверяют только число/порядок коммитов, не
точный текст этого конкретного сообщения — расхождение с ожиданием
Оператора возможно, но не блокирует критерии приёмки.

## Предложения системе
(пусто)
