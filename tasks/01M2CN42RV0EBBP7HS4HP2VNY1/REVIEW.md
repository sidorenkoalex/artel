---
task: 01M2CN42RV0EBBP7HS4HP2VNY1
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Рефакторинг canary.py — вынос запечатанного пула в pool_seal.py

## Гейт плана (Фаза A)

1. Покрытие требований — PLAN.md несёт таблицу «Покрытие требований»,
   все 10 требований SPEC закрыты шагами 1–7. Полно.
2. Шаги — размер MR разумный: один структурный перенос + одна разбивка
   `_run_one_task` на три фазы (явно разрешена требованием 6, не
   попутное улучшение). Проверяемые единицы, не микрооперации.
3. Подход не конфликтует с конвенциями: PLAN явно фиксирует связку
   `from .pool_seal import _pool_dir` (не `from . import pool_seal`) —
   обоснование через залоченную приёмочную планку `test_ac2_*`, что
   соответствует правилу «патчуемые имена на месте».

Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (13 функций дословно в pool_seal.py) | OK | Проверено байт-в-байт: `git show 812c9064:orchestrator/canary.py` строки 181–462 идентичны телу `orchestrator/pool_seal.py:34–313` (diff пуст, кроме двух пустых строк на границе sed-диапазона). |
| 2 (снять неиспользуемые импорты) | OK | `hashlib`/`hmac`/`struct`/`uuid`/`keychain` убраны из `canary.py`; `io` осталось и используется (`redirect_stdout(io.StringIO())`, canary.py:927). `os` стало мёртвым импортом, но SPEC требование 2 буквально называет только пять конкретных имён — `os` в списке нет, разработчик прав, что не тронул его (см. предложение системе ниже). |
| 3 (докстринг-блок заменён ссылкой) | OK | canary.py:44–47 — ссылка на `pool_seal.py`, детали формата не дублируются. |
| 4 (переключение потребителей) | OK | `artel.py`, `catalog.py`, `doctor/cli.py`, `doctor/canary_pool.py`, `doctor/__init__.py` — все пять точек переключены, проверено чтением диффа и `doctor.canary.merges_since_last_green_run` (canary_pool.py:181) — единственное оставшееся легитимное использование `doctor.canary`, не тронуто. |
| 5 (отсутствие циклов импорта) | OK | Прогнано: `python3 -c "import orchestrator.canary; import orchestrator.pool_seal; import orchestrator.catalog; import orchestrator.doctor; import orchestrator.artel"` — без ошибок. |
| 6 (разбивка `_run_one_task` на 3 фазы) | OK | Порядок побочных эффектов сверен построчно со старой версией (812c9064): print «заведена» → `store.db()` → запись `canary_runs` (с вычислением `target_sha`/`sha_label`/`verdict`) → сверка с бейзлайном/алерт отклонения → печать итога. Совпадает байт-в-байт по последовательности. Внешние сигнатуры `cmd_canary`/`cmd_pool_seal`/`restore_pool_if_missing`/`pool_drift_warning` не изменены. |
| 7 (внешнее поведение не меняется) | OK | Формат sealed/HMAC/GUID перенесён дословно (см. п.1); тексты отказов и журнала не менялись — сравнение тел функций подтверждает. |
| 8 (правка тестов — только импорты/пути патчей) | OK | Дифф `tests/test_canary.py`, `tests/test_doctor_canary_pool.py`, `tests/test_artel_role_restricted_commands.py`, `tests/test_new_argv_parsing.py` — построчно только переименование `canary.X`→`pool_seal.X` в обращениях/патчах, ни один `assert` не изменён. Два файла сверх списка SPEC (`test_artel_role_restricted_commands.py`, `test_new_argv_parsing.py`) добавлены разработчиком по тому же классу правки — это в PLAN явно объяснено (п.5) и корректно. |
| 9 (регенерация codebase-map.md) | OK | Перегнал `python3 scripts/codebase_map.py` — диф с версией в ветке только в строке `built_at_sha` (законно отстаёт/обновляется, не признак дефекта); секция `## orchestrator/pool_seal.py` присутствует, старые секции `canary.py`/`catalog.py`/`doctor/__init__.py` корректно лишились перенесённых функций/импортов в списках. Откатил тестовую регенерацию (`git checkout -- docs/codebase-map.md`) — дерево чистое. |
| 10 (не трогать перечисленное) | OK | `_ephemeral_clone`, `_drive_task`, `--sha`, `runner.in_role_environment`, `answer.py`, `prune.py` — вне диффа, подтверждено по списку изменённых файлов. |

## Замечания

Замечаний нет.

## Реестр замечаний

Пусто — первая итерация без замечаний.

## Вердикт

**approved**

## Проверено исполнением

- `python3 -c "import orchestrator.canary; import orchestrator.pool_seal; import orchestrator.catalog; import orchestrator.doctor; import orchestrator.artel"` — без ImportError (AC-8, требование 5).
- `python3 -m pytest tests/test_canary.py tests/test_doctor_canary_pool.py tests/test_artel_role_restricted_commands.py tests/test_new_argv_parsing.py -q` — 117 passed, 4 subtests passed.
- `python3 -m pytest tasks/01M2CN42RV0EBBP7HS4HP2VNY1/acceptance_tests/ -q` — 17 passed (все критерии приёмки SPEC, кроме AC-12, которая помечена `manual` с обоснованным основанием — оценка текста PLAN.md, не кода).
- `python3 -m pytest tests/test_fsm_map_regen.py -q` — 14 passed (гейт свежести карты не сломан).
- `python3 scripts/codebase_map.py` — сгенерировал карту, диф с закоммиченной версией только в `built_at_sha`; откатил (`git checkout -- docs/codebase-map.md`), дерево вернулось к чистому состоянию.
- Байт-в-байт сравнение перенесённого диапазона: `git show 812c9064:orchestrator/canary.py` (строки 181–462) против `orchestrator/pool_seal.py` (строки 34–313) — идентичны (AC-1).
- CI коммита 14300e4b — зелёный (7 проверок), заявлено пакетом ревью; полный набор `tests/` не гонял отдельно (решение Оператора 05.09 — гоняет CI).

## Предложения системе

- `orchestrator/canary.py` после переноса несёт мёртвый импорт `import os`
  (использование было только в перенесённом `_secret_fd`) — разработчик
  корректно не стал его убирать, т.к. требование 2 SPEC перечислило
  только пять конкретных имён, а правило «рефакторинг = перенос, не
  улучшение» запрещает попутную чистку. SPEC-черновики такого класса
  (перенос диапазона кода в новый модуль) стоит по умолчанию просить
  analyst формулировать требование про импорты общей фразой («убрать
  все импорты, ставшие неиспользуемыми после переноса», не перечислением
  имён) — иначе такой мёртвый импорт остаётся систематическим побочным
  продуктом ЛЮБОГО подобного переноса, и следующая задача тратит цикл на
  его уборку отдельным поводом.
