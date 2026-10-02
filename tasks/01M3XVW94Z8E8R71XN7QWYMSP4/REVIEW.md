---
task: 01M3XVW94Z8E8R71XN7QWYMSP4
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Прогон планки после подтяжки main исполняет долгоживущую группу

## Фаза A — план
- Таблица покрытия полна: требования 1–5 → шаги 1–3, AC-1…AC-6 разнесены.
- Шаги размера MR: код `pull.py`, файл тестов, приложение к скилу.
- Подход совпадает с эталоном `orchestrator/advance_gates/acceptance.py:233-250`
  (`long_lived_manifest` → `sorted(digests)` при `tests_locked_sha` →
  `acceptance.run(…, extra=…)`). Импорт внутри функции разрывает цикл
  `advance_gates.acceptance → fsm → pull`, обоснование в PLAN есть. Риск
  «отказ после уже сделанного merge» назван, и его прикрывает сверка
  перечня на `in_dev → verifying`.
- Приложение к `skills/test-authoring.md` применяется: `git apply --check`
  на чистом дереве даёт rc 0 (проверил сам).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/pull.py:565-584`: тот же `acceptance_gates.long_lived_manifest` и `acceptance.run(…, extra=long_lived)`. Своего разбора перечня или глоба нет (AC-5). Целиком долгоживущая планка больше не даёт «collected 0 items» (AC-1 зелёный) |
| 2 | OK | `pull.py:568-579`: `digests is None` → `Refused`, текст «перечень долгоживущих файлов планки не прочитан после подтяжки …: <причина>», запись в журнал, прогона нет, состояние не меняется |
| 3 | OK | `{}` или нет лока → прежний вызов `acceptance.run(tdir, cwd=wt_path)` без `extra` (AC-4, две подсценки) |
| 4 | OK | Приложение-диф в PLAN: правило, причина (снимок → main → `guard --all` требует блок), инцидент 30.09; `git apply --check` rc 0 |
| 5 | OK | `tests/test_pull_long_lived_plank.py`: 4 теста AC-1…AC-4, у каждого «Ловит мутацию: …» с наблюдаемым исходом (тип исхода, состояние, `extra`, журнал). Все заявки подтверждены временными мутациями (см. ниже) |

Замечания по тестам и целостности:
- Набор тестов не ослаблен: в `tests/` только новый файл, существующие
  тесты не менялись.
- Повтора долгоживущего теста нет. В перечне задачи — только файл
  разработчика, файлов `tests/test_01m3xvw94z8e8r71xn7qwymsp4_*.py` нет.
- Группы планки обоснованы. `test_pull_long_lived_plank.py` планки помечен
  «разовый» с причиной: подмена `gitcmd` запрещена долгоживущему файлу.
  Постоянный сторож того же свойства — `tests/test_pull_long_lived_plank.py`
  (ADR-0018 п.3 соблюдён). `test_ac6_skill_appendix.py` («разовый») читает
  PLAN задачи — это факт задачи, группа верна.
- Код решает задачу в общем виде: под литералы фикстур ничего не подогнано.
- «Влияние на систему» совпадает с diff: `pull.py`, новый тест, карта.
  Файлы «только чтение» не тронуты, `skills/` правится только приложением.
- `t["target"] or config.DEFAULT_TARGET` в `pull.py:567` равносилен
  `store.task_target` у эталона.

## Замечания
Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest tasks/01M3XVW94Z8E8R71XN7QWYMSP4/acceptance_tests tests/test_pull_long_lived_plank.py tests/test_pull.py tests/test_pull_additive_conflict.py tests/test_pull_conflict_marker_states.py -p no:cacheprovider -p timeout -o timeout=120 -q`: 53 passed, 6 subtests passed. Планка зелёная целиком, включая `test_ac6_skill_appendix.py`.
- Приложение PLAN, извлечённое из блока ```diff и поданное в `git apply --check -` на чистом дереве: rc 0.
- `python3 scripts/codebase_map.py` → `git diff -- docs/codebase-map.md`: разница только в строке `built_at_sha`, содержимое карты свежее. Файл потом восстановлен.
- Временные мутации `orchestrator/pull.py` (код возвращён, `git diff` пуст), прогон только `tests/test_pull_long_lived_plank.py`:
  - прогон без `extra` — 2 failed (AC-1, AC-2);
  - `None` трактуется как пустой перечень — 1 failed (AC-3);
  - `if not green and not long_lived` — 1 failed (AC-2);
  - отказ на пустом перечне (`if not digests`) — 2 failed (подсценки AC-4).

## Предложения системе
- Связка «`long_lived_manifest` → `sorted(digests)` при лок-sha →
  `acceptance.run(extra=…)`» теперь дублируется в
  `orchestrator/advance_gates/acceptance.py` и `orchestrator/pull.py`.
  Общий помощник в `advance_gates/acceptance.py` убрал бы риск разъезда
  правила. Отдельная задача: тот файл в зоне «только чтение» этой задачи.
