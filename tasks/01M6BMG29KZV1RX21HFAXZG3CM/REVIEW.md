---
task: 01M6BMG29KZV1RX21HFAXZG3CM
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: GitLab: гейт неослабления по исходам для full_suite ci — на verifying по отчёту CI отправленной головы

## Фаза A — план
- Таблица покрытия PLAN закрывает требования 1–16. Требование 16 покрыто дважды: шагом 1 и шагом 5 (ANSWER-2).
- Шаги проверяемые, размера MR. Подход переиспользует ядро `_judge_ci` и не вводит нового ядра. Конфликтов с архитектурой нет.
- «Влияние на систему» совпадает с diff: изменены два модуля и два файла `tests/`. Новый файл `tests/test_01m6bmg29kzv1rx21hfaxzg3cm_repeat_after_wait.py` появился по ANSWER-2, у него префикс задачи. Путь отката — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `outcome_integrity.py` `_outcome_integrity_gate`: для одиночного `ci` пишется запись пропуска `DEFERRED_LINE`, выписок нет. В `_components_gate` на рубеже `_IN_DEV` компоненты `ci` уходят в `outside`. Остальные рубежи `in_dev` не тронуты. |
| 2 | OK | `_verifying_refusal` → `_gate(ci=True)` → `_gate_ci` → `_judge_ci`. База — `_diff_base`, она названа явно. Мандат читается через `artifact_source.resolve`. |
| 3 | OK | Голова — `gitcmd.branch_head_sha(branch)`, та же ветка, по которой `ci.verifying_status` (`head_sha(branch, repo)`) только что дал «зелёный». Оба случая AC-9 (сжатие и pull-main) зелёные. |
| 4 | OK | `verifying_gate`: `BROKEN_REFUSAL_ACTION` ведёт в `in_dev`, кроме повтора и предела. Прочие действия (класс «чинит Оператор», сбой подготовки, отказ профиля) ведут в `escalated`. Действие и текст журнала прежние. |
| 5 | OK | Запись отказа делается после `state -> in_dev`, поэтому её видит `store.refusal_history`. AC-4 зелёный. |
| 6 | OK | `_ci_report` возвращает признак «проходящая негодность», `_Pending` отделяется от `_Prepare`. Ожидание идёт в прежнюю ветку потолка `fsm_advance.verifying`. Статусы `canceled`, `manual` и `failed` с `allow_failure` дают эскалацию сразу. |
| 7 | OK | Перезапуск во время чтения на `verifying` даёт `_Pending`. На мерже `_Pending` ловится как сбой подготовки, как прежде. AC-10 покрыт для обоих рубежей. |
| 8 | OK | Запись `PASSED_ACTION` ядра не изменилась. AC-2 зелёный. |
| 9 | OK | `artifact_source.resolve`, AC-5. |
| 10 | OK | `_components_gate(verifying=True)` перебирает все компоненты `ci`/`both`, AC-12. |
| 11 | OK | У `both` локальная часть остаётся на `in_dev`, часть по отчётам CI идёт на `verifying`. AC-13. |
| 12 | OK | В `fsm_advance.verifying` переход в `review` стоит только за `verifying_gate` без `moved`/`wait`. Проверено временной мутацией (см. ниже). |
| 13 | OK | `merge_gate_escalates` не менялся. `_Pending` — подкласс `_Prepare`, а `command` на мерже по-прежнему `approve`. |
| 14 | OK | Для `local` и артели `_verifying_refusal` возвращает `None` без записей в журнал. AC-15 зелёный. |
| 15 | OK | `test_ac9…` переписан по мандату ANSWER-1. Метод проверяет оба условия, (а) и (б), утверждения у него есть. |
| 16 | OK | `_cycle_reason`: правило повтора проверяется первым и смотрит последний отказ с находками по всей истории задачи. Предел считается по `state -> in_dev` с `RETURN_DETAIL`. Записи ожидания и сбоя подготовки повтор не прерывают (ANSWER-2). |

Тесты. Заявки «Ловит мутацию» в изменённом `test_ac9` и новом `test_repeat_after_pending_poll_escalates_as_repeat` наблюдаемы. В первом мутация «гейт не вызван» даёт `review` вместо `in_dev`. Во втором `PENDING_ACTION`, засчитанный предыдущим отказом, даёт пустой набор, причина эскалации становится «предел», и `REPEAT` не находится. Новый тест не повторяет долгоживущий файл: сценарий «ожидание между возвратом и повтором» в нём отсутствует.

Целостность. Ослабление `test_ac9…` покрыто ANSWER-1 («Ослабление тестов разрешено: …»). Строка гейта пакета говорит то же. Других изменений утверждений `tests/` нет. Защищённые пути (`gates.yaml`, `skills/`, `templates/`, `.github/`) не тронуты.

## Замечания

Замечаний уровня blocker и major нет.

- minor — `orchestrator/advance_gates/outcome_integrity.py` `verifying_gate` (ветка `PENDING_ACTION`). Каждый опрос ожидания пишет отдельную запись `PENDING_ACTION`, а рядом запись `VERIFYING_STATUS_ACTION`. Журнал растёт вдвое быстрее, чем при обычном ожидании CI. Риск заявлен в PLAN. Требований не нарушает, поэтому в реестр не заносится.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Реестр пуст: замечаний уровня blocker и major нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -p no:cacheprovider -q tests/test_01m6bmg29kzv1rx21hfaxzg3cm_repeat_after_wait.py tests/test_01m5xzskk8h096fd3cpn05bqnm_ci_outcome_gate.py` — 47 passed (40.5 с).
- `python3 -m pytest -p no:cacheprovider -q -p no:xdist tests/test_01m6bmg29kzv1rx21hfaxzg3cm_verifying_outcome_gate.py` — 45 passed (106.8 с). Запуск с `-n 4` не начался: воркеры xdist упали с «node down», тесты не собрались. Дефектом кода это не является.
- `artel.py plank-run 01M6BMG29KZV1RX21HFAXZG3CM` — 4 passed, код выхода pytest 0.
- Временная мутация в `orchestrator/fsm_advance.py`: `verdict = verifying_gate(...)` заменён на `SimpleNamespace(moved=False, wait="")`, то есть гейт не вызывается. Под ней красные `test_ac9_in_dev_gate_of_ci_component_judges_local_checkouts` и все три случая `test_ac11_review_reached_only_through_verifying_gate`: 4 failed. Код возвращён, `git status` чистый.
- `python3 scripts/codebase_map.py` — после него diff `docs/codebase-map.md` без строки `built_at_sha` пуст, карта свежая. Регенерация откачена.

## Предложения системе
- Долгоживущий файл `tests/test_01m6bmg29kzv1rx21hfaxzg3cm_verifying_outcome_gate.py` идёт 107–129 с при пороге 60 с (предупреждение пакета). Основная цена — `new_task` с настоящим выходом из `tests_writing` в каждом методе. Если такие стенды станут массовыми, стоит завести общий кэш фикстуры «задача в `verifying`» (`tests/merge_outcome_sandbox.py`).
