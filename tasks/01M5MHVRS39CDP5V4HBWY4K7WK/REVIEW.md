---
task: 01M5MHVRS39CDP5V4HBWY4K7WK
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Обвязка «id задачи + блокировка задачи» команд — одна функция вместо семи копий

## Фаза A: план
- Таблица покрытия полна (требования 1–6 → шаг 1). Один шаг на всё оправдан
  объёмом (по три строки на команду) и обоснованием монолита в SPEC.
- Подход (функция рядом с `run_locked`, тело по имени для `(conn, id)`,
  лямбда с параметром id для добавочных аргументов) не конфликтует с
  архитектурой; передача по имени сохраняет действенность
  `mock.patch.object(<модуль>, "_cmd_…")` — глобал ищется при вызове команды.
- «Влияние на систему» совпадает с диффом: 7 модулей `orchestrator/`, новый
  файл `tests/`, карта; существующие тесты не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/lease.py:378-391`: `store.db()` → `resolve_task_id` → `return run_locked(conn, task_id, session_id, lambda sid: body(conn, task_id))`, без именованных аргументов. |
| 2 | OK | Все семь команд — один вызов `lease.run_task_command(task_id, session_id, …)`; `cmd_reject`/`cmd_ci_rerun`/`cmd_zones_extend` — лямбда `conn, tid`, id из параметра; `cmd_run` возвращает результат. Сигнатуры не тронуты. |
| 3 | OK | «ЗДЕСЬ» заменено ссылкой на `lease.run_task_command` в `cmd_reject`, `cmd_workspace`, `cmd_ci_rerun`, `cmd_run`; три прочих докстринга в диффе не меняются. |
| 4 | OK | `tests/test_lease_run_task_command.py`: (а) `test_body_gets_connection_and_full_id_run_locked_gets_full_id`, (б) `test_foreign_live_lease_refusal_matches_acquire_text` (pid — `os.getppid()`, часы `liveness` заморожены, сравнение текста целиком), (в) линтер AST с требуемой строкой «Ловит мутацию», (г) семь команд с настоящими `run_task_command`/`run_locked` и шпионом `_cmd_*`. На базе (а)–(в) красные (нет `lease.run_task_command`; копии обвязки). |
| 5 | OK | `git diff 55d469fd...HEAD -- tests/` без двух новых файлов — пусто. |
| 6 | OK | В модулях команд изменены только тела семи функций и четыре докстринга; импорты `store` остались используемыми (grep `store.` по каждому модулю — 4…83 вхождений), удалять нечего; в `lease.py` только добавление. |

## Замечания
Нет blocker/major/minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: в итерации 1 замечаний не заведено.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest tests/test_lease_run_task_command.py tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py tests/test_workspace.py tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py tests/test_task_id_prefix_regression.py tests/test_lease.py -q -p no:cacheprovider` — 108 passed, 169 subtests passed.
- `python3 -m pytest tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py tests/test_pull_conflict_marker_states.py tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py -q -p no:cacheprovider` — 66 passed, 58 subtests passed.
- `artel.py plank-run 01M5MHVRS39CDP5V4HBWY4K7WK` — 5 passed, код выхода pytest 0.
- Временная мутация 1: в `lease.run_task_command` добавлен `same_host_ok=True` → в `tests/test_lease_run_task_command.py` красные (а) и (б); код возвращён.
- Временная мутация 2: в `ci_rerun.cmd_ci_rerun` лямбда отдаёт в `_cmd_ci_rerun` внешний `task_id` → красные (в) и (г) по subTest `cmd_ci_rerun`; код возвращён, `git status --short` пуст.
- `git diff 55d469fd...HEAD -- tests/ ':!<два новых файла>'` — 0 строк (существующие тесты не тронуты).

## Предложения системе
- SPEC требования 4/AC-8 потребовал от разработчика отдельный файл `tests/` с (а)–(г), хотя долгоживущий файл test_author (`tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py`) уже держит (а)–(в): получился SPEC-узаконенный повтор, прямо противоречащий ADR-0020 п. 4. Аналитику (скил spec-writing) стоит не формулировать требование «новый тестовый файл с проверками …» в задачах, где долгоживущие тесты пишет test_author, — назначать проверки одному файлу.
