---
task: 01M1SCQ6WZHMQVK1AHP9F392JZ
type: review
author_role: reviewer
status: approved
iteration: 3
schema_version: 4
---

# REVIEW: регрессия №15 — рубеж «замечания ревью не отработаны» сверяется с коммитом ревьювера, а не с последним коммитом REVIEW.md

## Контекст итерации 3

Advance итерации 2 отклонён не по содержанию MR, а механикой
«вердикт учтён по номеру итерации» (`orchestrator/fsm_advance.py:149-150`,
`t["reviewed_iter"]`): гейт `review -> verifying` требует нового прогона
ревьювера с `iteration` строго больше уже учтённого, даже когда код и
PLAN.md не менялись. Это штатный, отдельный от предмета этой задачи
механизм (сверка по номеру итерации артефакта, не по git-времени
коммита REVIEW.md) — не тот класс бага, который чинит сама задача
(там рубеж `in_dev -> review` внутри `fsm_advance.py` сверяется со
временем чужого коммита; здесь фиксированное поле `reviewed_iter` в
БД задачи, коммиты вовсе не участвуют). Отдельного замечания не
завожу.

Проверил фактическую неизменность:
- `git diff f310b4678a2a10988d66d767421d1e0c90aacdac...HEAD --stat -- orchestrator/fsm_advance.py orchestrator/auto.py tests/test_fsm_review_rework_gate.py` — пусто.
- `git diff main...HEAD --stat` — три файла: `docs/codebase-map.md`,
  `orchestrator/fsm_advance.py`, `tests/test_fsm_review_rework_gate.py`
  (см. «Проверено исполнением» — идентично тому, что видела итерация 2).
- `git merge-base --is-ancestor 03345ae1 f310b4678a2a10988d66d767421d1e0c90aacdac` —
  true: сам коммит с правкой (`03345ae1`) — предок базы инкрементального
  diff, промежуточные коммиты HEAD после `f310b467` — чужие
  «подтяжки main» (задача 01M1SG9YKB…, операторские правки
  `PROGRAM_STOP_LOSS_USD`/`MAX_PARALLEL_TASKS`/`docs/backlog.md`), не
  относящиеся к зоне этой задачи.

Итерация переисследовала SPEC/MR самостоятельно (не приняла вывод
итерации 2 на веру) — прочитан код `_reviewer_verdict_baseline` и
`_review_rework_gate_refuses` целиком, сверен префикс с
`checkpoint.py::own_commit_marker`, прогнаны все тесты заново.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (опорное время = автокоммит шага reviewer, либо запись журнала) | OK | `_reviewer_verdict_baseline` (orchestrator/fsm_advance.py:748-778): фильтр по `_REVIEWER_STEP_AUTOCOMMIT_PREFIX` (fsm_advance.py:745) сверен дословно с `checkpoint.py:535` (`own_commit_marker = f"{task_id}: артефакты шага {role} (автокоммит оркестратора"`) — при `role="reviewer"` строки совпадают посимвольно. Fallback на `store.task_steps` (actor="reviewer", action="agent run finished") подтверждён юнит-тестами `test_no_matching_commit_falls_back_to_the_journal_entry`, `test_git_not_answering_falls_back_to_the_journal_entry`. |
| 2 (OR: коммит developer в коде ИЛИ запись журнала после `state -> in_dev`, через общую функцию) | OK | fsm_advance.py:842-844 зовёт `auto._role_step_since_state_entry(conn, task_id, "in_dev", "developer")` — ту же функцию (auto.py:133), что уже использует журнальный гейт цикла (регрессия №13, auto.py:419), не независимую копию критерия (AC-4). |
| 3 (отказ называет оба момента и источник) | OK | fsm_advance.py:846-849: `detail` несёт `review_ts.isoformat()`, `baseline_source` и `code_ts_text`. Реальный вывод приёмочного прогона (см. «Проверено исполнением») содержит обе даты и слово `reviewer`. |
| 4 (правка леджера developer'ом не сдвигает опорное время) | OK | Фильтр берёт роль из текста автокоммита; `startswith(prefix)` с `role="reviewer"` не пропускает автокоммит роли `developer`, даже будучи самым свежим коммитом REVIEW.md. Покрыто юнит-тестом `test_developer_ledger_edit_commit_is_not_a_candidate` и приёмочным `test_ac2_developer_ledger_edit_does_not_move_the_baseline` — оба зелёные. |
| AC-8 (регрессия №13 не ослаблена) | OK | `git diff --stat main...HEAD` не касается `tests/test_auto_cycle.py` и `orchestrator/auto.py` — ни один из файлов не тронут. Прогнал модуль лично: 33/33 в его составе зелёные (в общем прогоне 54 теста ниже). |

Импорт `auto` в `fsm_advance.py` на уровне модуля (строка 12) не создаёт
цикла — проверил лично: `python3 -c "import orchestrator.fsm_advance; import orchestrator.auto"` проходит без ошибок (оба модуля импортируются
раздельно и совместно).

Зона диффа (`docs/codebase-map.md`, `orchestrator/fsm_advance.py`,
`tests/test_fsm_review_rework_gate.py`) укладывается в зону SPEC
(`orchestrator/fsm_advance.py, orchestrator/auto.py, tests/`); правка
`docs/codebase-map.md` — обязательный реген карты тем же коммитом
(conventions-core), не самостоятельное изменение. Регенерировал карту
локально и сравнил с закоммиченной версией без строки `built_at_sha` —
содержимое идентично (см. «Проверено исполнением»); рабочее дерево
восстановлено.

## Замечания

Новых замечаний по итогам самостоятельной перепроверки нет.

## Реестр замечаний

Пусто: единственная запись прошлых итераций (`R1-F1`) уже переведена в
`accepted` итерацией 2 (восстановима из git-истории артефактной ветки)
— код и тесты с той итерации не менялись (см. «Контекст итерации 3»),
основания пересматривать закрытие нет.

## Вердикт

approved

Требования 1-4 и AC-8 подтверждены самостоятельной проверкой кода и
свежим прогоном тестов (код не менялся со времени итерации 2, но
проверка не унаследована — перепройдена заново). Реестр замечаний
закрыт целиком. Блокеров и major-замечаний нет.

## Проверено исполнением

- `python3 -m unittest tests.test_fsm_review_rework_gate tests.test_auto_cycle tests.test_advance_guard -v` — 54 теста, все зелёные (в т.ч. все 6 юнит-тестов `_reviewer_verdict_baseline` и 12 тестов `test_auto_cycle`/`test_advance_guard`, затрагиваемых переиспользованием `_role_step_since_state_entry`).
- `python3 -m unittest discover -s tasks/01M1SCQ6WZHMQVK1AHP9F392JZ/acceptance_tests -p "test_review_rework_gate.py" -v` — 9 приёмочных тестов (AC-1..AC-7), все зелёные; реальный вывод отказа гейта в конце прогона: `замечания ревью не отработаны: нет шага developer после итерации 1 (опорное время 2026-08-01T10:00:00+00:00 — автокоммит шага reviewer; последний коммит developer 2026-07-31T10:00:00+00:00)` — обе даты и источник названы (AC-5).
- `git diff f310b4678a2a10988d66d767421d1e0c90aacdac...HEAD --stat -- orchestrator/fsm_advance.py orchestrator/auto.py tests/test_fsm_review_rework_gate.py` — пусто (зона задачи не менялась с прошлого вердикта).
- `git diff main...HEAD --stat` — только `docs/codebase-map.md` (24 строки), `orchestrator/fsm_advance.py` (118 строк), `tests/test_fsm_review_rework_gate.py` (133 строки) — совпадает с зоной SPEC, посторонних файлов нет.
- `git merge-base --is-ancestor 03345ae1376bd9cc57deab232d706dcce4313f0a f310b4678a2a10988d66d767421d1e0c90aacdac` — код 0 (true): фактический коммит с правкой — предок базы инкрементального диффа пакета, остальные коммиты HEAD (`подтяжка main`) несут чужие задачи, не эту.
- `python3 scripts/codebase_map.py`, сравнение построчно с закоммиченной версией без строки `built_at_sha` (`git diff docs/codebase-map.md` после регена показал расхождение только в этой строке) — содержимое идентично; восстановил файл `git checkout -- docs/codebase-map.md`, рабочее дерево чистое кроме материализованных `tasks/01M1SCQ6WZHMQVK1AHP9F392JZ/`.
- `python3 -c "import orchestrator.fsm_advance; import orchestrator.auto"` — импортируются без ошибок, цикла нет.
- Прочитан полный текст `_reviewer_verdict_baseline` и `_review_rework_gate_refuses` (fsm_advance.py:745-853) и сверен построчно с `checkpoint.py:535` (`own_commit_marker`) и `auto.py:133` (`_role_step_since_state_entry`) — переиспользование настоящее, не копия.

## Предложения системе

(нет — наблюдение о механике «reviewed_iter» из «Контекст итерации 3»
не повторяет уже поданные предложения итерации 2 и не тянет на
отдельный пункт: сам механизм работает по замыслу, просто требует
явного нового прогона ревьювера при неизменном коде — не дефект.)
