---
task: 01M4JJJF9SCR128A0XJPT2M7QX
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Подсчёт членов группы процессов — сбой `ps` не выдаётся за пустую группу

## Фаза A — план

- Таблица покрытия PLAN полна: требования 1–7 и AC-1…AC-5 сопоставлены шагам/тестам.
- Шаги проверяемые и размером с MR (код, сторож, карта).
- Подход не противоречит архитектуре: форма сигнала сбоя — «нижняя оценка 1 по
  `killpg(pgid, 0)`» — сохраняет `int` и `> 0` закрытого `catalog.py:732`,
  вызывающие из «Только чтение» не правятся.
- Причина нуля (требование 1) установлена и воспроизводима: в окружении этого
  шага `PATH=…/.artel/venv/bin:…/pyenv/…/bin:/usr/bin:/opt/homebrew/bin` без
  `/bin`, `shutil.which('ps')` → `None` (перепроверено мной, см. ниже).
  Исправление сделано по причине (`_ps_executable` с запасными `/bin`,
  `/usr/bin`), тест `test_kills_the_leader_and_returns_a_positive_count` не тронут.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Причина (PATH роли без `/bin`) записана в PLAN «Подход»; исправление — `liveness.py::_ps_executable`. Сторож причины — `tests/test_liveness.py::GroupMemberCountPathTest`, проверен временной мутацией (красный). |
| 2 | OK | `_group_member_count`: `OSError`/`TimeoutExpired`/ненулевой код → `_group_exists(pgid)` → 1/0. Пустая группа со штатным кодом 1 `ps` → `killpg` даёт `ESRCH` → 0 (AC-4 зелёный). |
| 3 | OK | Цикл ожидания и финальная проверка идут на том же `_group_member_count`, при сбое `ps` на живой группе — 1 → `SIGKILL` после `grace_sec` (AC-1/AC-2 зелёные). |
| 4 | OK | Подсчёт до сигнала при сбое даёт 1 по сверке существования; дополнительно `max(count, 1)` после дошедшего `SIGTERM` (`liveness.py:141`). Сигнатура и `int` сохранены. Примечание без последствий: `max(count, 1)` — страховка на гонку «группа появилась между подсчётом и сигналом», ни один тест её не держит (временное удаление строки — все зелёные); поведение корректно, дефекта нет. |
| 5 | OK | Исключение наружу не выходит, тип `int`; AC-5 (`cmd_status` при каждом виде сбоя) зелёный. |
| 6 | OK | Тест зелёный в PATH роли без правки утверждений; diff `tests/test_liveness.py` — только добавления. |
| 7 | OK | `git diff 1f3a0413 -- tests/test_liveness.py` не содержит удалённых строк; существующие методы не тронуты. |

## Замечания

Нет замечаний уровня blocker/major/minor.

Проверено дополнительно:
- `_group_exists`: `PermissionError` → True (группа есть, но чужая) — согласовано с `_pid_alive`; прочий `OSError` → False — не хуже прежнего поведения.
- Новый тест в `tests/` не повторяет долгоживущий файл задачи: тот подменяет `Popen` и проверяет сбой, новый — поиск штатного `ps` вне PATH (точный счёт 2 vs нижняя оценка 1); заявка «Ловит мутацию» наблюдаема и подтверждена.
- `addCleanup` в новом тесте в порядке LIFO: сначала `terminate_process_group`, затем `leader.wait` — процесс не остаётся висеть.
- Зоны: изменены только `orchestrator/liveness.py`, `tests/test_liveness.py`, `docs/codebase-map.md` — в пределах `zones` SPEC; защищённых путей нет.
- Безопасность: `ps` ищется в PATH вызывающего и затем в системных `/bin`, `/usr/bin` — новой поверхности недоверенного ввода нет (PATH и раньше определял, какой `ps` запускается).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт

approved

## Проверено исполнением

- `python3 -c "import shutil;print(shutil.which('ps'))"` в окружении шага → `None` — причина требования 1 подтверждена.
- `python3 -m pytest -q tests/test_liveness.py tests/test_01m4jjjf9scr128a0xjpt2m7qx_group_count_failure.py tests/test_catalog_status_log.py` (PATH роли без `/bin`) → `24 passed, 16 subtests passed`.
- Временная мутация M1 (`_ps_executable` без запасных `/bin`, `/usr/bin`): `tests/test_liveness.py` → `1 failed, 5 passed`, красный ровно `GroupMemberCountPathTest::test_counts_members_exactly_when_ps_is_not_on_path`. Код возвращён.
- Временная мутация M2 (ненулевой код `ps` → `return 0`): долгоживущий файл → `2 failed` (subtests `exit_1_silent`, `exit_2_stderr` в `test_ac2_…`). Код возвращён.
- Временная мутация M3 (удалён `max(count, 1)`): `tests/test_liveness.py` + долгоживущий файл → `11 passed` — строка не охраняется тестом (см. примечание к требованию 4). Код возвращён; `git status --short` — чисто.
- `python3 scripts/codebase_map.py` → отличие от закоммиченной карты только в строке `built_at_sha` — карта свежая; регенерация откачена.
- `python3 …/orchestrator/artel.py plank-run 01M4JJJF9SCR128A0XJPT2M7QX` → «планки нет: … нет файлов test_*.py; pytest не запускался» (у задачи только долгоживущий файл, прогнан выше).
- CI коммита 3426ab8c — зелёный (16 проверок, по пакету).

## Предложения системе

- `orchestrator/runner.py::role_env` собирает PATH роли без `/bin` — то же наблюдение, что в PLAN; любой голый вызов `/bin`-утилит (`ps`, `ls`, `kill`…) из кода пульта в шаге роли тихо деградирует. Стоит отдельной задачей либо добавить `/bin`, либо проверить голые вызовы.
