---
task: T078
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: Отказ advance доносится до следующего запуска роли

## Гейт плана (Фаза A)

- Таблица покрытия PLAN.md полна: все 5 требований SPEC отображены на
  шаги 1-4, разрывов нет.
- Шаги — проверяемые единицы (store-функция / brief-функция / точка
  подключения в runner / тесты), не микрооперации и не «сделать всё».
- Подход не конфликтует с конвенциями: чтение `steps` только через
  `store.py` (`store.refusal_history`), не сырой SQL в `brief.py`/
  `runner.py`; журналирование компонента брифа — тем же приёмом
  `_journal_component`, что и остальные компоненты. Скоуп по состоянию
  без новой колонки БД — обоснованное решение (граница — последняя
  запись `state -> {state}`, которую `store.set_state` уже пишет на
  каждом переходе, orchestrator/store.py:504), не самопальный велосипед.
- Точка подключения — одна, после сборки `prompt`, вне разбора по
  ролям (orchestrator/runner.py:295-303) — проверено чтением: ветка
  `role == "test_author"` (orchestrator/runner.py:222-241) действительно
  не собирает `brief_text`, и единая точка после всех веток — единственный
  способ покрыть её без отдельной правки миссии test_author. План
  корректно называет это побочно чинимым пробелом.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `store.refusal_history` (orchestrator/store.py:416-444) скоупит по task_id и по границе последней записи `state -> {state}`; `brief.advance_refusal_history` (orchestrator/brief.py:192-212) кладёт `row['detail']` целиком — проверено: тексты отказов в `fsm.py` (guard_refuses:436-438, `_dirty_refuses`:468-472, трассируемость AC:770-773 и др.) несут адреса файлов/AC в `detail`, ровно он и попадает в блок без усечения. |
| 2 | OK | Рамка `orchestrator/brief.py:207-209` — «Предыдущая попытка сдать шаг отклонена вот почему — почини это:» — буквально формулировка требования 2. |
| 3 | OK | `ADVANCE_REFUSAL_LIMIT = 5` (orchestrator/brief.py:30), `matches[-limit:]` (store.py:444) — потолок применён, хронологический порядок сохранён (юнит-тест `test_limit_keeps_only_the_most_recent_entries_in_order`). |
| 4 | OK | Фильтр `task_id=?` через `task_steps` + граница по состоянию — юнит-тест `test_refusal_of_a_past_visit_is_excluded_by_the_state_marker` и `test_other_task_entries_never_appear`, приёмочный `AC3IsolationTest` (оба сценария — чужое состояние той же задачи и чужая задача) зелёные. |
| 5 | OK | Пустая история → `""` до вызова `_journal_component` (brief.py:204-205, ранний возврат — компонент даже не журналируется на чистом пути) → `runner.py:302` не трогает `prompt`. AC-2 зелёный. |

### Критерии приёмки

| AC | Вердикт | Комментарий |
|---|---|---|
| AC-1 | OK | Сценарий T069 воспроизведён реальным `fsm.cmd_advance` + реальным `runner.cmd_run`, текст журнальной записи проверен по факту попадания в собранный промпт (`tasks/T078/acceptance_tests/test_advance_refusal_reaches_next_role_run.py::AC1RefusalReachesNextRunTest`). |
| AC-2 | OK | `AC2CleanPathTest` — чистый путь, блока нет. |
| AC-3 | OK | `AC3IsolationTest` — оба сценария (чужое состояние / чужая задача). |
| AC-4 | OK (manual skip) | `tasks/T078/acceptance_tests/test_manual_criteria.py` — обоснованный skip (полный набор уже гоняет CI/merge_gate); прогнал вручную (см. «Проверено исполнением») — зелёный. |

## Замечания

(нет)

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest tests.test_advance_refusal_history -v` — 10 тестов, все зелёные (скоуп по состоянию, потолок, хронологический порядок, изоляция по задаче, рамка блока, журналирование компонента).
- `python3 -m unittest discover -s tasks/T078/acceptance_tests -v` — 4 теста (AC-1, AC-2, AC-3×2), все зелёные; AC-1 прогнан через реальный `fsm.cmd_advance` (тот же путь, что инцидент T069) и реальный `runner.cmd_run` с захватом промпта на stdin агента.
- `python3 -m unittest discover -s tests` — 980 тестов, все зелёные (AC-4, полный регресс).
- `python3 scripts/guard.py tasks/T078/SPEC.md tasks/T078/PLAN.md tasks/T078/TZ.md` — GUARD: ок (3 файлов).
- Свежесть `docs/codebase-map.md`: перегенерировал `scripts/codebase_map.py` на HEAD и сравнил содержимое (без строки `built_at_sha`) с закоммиченной картой — расхождений нет (рабочее дерево после проверки восстановлено `git checkout -- docs/codebase-map.md`, `git status` чист). Тот же критерий, что использует CI-джоба `codebase-map` (.github/workflows/ci.yml:75-80) — на этой ветке джоба не гоняется (`if: github.ref == 'refs/heads/main'`), но содержимое уже сходится, регрессии на main не будет.
- Прочитал `orchestrator/fsm.py` (участки guard_refuses, `_dirty_refuses`, `_read_branch_text_or_refuse`, ветки `tests_writing`/`in_dev`/`review`) и `orchestrator/store.py` (`set_state`, `task_steps`) целиком по месту, вне пакета — понадобилось проверить, что формат журнальной записи `"state -> {state}"` (store.py:504) и разнообразные тексты `"переход отклонён..."` в fsm.py действительно совпадают с тем, что предполагает `store.refusal_history`, а не только с тем, что описывает PLAN.

## Предложения системе

(нет)
