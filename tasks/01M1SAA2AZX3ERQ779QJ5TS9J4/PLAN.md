---
task: 01M1SAA2AZX3ERQ779QJ5TS9J4
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: бриф роли после возврата цитирует причину возврата первым пунктом

## Подход

Раздел «Причина возврата» строится ЧТЕНИЕМ уже существующей истории
журнала `steps` (`store.task_steps`), без новых колонок и без правки
FSM-диспетчеров. Ключевое решение: «это возврат?» определяется не
текстовым паттерном `detail` (хрупко — разные вызовы reject несут
разный текст причины), а тем, ИЗ какого состояния пришла ПОСЛЕДНЯЯ
запись `state -> <текущее>` этой задачи — состояние-предшественник
читается из ближайшей более ранней записи `state -> X` в том же
журнале. Множество состояний-триггеров возврата фиксировано и
буквально повторяет перечисление требования 1 SPEC:
`{review, acceptance, verifying, merge_gate, escalated}`.

- Предшественник `review` → `review -> in_dev` по `changes_requested`
  (единственный переход review→in_dev в fsm_advance.py).
- Предшественник `acceptance`/`verifying`/`merge_gate` → `reject`
  Оператора из соответствующего состояния (fsm.py::_cmd_reject).
- Предшественник `escalated` → возврат из эскалации по `approve`
  (fsm.py::_cmd_approve, ветка `state == "escalated"`) — для ЭТОГО
  случая `detail` записи `state -> <текущее>` фиксирован
  («эскалация разрешена, продолжаем», без содержания), поэтому
  раздел вместо него берёт `detail` записи `state -> escalated`,
  ближайшей ПЕРЕД записью возврата (та, что начала именно этот цикл
  эскалации, а не более раннюю), и ссылку на `ANSWER-n.md` с
  наибольшим `n` (`_latest_answer_rel`, уже существует в brief.py).
- Любой другой предшественник (`tests_writing`, `spec_gate`, либо
  запись `state -> <состояние>` отсутствует вовсе) → визит не начат
  возвратом, раздел не строится (требование 5, AC-6).

Раздел собирается новой функцией `_return_reason_component`, общей
для всех трёх сборщиков брифа (developer/analyst/test_author) — той
же схемой рендера, что и остальные компоненты (`_manifest_component`
для developer — с описью размера; `_journal_component` для analyst/
test_author), с тем же общим `run_id` границ недоверенных данных, что
и у соседних компонентов вызова. Раздел добавляется ПЕРВЫМ элементом
списка `parts` (перед SPEC.md/картой/PLAN.md/REVIEW.md/QUESTIONS.md)
— порядок требования 3/AC-4.

Никаких изменений в `orchestrator/fsm.py`, `fsm_advance.py`,
`fsm_merge_gate.py`, `store.py` (диспетчеры и журналируемые тексты
`detail` не трогаются, SPEC «Не входит»).

## Шаги

1. `orchestrator/brief.py`: добавить константы `RETURN_REASON_HEADER`/
   `RETURN_REASON_CLOSING`, функции `_previous_state_name`,
   `_return_context`, `_return_reason_component`; подключить вызов в
   `developer_brief` (state="in_dev"), `analyst_map_component`
   (state="spec_writing"), `test_author_answer_component`
   (state="tests_writing") первым элементом собираемых частей.
2. Юнит-тесты `tests/test_brief.py`: сценарии на все три триггера
   (review→in_dev, reject из acceptance/verifying/merge_gate,
   возврат из escalated) и на отсутствие раздела (первый визит,
   штатный advance) — тем же приёмом `seed`, что использует
   `tasks/01M1SAA2AZX3ERQ779QJ5TS9J4/acceptance_tests/_sandbox.py`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |

## Влияние на систему

Зона задачи — `orchestrator/brief.py`, `tests/`. Изменение читает
журнал `steps` (уже существующие записи `state -> X`/`detail`),
ничего в нём не создаёт и не меняет формат. Риск для соседей: три
сборщика брифа (`developer_brief`/`analyst_map_component`/
`test_author_answer_component`) теперь могут добавить один
дополнительный компонент — это увеличивает объём брифа на возвратных
визитах (существующая дисциплина размера/частей `context_package`
уже обрабатывает рост объёма, отдельного лимита не требуется).
`tests/test_brief.py` без seed-истории журнала (текущие тесты) видят
`_return_context() is None` и получают прежний текст без изменений —
проверено чтением: тесты не вызывают `seed_state`/`store.journal`
с действием `state -> X` для своих задач. Откат — удаление вызовов
`_return_reason_component` из трёх сборщиков и самой функции.

## Риски

- Есть третий (кроме FSM-переходов и юнит-тестов) читатель истории
  `steps`, который мог бы завести запись `state -> escalated` без
  последующего парного возврата, — тогда `_previous_state_name` не
  находит эскалацию как непосредственного предшественника. Не
  найдено: `set_state` — единственная точка записи `state -> X`.

## Предложения системе
