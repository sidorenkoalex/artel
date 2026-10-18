---
task: 01M58FNWBV25FF26E7AZ9Q9912
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: G1а (часть 1) — компоненты проекта в записи targets.yaml: схема, profile_of, выбор по путям

## Подход
Схема `components:` проверяется в `targets.check` отдельной функцией
`_check_components` рядом с `_check_profile`: таблица видов полей компонента
`COMPONENT_FIELDS` (прежние подполя профиля — тех же видов, кроме `report` с
перечнем `COMPONENT_REPORTS` и `install`/`checks_local` вида «одна команда»)
плюс новые виды (`path_template`, `regexes`, `masks`, `repo_paths`,
`paths_source`, `depends_on`, `tools`). `_check_profile` и
`_profile_value_error` не меняются — тексты `test_profile` прежние
(требование 4). Отказ компонента: `<targets>: target '<имя>': компонент
'<компонент>': поле '<поле>' — <причина>`.

Отказ до G1б — подкласс `targets.ComponentsPending(TargetsError)` с причиной
`targets.MULTI_COMPONENT_PENDING`: `full_suite_limit` и `_task_own_profile`
бросают `TargetsError` (вызывающим — прежний вид), а `drop_from_code_copy`
перехватывает только подкласс — ширина перехвата ровно «отказ с признаком
`multi`» (требование 10, AC-9).

`repo_context.profile_of`: `ProfileAnswer.multi: bool = False`; запись с
одним компонентом — PRESENT с подполями компонента из `PROFILE_FIELDS`
(без обязательного подполя — UNREAD, причина называет компонент и подполе),
с несколькими — UNREAD `multi=True`. `decide` для `multi` пишет причину с
полем `components`; прочие тексты прежние.

`project_profile`: `Component(name, fields)`, `components`,
`select_components`, `test_id`, `parse_test_id`. Выбор при пустом наборе
путей у записи с несколькими компонентами — все компоненты (консервативно:
SPEC этот случай не называет, пустой выбор означал бы «ничего не гонять»).

## Шаги
1. `targets.py`: `COMPONENTS_FIELD`, `COMPONENT_FIELDS`, `COMPONENT_REPORTS`,
   `ComponentsPending`, `MULTI_COMPONENT_PENDING`, `_check_components`,
   отказ записи с `test_profile` и `components:` сразу.
2. `repo_context.py`: `ProfileAnswer.multi`, чтение `components:` в `profile_of`.
3. `project_profile.py`: текст отказа `multi` в `decide`; `Component`,
   `components`, `select_components`, `test_id`, `parse_test_id`.
4. `acceptance.py`: `_task_own_profile` бросает `ComponentsPending` на
   UNREAD с `multi`; `drop_from_code_copy` перехватывает только его.
5. Тесты: долгоживущий файл задачи и планка (`plank-run`), тесты
   затронутых модулей; свой тест на `parse_test_id` негодной строки и
   выбор при пустом наборе; регенерация карты.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1, 2, 3 (прежний код `test_profile` не тронут) |
| 5 | 2, 3 |
| 6 | 3 |
| 7 | 3 |
| 8 | 3 |
| 9 | 2, 3 (`suite_run._profile_command` получает UNREAD с причиной) |
| 10 | 4 |
| 11 | 5 |

## Влияние на систему
- `targets.check` строже только для записей с `components:` — сегодня их в
  `targets.yaml` нет; записи с `test_profile` проходят прежний путь
  (`_check_profile` не менялся).
- `_task_own_profile` на записи с несколькими компонентами отказывает вместо
  `None` — строгость, не ослабление (ANSWER-1, п. 2); на прочих исходах
  поведение прежнее. `plank_run.py:220` и `doctor/cli.py` не перехватывают
  новый отказ — вынесено SPEC в G1б/G1а-2, до них записей с `components:`
  нет.
- Гейты, лимиты, guard и существующие тесты не меняются. Откат — revert
  merge-коммита задачи.

## Риски
- `yamlmini` молча перезаписывает повторный ключ компонента — ограничение,
  названное SPEC в «Не входит».
- Выбор при пустом наборе путей — «все компоненты» (решение плана, см.
  «Подход»).

## Предложения системе
