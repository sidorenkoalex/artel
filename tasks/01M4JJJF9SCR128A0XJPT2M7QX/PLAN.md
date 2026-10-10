---
task: 01M4JJJF9SCR128A0XJPT2M7QX
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Подсчёт членов группы процессов — сбой `ps` не выдаётся за пустую группу

## Подход

**Причина нуля (требование 1) — установлена и воспроизведена.** suite-run,
запущенный из шага роли, наследует PATH окружения роли
(`runner.role_env`, `orchestrator/runner.py:1041`): `.artel/venv/bin:…/pyenv/…/bin:/usr/bin:/opt/homebrew/bin`
— без `/bin`, а `ps` на macOS лежит только в `/bin/ps`.
`subprocess.run(["ps", …])` в `_group_member_count` падает
`FileNotFoundError` → 0 → `terminate_process_group` возвращает 0.
Воспроизведение в этом шаге (тот же PATH роли, без нагрузки, без xdist):
`python3 -m pytest tests/test_liveness.py` до правки →
`FAILED …::test_kills_the_leader_and_returns_a_positive_count — 0 not greater than or equal to 1`,
детерминированно; `python3 -c "import shutil; print(shutil.which('ps'))"` → `None`.
Отдельные зелёные прогоны 3/3 и зелёный автогейт шли из окружения с
`/bin` в PATH (сессия Оператора/пульт), поэтому падение выглядело
неустойчивым: решает окружение запуска, а не нагрузка или соседние
тесты. Тест не правится — он верен.

**Исправление по причине** (`orchestrator/liveness.py`):
1. `_ps_executable()` — `ps` ищется по PATH вызывающего с запасными
   `/bin`, `/usr/bin` (`shutil.which`); в окружении роли находится
   штатный `/bin/ps`, подсчёт снова точный.
2. `_group_member_count` различает «пусто» и «подсчёт не удался»
   (требование 2): при `OSError`/`TimeoutExpired`/ненулевом коде `ps`
   существование группы сверяется `os.killpg(pgid, 0)` (`_group_exists`,
   приём `_pid_alive` для группы): группы нет → 0 (в т.ч. штатный код 1
   `ps` на пустой группе), группа есть → нижняя оценка 1. Тип возврата
   остаётся `int`, исключение наружу не выходит — `catalog.py:732`
   (`_group_member_count(pgid) > 0`) не ломается (требование 5) и при
   сбое `ps` на живой группе показывает её живой.
3. `terminate_process_group`: после дошедшего `SIGTERM` возврат
   `max(count, 1)` — сигнал дошёл хотя бы до одного процесса
   (требование 4); цикл ожидания и `SIGKILL` работают на том же
   `_group_member_count`, который при сбое `ps` на живой группе даёт 1 —
   выжившие добиваются `SIGKILL` после `grace_sec` (требование 3).
   Сигнатуры не меняются.

Форма сигнала сбоя — «нижняя оценка 1 по сверке существования», а не
`None`/исключение: так `> 0` в закрытом `catalog.py` остаётся корректным
без правки вызывающих.

## Шаги

1. `orchestrator/liveness.py`: `_group_exists`, `_ps_executable`, новая
   ветка сбоя в `_group_member_count`, `max(count, 1)` после `SIGTERM`.
2. `tests/test_liveness.py`: новый сторож
   `GroupMemberCountPathTest::test_counts_members_exactly_when_ps_is_not_on_path`
   (группа лидер+потомок, PATH — пустой каталог → подсчёт 2). Проверен
   мутацией: без запасных `/bin`, `/usr/bin` в `_ps_executable` тест
   красный (возврат 1 вместо 2), остальные зелёные. Существующие методы
   не тронуты.
3. `python3 scripts/codebase_map.py` — карта регенерирована.

Прогоны в шаге: `python3 -m pytest tests/test_liveness.py
tests/test_01m4jjjf9scr128a0xjpt2m7qx_group_count_failure.py
tests/test_catalog_status_log.py` — 24 passed, 16 subtests passed (PATH
роли, без `/bin`). `plank-run` — планки `test_*.py` у задачи нет (только
долгоживущий файл, он в прогоне выше). Полный набор — `suite-run` №1:
«зелёный прогон», упало 0.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | Подход (причина), 1 (`_ps_executable`), 2 (сторож) |
| 2 | 1 (`_group_member_count` + `_group_exists`) |
| 3 | 1 |
| 4 | 1 (`max(count, 1)`) |
| 5 | 1 (тип `int`, без исключения) |
| 6 | 1 (тест зелёный в PATH роли без правки) |
| 7 | 2 (существующие методы не тронуты) |

| AC | Чем проверено |
|---|---|
| AC-1, AC-2 | `tests/test_01m4jjjf9scr128a0xjpt2m7qx_group_count_failure.py::FailedCountTerminateTest` — зелёный |
| AC-3, AC-4 | `…::HealthyCountTerminateTest` — зелёный |
| AC-5 | `…::FailedCountStatusTest` — зелёный |

## Влияние на систему

Затронут общий примитив снятия группы — `runner` (таймаут), `cleanup`,
`pause`, `release`, `canary`, `doctor/hung_test_watchdog`, плюс строка
`status` (`catalog.py:732`). Поведение при исправном `ps` не меняется.
При сбое `ps` на живой группе снятие теперь доходит до `SIGKILL`, а
`status` видит группу живой — строже, не слабее. Новый вызов
`os.killpg(pgid, 0)` сигнала не шлёт. Защита «не бить собственную
группу» не тронута. Гейты, лимиты, инварианты не затрагиваются. Откат —
revert коммита задачи.

## Риски

- Нижняя оценка 1 при сбое `ps` занижает число снятых для группы из
  нескольких процессов в журнале (`group_kill_detail`) — только при
  сбое `ps`, раньше там был 0.
- Группа из одного зомби-лидера, не дожатого вызывающим: `killpg(…, 0)`
  её видит — ожидание до `grace_sec` и `SIGKILL` (no-op), как и при
  штатном `ps`, который зомби тоже перечисляет.

## Предложения системе

- `runner.role_env` (`orchestrator/runner.py:1041`) собирает PATH роли без
  `/bin`: на macOS в шаге роли не находятся `ls`, `ps` и прочие утилиты
  `/bin` — любой код пульта, зовущий их голым именем из suite-run/планки
  в шаге роли, тихо деградирует. Стоит добавить `/bin` в PATH роли
  либо сверить все голые вызовы `/bin`-утилит (отдельная задача: файл
  вне зоны).
- `suite-run --wait` (`orchestrator/suite_run.py`) на зелёном полном
  прогоне ~4800 тестов печатает «прошло: 1, упало: 0» — счётчик сводки,
  похоже, считает не тесты; сводка вводит в заблуждение.
