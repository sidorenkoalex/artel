---
task: 01M290PVYG2VJK6442H5BAX9MA
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: чекпоинты пульта коммитят только зоны задачи и tasks/<id>/; на подтяжке посторонний файл — отказ, не предупреждение; гейт зон видит неотслеживаемые файлы

## Подход

Общий корень бага — `_commit_worktree_change` (`orchestrator/checkpoint.py`)
делает `git add -A` без фильтра по зонам задачи. Чиню в ОДНОМ месте
(общая обвязка), которым уже пользуются все четыре WIP-чекпоинта, а не
точечно в каждом:

- `_zone_paths(conn, task_id)` — declared `zones` + `zones_extension` +
  `config.COMMON_ZONES` + `tasks/<id>/`; пустой список, если задача не
  заявила зону вовсе (обратная совместимость со старыми задачами/
  тестовыми фикстурами — тот же приём, что уже несёт
  `fsm_advance._zones_gate`).
- `_stray_staged_paths(wt, zones)` — застейдженные пути `git diff
  --cached --name-only`, не покрытые ни одной зоной, по правилу
  вложенности `zone_lock._paths_overlap` (fail-closed на отказ git —
  `None`, не пустой список).
- `_commit_worktree_change` получает `conn`/`task_id` и новый флаг
  `refuse_on_stray`: `False` (три обычных чекпоинта, AC-1/AC-2) —
  посторонний путь снимается со стейджа и не коммитится, остальное
  коммитится как обычно, одна запись журнала на весь список; `True`
  (только `commit_pull_checkpoint`, AC-3) — коммита не происходит
  ВООБЩЕ, весь стейдж снимается.

`commit_pull_checkpoint`'s возврат (`str`) не меняю — зафиксирован
существующими `tests/test_timeout_checkpoint.py::
CommitPullCheckpointTest`. Отказ AC-3 вызывающий код
(`orchestrator/pull.py::_clean_worktree_before_merge`) читает по СВЕЖЕЙ
записи журнала `checkpoint.STRAY_WORKTREE_FILES_ACTION` (тот же приём
отсечки, что `auto._run_paused_refusal`), не по возврату функции —
`evaluate()` в этом случае возвращает `Refused(...)` вместо запуска
`git merge` (AC-4: именованная причина «посторонние файлы в worktree —
решение Оператора», тот же класс отказа, что уже узнаёт `auto`
по префиксу `REFUSAL_ACTION_PREFIX`).

`commit_step_artifacts` (AC-5) — критерий допустимости `tasks/<id>/`
первого уровня и `acceptance_tests/` переведён на прямой вызов
`guard.is_extraneous_acceptance_test_file`/`guard.
is_extraneous_task_root_file` вместо независимой копии регулярки;
`RETRO.md` — единственное добавленное исключение поверх guard (сам
белый список `TASK_ROOT_ALLOWED_MD` не трогаю — зона задачи 01M28NX43E).

`_zones_gate` (AC-6) — после `gitcmd.diff_names` (committed-дифф)
довеском мержу неотслеживаемые пути worktree (`git status --porcelain`,
новая `_untracked_worktree_paths`), fail-open на отказ ЭТОГО довеска
(committed-дифф уже fail-closed на своих отказах).

`.gitignore` (AC-7) — три новых шаблона, привязанных к корню репозитория
(`/.git-commit-msg*.txt`, `/_*.txt`, `/_*.md`).

## Шаги

1. `orchestrator/checkpoint.py`: `_zone_paths`/`_stray_staged_paths`/
   `STRAY_WORKTREE_FILES_ACTION`, новая сигнатура `_commit_worktree_
   change` (+`refuse_on_stray`), три обычных чекпоинта и
   `commit_pull_checkpoint` переведены на неё; `_is_stray_acceptance_
   test_file`/новая `_is_extraneous_task_root_file` делегируют guard.
2. `orchestrator/pull.py`: `_clean_worktree_before_merge` читает журнал
   на предмет отказа AC-3, `evaluate()` возвращает `Refused(...)` без
   `git merge`, если чекпоинт отказал.
3. `orchestrator/fsm_advance.py`: `_untracked_worktree_paths`, слияние
   с `files` в `_zones_gate` до сверки с зонами/защищёнными путями.
4. `.gitignore`: три новых шаблона.
5. Тесты: юнит-тесты новых чистых функций
   (`tests/test_checkpoint_zone_filter.py`, дополнения `tests/
   test_zones_gate.py`/`tests/test_pull.py`); залоченная планка приёмки
   `tasks/01M290PVYG2VJK6442H5BAX9MA/acceptance_tests/` покрывает AC-1
   .. AC-7 целиком через реальный git.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (фильтр по зонам во всех WIP-чекпоинтах) | 1 |
| 2 (отказ перехода на подтяжке при постороннем файле) | 1, 2 |
| 3 (белый список `commit_step_artifacts` — источник guard) | 1 |
| 4 (гейт зон видит неотслеживаемые файлы) | 3 |
| 5 (`.gitignore` — черновики ролей) | 4 |
| 6 (тесты) | 5 |

## Влияние на систему

Затронуты механизмы инвариантов #30 (`orchestrator/checkpoint.py`) и #34
(`orchestrator/fsm_advance.py`) — оба ужесточаются (фильтр по зонам,
видимость неотслеживаемых файлов), ни один не ослабляется: раньше
`git add -A` коммитил ЛЮБОЙ путь worktree (кроме `tasks/<id>/`), теперь —
только заявленные зоны; раньше гейт зон не видел неотслеживаемые файлы,
теперь видит. Обратная совместимость: задача без объявленной зоны вовсе
(`zones`/`zones_extension` оба пусты) не попадает под новый фильтр —
`_zone_paths` в этом случае отдаёт пустой список, и весь класс старых
тестов/задач без `zones` (большинство существующего набора `tests/
test_timeout_checkpoint.py`) ведёт себя байт-в-байт как раньше;
подтверждено прогоном полного набора `CommitPullCheckpointTest`/
`CommitTimeoutCheckpointTest`/`CommitAbnormalCheckpointTest`/
`CommitPauseNowCheckpointTest` без единого изменения ожидаемого
поведения. Откат — `git revert` этого коммита: обе новые проверки
дополняют существующие пути кода, не заменяют их логику для задач без
zones.

`commit_pull_checkpoint` — единственный из четырёх чекпоинтов, чей
возврат читают существующие тесты буквально как `str`
(`tests/test_timeout_checkpoint.py::CommitPullCheckpointTest`) —
контракт возврата НЕ менялся; факт отказа AC-3 читается вызывающим
кодом по журналу, не по новому полю возврата, поэтому существующие
тесты остаются в силе без правки.

`.gitignore` — новые шаблоны привязаны к корню (`/`-префикс), не влияют
на легитимные одноимённые файлы внутри `tasks/<id>/acceptance_tests/`
(AC-7 явно проверяет эту границу тестом `test_ac7_role_scratch_pattern_
does_not_reach_into_subdirectories`).

## Риски

`_untracked_worktree_paths`/`_stray_staged_paths` — дополнительные
вызовы `git status`/`git diff --cached` на каждом входе в
`in_dev -> verifying`/на каждом WIP-чекпоинте; для self-target worktree
это дешёвая локальная операция, заметного замедления не ожидаю.

## Предложения системе

`fsm_advance._answer_zones_mandate` (строка 701) разбирает маркер
`Расширение зон разрешено:` только как НАЧАЛО строки (`line.
startswith`); в ANSWER-1.md этой задачи (строки 26-27) Оператор дал
мандат прозой с переносом строки посреди неё — маркер оказался в конце
строки 26, путь `orchestrator/pull.py` — на следующей строке 27, и
`_answer_zones_mandate` на реальном тексте этого файла возвращает
пустое множество (проверено вызовом функции: `set()`). Раздел ниже
«## Расширение зон» без ДОПОЛНИТЕЛЬНОГО мандата с маркером НАЧАЛОМ
строки (например, через `zones-extend`) гейт `in_dev -> verifying` не
пропустит.

## Расширение зон

Пути: orchestrator/pull.py

Обоснование: ANSWER-1.md, п.2 — отказ подтяжки при постороннем файле
(AC-3/AC-4) реализован в `orchestrator/pull.py::_clean_worktree_before_
merge`/`evaluate`, вне заявленных зон задачи (`orchestrator/
checkpoint.py`, `orchestrator/fsm_advance.py`, `.gitignore`, `tests/`).
Мандат Оператора — ANSWER-1.md.
