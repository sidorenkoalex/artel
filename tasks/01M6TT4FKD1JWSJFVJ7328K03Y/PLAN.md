---
task: 01M6TT4FKD1JWSJFVJ7328K03Y
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Источник отчёта базы для гейта исходов full_suite ci: поле ci_base компонента (main | branch)

## Подход

Источник «до» — поле записи (ADR-0031 пп. 1, 5). Без `ci_base` и при
`ci_base: main` ни один новый путь не включается: все новые ветки кода
стоят за признаком `targets.ci_base_branch(entry)` (непустое имя ветки
только при `ci_base: branch`), а тексты, записи журнала и эталон
политики прежней записи не меняются.

Ключевые решения:

- **Поля и их правила** — в загрузчике записей `targets.check`
  (`orchestrator/targets.py`): вид поля компонента (`ci_base`,
  `ci_base_branch`, `ci_base_push_options`) — в `COMPONENT_FIELDS`;
  правила записи целиком (обязательность ветки, ≠ `base`, не по шаблону
  веток задач, `base` = `config.MAIN_BRANCH`, параметры —
  `push_option_error` с `push_options_forbidden` записи, одинаковые
  значения у всех компонентов `ci_base: branch`, `ci_base` только при
  `ci`/`both`) — новой функцией после `_check_components`: она видит и
  плоскую запись слоя репозитория, и сведённую запись локального слоя.
  Читатели — `targets.ci_base_branch(entry)` и
  `targets.ci_base_push_options(entry)`.
- **Отправка базы** — одна функция `outcome_integrity._push_ci_base`:
  неблокирующий `fcntl.flock` файла `PROJECTS/<проект>/ci_base.lock`
  только на время проверки очереди и самой отправки (не `merge_lock`,
  записка 2 возврата 3); очередь — последняя запись «отчёт базы:
  отправка» задач проекта (`store.steps_of_action`): её sha держит
  очередь, пока задание `ci_job` (любого компонента записи с `ci_base:
  branch`) не `running` и не завершено, и пока запись моложе
  `config.VERIFYING_CEILING_SEC`. Отправка — `gitcmd.in_repo(<клон>,
  "push", "--force", -o …ci_base_push_options, "origin",
  "<B>:refs/heads/<ci_base_branch>", task_id=…)`: единая точка
  `_push_plan`; `policy.push_options` туда не добавляются, потому что
  refspec не ветка задачи.
- **Классификация базы** — `_ci_base_report` на неудаче поиска бросает
  подкласс `_NoBaseReport(_Prepare)` с исходом точки ответвления
  (последняя попытка задания, причина, проходящая ли). В режиме
  `branch` `_judge_ci` разбирает его: задания нет — попытка отправки и
  ожидание; задание есть и проходящая негодность — запись «отчёт базы:
  задание <id> коммита <B>» и ожидание; окончательная — та же запись и
  `_Prepare` «нет отчёта базы: <причина>» (у `canceled` — «задание
  отменено»). Ожидание — новый `_BasePending(_Pending)` → отказ с новым
  действием `BASE_PENDING_ACTION` «гейт исходов на verifying: ожидание
  отчёта CI базы»; `verifying_gate` журналирует его рядом с
  `PENDING_ACTION`, и `fsm_advance.verifying` ведёт его прежним потолком
  (текст ожидания попадает в «последний статус» эскалации). На мерже
  тот же исход — сбой подготовки с «отчёт базы ожидается, повтори
  approve».
- **Белый список и хук** — `gitcmd._whitelist_refusal`: refspec в
  `ci_base_branch` записи — `--force` допустим, только если все refspec
  отправки идут в неё; источник — явный sha/ветка и предок свежего sha
  `<base>` в `origin` (`fetch_ref_sha(..., tracking_refs=False)` +
  `is_ancestor`). Эталон политики дописывает `ci_base_branch=<ветка>`
  только при `ci_base: branch`; хук пропускает ровно эту ветку для sha —
  предка `refs/remotes/origin/<base>` клона (вторая линия).
- **Ранний запуск** — `fsm_advance.tests_writing` после `set_state ->
  in_dev`: одна попытка `outcome_integrity.early_base_push`; любой сбой
  — запись журнала, переход не трогается.
- **`doctor`** — строка `project-ci-base-<проект>-<компонент>` в
  `component_checks`: защиты хостинга (`forge.protections`, совпадение
  по маске), у `target-human` — ключ `ci_base_branch=` в файле политики
  клона; `ok` либо `warn` с причиной.

Объём совпадает с оценкой SPEC (шесть модулей, хук, карта, тесты) —
`budget_usd` не переоцениваю.

## Шаги

1. `targets.py`: поля компонента, правила записи, читатели
   `ci_base_branch`/`ci_base_push_options`.
2. `gitcmd.py` + хук `pre-push`: эталон политики с ключом
   `ci_base_branch=`, белый список (`--force` и источник по свежему
   `origin/<base>`), хук — пропуск ветки для предка `origin/<base>`.
3. `outcome_integrity.py`: `_ci_report` с последней попыткой,
   `_NoBaseReport`, `_BasePending`, отправка базы с очередью и замком,
   классификация, действие ожидания базы, отказ на мерже,
   `early_base_push`.
4. `fsm_advance.py`: ранняя отправка на выходе из `tests_writing`.
5. `doctor/project_checks.py`: строка `ci_base_branch`.
6. Карта `docs/codebase-map.md`, прогон долгоживущих тестов задачи,
   планки (`plank-run`) и тестов затронутых модулей.

Тесты: поведение покрыто долгоживущими файлами задачи
`tests/test_01m6tt4fkd1jwsjfvj7328k03y_ci_base_{gate,fields,doctor}.py`
(AC-1…AC-9, AC-13, AC-14) и планкой `acceptance_tests/test_ci_base_push.py`
(AC-10…AC-12, AC-14); своих тестов сверх них не добавляю — свойств диффа
вне их охвата нет. Прогоны шага: `plank-run` — 17 passed; три
долгоживущих файла задачи — зелёные; тесты затронутых модулей
(`test_push_hook_units`, `test_push_hook_stand`,
`test_01m5xzskk8gzteca2kwafhe029_component_fields`, `test_component_checks`,
`test_01m58pg72pg64gs790xm2ews61_doctor_components`,
`test_project_components`, `test_01m4s24963r9h18an2xdp6r15b_targets_field`,
`test_01m5xzskk8h096fd3cpn05bqnm_ci_outcome_gate`,
`test_01m6bmg29kzv1rx21hfaxzg3cm_verifying_outcome_gate`,
`test_ci_job_full_suite`) — зелёные без правки. Карта
`docs/codebase-map.md` регенерирована.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 3 |
| 3 | 3 |
| 4 | 3, 4 |
| 5 | 3 |
| 6 | 2 |
| 7 | 3 |
| 8 | 3 |
| 9 | 5 |

## Влияние на систему

- Гейт исходов `ci` (`verifying` и мерж): у записей без `ci_base`
  путь кода прежний — новые ветви только за `targets.ci_base_branch`;
  `_ci_report` возвращает те же три значения, внутренний помощник
  добавляет последнюю попытку. Fail-closed сохраняется: окончательная
  негодность базы — эскалация, проходящая — ожидание под прежним
  потолком `verifying`, на мерже — сбой подготовки без пропуска.
- Белый список отправки: расширен ровно на ветку `ci_base_branch`
  записи и только для sha — предка свежего `origin/<base>`; `--force`
  разрешён только когда все refspec отправки — в эту ветку. Прочие
  правила (отказ `base`, тегов, удалений, чужих веток, `+`-refspec,
  опций `-o` против запретов) не тронуты, тексты отказов прежние.
- Хук `pre-push` (мандат `ANSWER-1.md`): новый ключ читается
  необязательно; без него поведение побайтно прежнее, удаление и `base`
  отказываются до нового правила.
- Пульт `ci_base_branch` не удаляет: `cleanup` и `kill` не трогаются
  (удаляют только ветки задач).
- Откат — revert merge-коммита задачи; данных и схемы БД изменение не
  трогает (`store.py` не правится, записи журнала новые).

## Риски

- Очередь по журналу видит только отправки пульта; ручная отправка в
  `ci_base_branch` в обход пульта очередь не держит (не требуется SPEC).
- Отменённое задание предыдущей базы (прерываемое задание CI проекта) —
  принятый риск SPEC: отказ «задание отменено», обхода гейта нет.

## Предложения системе

- Сторож роли отказывает `pytest -n` и на перечне файлов затронутых
  модулей: `test_01m6bmg29kzv1rx21hfaxzg3cm_verifying_outcome_gate.py`
  последовательно идёт 7.5 мин и съедает заметную долю таймаута шага —
  в скиле coding-standards нет пути «параллельно, но не весь набор».

