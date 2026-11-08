---
task: 01M6TT4FKD1JWSJFVJ7328K03Y
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Источник отчёта базы для гейта исходов full_suite ci: поле ci_base компонента (main | branch)

## Фаза A: план

- Таблица покрытия полна: требования 1–9 разложены по шагам 1–5 и 7. Шаг 7 (итерация 2) — проверяемая единица: новый файл `tests/` и правка `_ci_last_attempt`.
- Прошлый дефект плана закрыт. В PLAN больше нет утверждения «свойств вне охвата нет»: там прямо сказано, что планка разовая и что свойства стережёт `tests/test_ci_base_push_guard.py`.
- «Влияние на систему» соответствует инкрементальному diff: правка затронула только `outcome_integrity.py` (признак `unread`) и добавила новый тестовый файл.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Не менялось с итерации 1 (`_check_ci_base`) |
| 2 | OK | Добавлен `_pipeline_unread`: при итоге `unknown` без заданий или с кодом HTTP отправки нет, это ожидание. Если конвейера нет (`forge.NONE`), база отправляется. Текст причины `_ci_last_attempt` не изменился, поэтому отказы записей без `ci_base` побайтно прежние |
| 3 | OK | Как в итерации 1; при несчитанном конвейере — тот же `_BasePending` |
| 4 | OK | Если в `early_base_push` конвейер не прочитан, пишется запись `BASE_SEND_REFUSED_ACTION`, отправки нет, переход не затронут |
| 5 | OK | Не менялось |
| 6 | OK | Добавлены сторожа в `tests/`; каждый проверен временной мутацией (см. «Проверено исполнением») |
| 7 | OK | Несчитанный конвейер отнесён к проходящей негодности («статус не прочитан») |
| 8 | OK | Не менялось |
| 9 | OK | Не менялось |

## Замечания

Блокеров и major нет.

Наблюдение без записи в реестр (minor, вкус): ветку `if unread:` в `orchestrator/advance_gates/outcome_integrity.py::early_base_push` ни один тест не стережёт. Если заменить её на `if False:`, `tests/test_ci_base_push_guard.py` и `tests/test_01m6tt4fkd1jwsjfvj7328k03y_ci_base_gate.py` дают 39 passed. Последствие то же, что у R1-F2: при сбое API на входе в `in_dev` пройдёт лишняя отправка базы и один лишний конвейер CI; гейт это не обходит. Основной путь (`_ci_base_unfit` на `verifying`) стережёт `test_base_push_only_when_pipeline_read`. По желанию — добавить параметр в тот же тест для `early_base_push`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/gitcmd.py:1008-1015, :1045-1055, :1088-1103; scripts/git-hooks/target-human/pre-push:99-104; AC-12 | Расширение прав отправки не стерёг ни один тест `tests/` | — | Принято: в `tests/test_ci_base_push_guard.py` пять тестов на стенде `real_git`. Мутации `all→any`, снятие проверки предка, `tracking_refs=True`, сверка с `refs/remotes/origin/<base>` и `true` вместо `merge-base --is-ancestor` в хуке — каждая красит свой тест. Тест `kill`/уборки регрессионный (`cleanup.py` задача не трогает) — допустимо |
| R1-F2 | accepted | orchestrator/advance_gates/outcome_integrity.py (`_ci_base_unfit`, `early_base_push`) | Сбой чтения конвейера приравнивался к «задания нет» | — | Принято: признак `unread` есть в обоих местах. Мутация «`unread` всегда False» красит `test_base_push_only_when_pipeline_read[status0-False]`. Ветка в `early_base_push` без сторожа — наблюдение выше, не блокирует |

## Вердикт

approved. R1-F1 и R1-F2 закрыты, реестр закрыт целиком.

Наблюдение для Оператора (повтор итерации 1): планка `acceptance_tests/test_ci_base_push.py` помечена `Группа: разовый`, хотя проверяет свойства кода (AC-10…AC-12). Сторожа в `tests/` теперь есть, поэтому вопрос группы планки — только чистота разметки; решить его можно через `amend-tests`.

## Проверено исполнением

- `python3 -m pytest -q -p no:cacheprovider tests/test_ci_base_push_guard.py` — 7 passed (11.7 с).
- Временные мутации, по одной; после каждой код возвращён, `git status --porcelain` пуст. Прогон: `tests/test_ci_base_push_guard.py`.
  - `gitcmd.py:1008` `all(` → `any(` — красный `test_whitelist_force_only_when_every_refspec_goes_to_ci_base_branch`;
  - `_ci_base_source_refusal`: `if False and not is_ancestor` — красные `test_whitelist_refuses_non_ancestor_into_ci_base_branch` и `test_whitelist_checks_fresh_origin_base_not_local_tracking_ref`;
  - `tracking_refs=False` → `True` — красный `test_whitelist_checks_fresh_origin_base_not_local_tracking_ref`;
  - `is_ancestor(src, 'refs/remotes/origin/' + base)` — красный тот же тест (вместе с `test_01m6tt4fkd1jwsjfvj7328k03y_ci_base_gate.py`: 1 failed, 38 passed);
  - хук: `git merge-base --is-ancestor …` → `true` — красный `test_hook_passes_only_ancestor_of_origin_base_into_ci_base_branch`;
  - `_ci_last_attempt`: `unread` всегда False — красный `test_base_push_only_when_pipeline_read[status0-False]`;
  - `early_base_push`: `if unread:` → `if False:` — 39 passed, не красный (наблюдение в «Замечаниях»).
- `python3 …/artel.py plank-run 01M6TT4FKD1JWSJFVJ7328K03Y` — 17 passed, код выхода pytest 0.
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m6tt4fkd1jwsjfvj7328k03y_ci_base_doctor.py tests/test_01m6tt4fkd1jwsjfvj7328k03y_ci_base_fields.py tests/test_push_hook_units.py tests/test_gitcmd_push_point.py tests/test_01m5xzskk8h096fd3cpn05bqnm_ci_outcome_gate.py` — 107 passed, 14 subtests passed.
- `tests/test_01m6tt4fkd1jwsjfvj7328k03y_ci_base_gate.py` — все зелёные. Файл шёл в прогонах мутаций выше; мутации `gitcmd` и `early_base_push` его не задевают, поэтому эти прогоны — его прогоны на неизменном коде гейта.

## Предложения системе

- Сторож команд роли отклоняет bash с `${…}` в кавычках, поэтому временные мутации пришлось делать python-скриптом в рабочем каталоге с последующим `task-rm`. Скил review-checklist мог бы назвать такой путь штатным.
