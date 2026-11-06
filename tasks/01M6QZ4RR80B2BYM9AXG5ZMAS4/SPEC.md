---
task: 01M6QZ4RR80B2BYM9AXG5ZMAS4
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/projects.py, orchestrator/artel.py, docs/codebase-map.md, tests/
budget_usd: 30
---

# SPEC: target-set — замена блока профиля или компонента из файла

## Контекст
Команда `target-set` (`orchestrator/projects.py:395`, `cmd_target_set`) правит
записи локального слоя `.artel/targets.yaml` по одному листу: значение —
скаляр или потоковый список (`_argument_value`, `:686`), путь проверяет
`_field_keys` (`:633`), форма `--key`/`--drop-key` (`_target_set_key`) пишет
ключ поля-отображения из `KEY_FIELDS` (`:380`). `_field_keys` отказывает любому
пути в `description.test_profile` и его подполях («вложенное отображение»,
`:659-672`) и компоненту, которого нет в записи (`NO_COMPONENT`, `:382`).

Перевод записи с раннера `pytest-own` на `compose`
(`targets.PROFILE_RUNNER_COMPOSE`, `orchestrator/targets.py:100`) требует
одновременно сменить `runner`, добавить поля `COMPOSE_REQUIRED` (`:110`) и
`report: junit-xml`, снять поля `COMPOSE_FORBIDDEN` (`:115`); `_check_compose`
(`orchestrator/targets.py:1239`) отказывает каждому промежуточному состоянию,
поэтому правка по одному листу невозможна, а ручная правка слоя запрещена
контрактом сессии (`docs/operator-session.md`, инцидент 04.11). Нужна форма,
заменяющая блок `test_profile` или компонента целиком из файла, через общий
путь записи `target-set` (`_target_set_load`, `_rendered`, сверка до записи,
`_backup_copy`, `_target_set_write`).

`yamlmini` не разбирает потоковые отображения `{…}`, блочные разбирает
(`yamlmini.mapping`); `_render` (`orchestrator/projects.py:254-274`) пишет
`dict` блоком и отказывает ключам, которые не записать.

## Требования

1. **Новая форма**: `target-set <проект> <путь блока> --from-file <файл>`.
   Третий аргумент `--from-file` — всегда новая форма; если при этом число
   аргументов не равно четырём — отказ со строкой `TARGET_SET_USAGE`, слой не
   записан.
2. **Путь блока** — ровно один из двух видов:
   - `description.test_profile`;
   - `description.components.<имя>` — компонент, который в записи уже есть,
     или новый (имя — непустая строка, которую `_render` может записать
     ключом).

   Любой другой путь — отказ с перечнем двух допустимых видов; слой не
   записан.
3. **Файл** — блочное отображение подмножества `yamlmini`: содержимое блока
   без ключа пути (первая строка — поле блока, например `runner: compose`).
   Отказ с причиной, слой не записан, если: файл не прочитан или не UTF-8;
   ошибка разбора `yamlmini`; разобранное значение — не отображение или
   пустое; в файле есть строка-комментарий (тот же признак, что
   `_comment_line`, `orchestrator/projects.py:610`); значение содержит то,
   что `_render` не записывает.
4. **Замена целиком**: значение по пути блока заменяется разобранным
   отображением целиком — поля, которых нет в файле, из блока уходят.
   Прочие поля записи и прочие записи слоя не меняются.
5. **Сверка до записи** — новая функция рядом с `_target_set_mismatches`
   (поведение `_target_set_mismatches` для прежних форм не меняется): все
   изменённые, добавленные и снятые листы разобранного нового текста лежат
   под `targets.<проект>.<путь блока>`; значение по этому пути после разбора
   равно значению файла (`_differences`); `_merge_mismatches` проходит —
   сведённая запись проекта годна для `targets.merge_local`, сведённые
   записи прочих проектов равны прежним. Отказ любой из проверок — текст
   причины (в том числе отказ `merge_local`, например правил `compose`),
   слой побайтно прежний, копии нет.
6. **Тот же хвост**: копия прежнего файла и запись журнала — через
   `_target_set_write`. Строка журнала и вывода:
   `<путь блока>: блок из <файл> (листов было <N> → стало <M>)`, для нового
   компонента — `было (нет)`. Блок уже равен значению файла — вывод «без
   изменений», копии и записи журнала нет. Отказы `_target_set_load`
   (проект артели, записи нет в слое, строка-комментарий в слое) действуют
   и для новой формы; недоступный журнал — отказ до записи, как у прежней
   формы.
7. **Прежние формы не меняются**: `target-set <проект> <путь> <значение>`,
   `--key`, `--drop-key`, `--show` и их тексты отказа — побайтно прежние,
   включая отказ «вложенное отображение» для
   `description.test_profile.<поле>` и `NO_COMPONENT` для прежней формы.
8. **Справка**: `TARGET_SET_USAGE` (`orchestrator/projects.py:370`) и строки
   справки `target-set` в `orchestrator/artel.py` (`:197-200`) называют новую
   форму; каждая альтернатива начинается словом `target-set`, строки
   продолжения — с отступом больше двух пробелов (иначе краснеет
   `tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py::…::test_ac4_every_command_word_of_help_is_a_registry_key`).
   `docs/codebase-map.md` — только повторной генерацией
   `scripts/codebase_map.py`.

## Критерии приёмки

AC-1. Given вымышленная запись с `test_profile` раннера `pytest-own` и файл
блока с `runner: compose`, всеми полями `COMPOSE_REQUIRED`, `workdir` под
левой частью `compose_mount` и `report: junit-xml`, When
`target-set <проект> description.test_profile --from-file <файл>`, Then
`targets.target(<проект>)["test_profile"]` равно отображению файла, поля
прежнего профиля, которых нет в файле, сняты, прочие разделы записи и
прочие записи побайтно прежние; создана копия прежнего файла и запись
журнала по формату требования 6
(`description.test_profile: блок из <файл> (листов было <N> → стало <M>)`).

AC-2. Given тот же файл без `compose_mount`, When та же команда, Then отказ с
текстом проверки `compose` про отсутствующее поле, слой побайтно прежний,
копии нет.

AC-3. Given запись с компонентами, When `--from-file` на новый компонент
`description.components.<новое имя>`, Then компонент добавлен, прочие
компоненты целы, строка журнала несёт `было (нет)`; When `--from-file` на
существующий компонент, Then он заменён целиком (поля, которых нет в файле,
сняты).

AC-4. Given путь `policy.no_paths`, `description.test_profile.runner` или
`machine.submodule_tokens` с `--from-file`, When команда, Then отказ с
перечнем двух допустимых видов пути, слой побайтно прежний.

AC-5. Given файл с ошибкой разбора, пустой, со списком вместо отображения, со
строкой-комментарием или несуществующий, When команда, Then отказ с
причиной, слой побайтно прежний, копии нет.

AC-6. Given повтор той же команды на уже применённом файле, When команда,
Then вывод «без изменений», новой копии и записи журнала нет.

AC-7. Given `--from-file` третьим аргументом без файла или с лишним
аргументом, When команда, Then отказ со строкой `TARGET_SET_USAGE`, слой не
записан.

AC-8. Прежние формы `target-set` (значение, `--key`, `--drop-key`, `--show`)
— тексты и поведение прежние, в том числе отказ «вложенное отображение» для
`description.test_profile.<поле>` и `NO_COMPONENT` в форме значения;
существующие тесты (`tests/test_projects_target_set.py`,
`tests/test_01m6kbd9fc36warwsy9z0jdmg5_target_set.py`,
`tests/test_01m6phs9xqtppz73v80acgszjs_target_set_key.py`,
`tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py`) зелёные без
правки.

AC-9. `TARGET_SET_USAGE` и строки справки `target-set` в
`orchestrator/artel.py` называют форму `--from-file`; каждая альтернатива
справки начинается словом `target-set`, строки продолжения — с отступом
больше двух пробелов.

## Оценка объёма и деление

Сработавший сигнал: число упомянутых модулей ≥ 5 — в тексте названы
`orchestrator/projects.py`, `orchestrator/artel.py`, `orchestrator/targets.py`,
`orchestrator/yamlmini.py`, `scripts/codebase_map.py`. Из них правятся только
два файла кода (`orchestrator/projects.py` — новая форма и сверка блока;
`orchestrator/artel.py` — только строки справки) плюс генерация карты и
долгоживущие тесты задачи (общие зоны); `orchestrator/targets.py`,
`orchestrator/yamlmini.py`, `scripts/codebase_map.py` — только чтение.

Прогноз диффа: 20 КиБ

Обоснование монолита: новая форма `--from-file` (разбор, сверка, запись) и
её справка — одна функция команды; часть со справкой без формы
назвала бы несуществующий вызов, форма без справки — расходится с
`TARGET_SET_USAGE`, которым сама же отказывает (требование 1). Делить
нечего по зонам: весь код — в одном файле `orchestrator/projects.py`.

## Не входит

- Разбор потоковых отображений `{…}` в `yamlmini`; правка
  `orchestrator/yamlmini.py` и `orchestrator/targets.py` (только чтение).
- Снятие блока целиком (`test_profile` или компонента) и переход записи с
  `test_profile` на `components`.
- Замена блоков вне `description` и правка слоя репозитория (`targets.yaml`
  репозитория).
- Правка настоящего локального слоя `.artel/targets.yaml` в тестах и при
  разработке: тесты — только вымышленные записи и файлы блоков во временной
  песочнице (фикстура `initialized_tmp_root`,
  `tests.sandbox.InitializedTmpRootTest`), без имён и адресов реальных
  проектов, без Docker и сети.
- Правка существующих тестов: если существующий тест краснеет —
  эскалация с именем теста, без правки.
- Полный зелёный набор `tests/` и зелёный CI ветки — её держит пульт.
- Правка `docs/codebase-map.md` руками (только генерацией).
- Правка файлов только чтения: `orchestrator/targets.py`,
  `orchestrator/yamlmini.py`, `scripts/codebase_map.py`,
  `docs/operator-session.md`, `tests/sandbox.py` и существующих тестов
  `target-set`/справки, названных в AC-8.

## Материалы

- ТЗ: `tasks/01M6QZ4RR80B2BYM9AXG5ZMAS4/TZ.md`.
- `orchestrator/projects.py`: `cmd_target_set` (`:395`), `_target_set_load`
  (`:444`), `_rendered` (`:480`), `_target_set_write` (`:489`),
  `_comment_line` (`:610`), `_field_keys` (`:633`), `_target_set_mismatches`
  (`:761`), `_merge_mismatches` (`:813`), `_backup_copy` (`:839`).
- `orchestrator/targets.py`: `COMPOSE_REQUIRED` (`:110`), `COMPOSE_FORBIDDEN`
  (`:115`), `merge_local` (`:486`), `_check_compose` (`:1239`).
