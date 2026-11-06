---
task: 01M6R8W7TSA6G85PVZZFDMRY25
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/projects.py, orchestrator/artel.py, docs/codebase-map.md, tests/
budget_usd: 25
---

# SPEC: target-set: запись автора коммитов пульта machine.commit_author

## Контекст
Поле `machine.commit_author` локального слоя задаёт автора коммитов пульта
проекта (`orchestrator/targets.py:410`, `DELIVERY_MACHINE_FIELDS`); проверка
формы — `orchestrator/targets.py:715-720`: отображение ровно с ключами `name`
и `email`, оба непустые строки, иначе отказ «нужно {name, email} — обе
непустые строки». Читают поле `gitcmd.commit_author` / `gitcmd.pult_identity`
(`orchestrator/gitcmd.py:567-582`). Записать его командой пульта сейчас нельзя:
путь поля ведёт во вложенное отображение, `--key` — только для `KEY_FIELDS`,
`--from-file` — только для путей `BLOCK_PATHS` (`orchestrator/projects.py:379-380`,
проверка пути — `_block_keys`). Правка по одному ключу невозможна по существу:
запись с одним `name` не проходит проверку формы. Опыт 06.11: GitLab с правилом
«email автора коммита совпадает с учётной записью отправителя» отклонил push
артефактной ветки, пока поле не вписали ручной правкой слоя. Форма `--from-file`
(задача 01M6QZ4RR80B2BYM9AXG5ZMAS4) уже несёт разбор файла блока, его проверки,
сверку `_target_set_block_mismatches`, копию прежнего файла и журнал.

## Требования
1. Путь блока `machine.commit_author` — третий допустимый вид пути формы
   `target-set <проект> <путь блока> --from-file <файл>`, наравне с
   `description.test_profile` и `description.components.<имя>`. Поле может
   отсутствовать в записи (заводится) или быть (заменяется целиком).
2. Строка `BLOCK_PATHS` дописывается в конец и становится
   `допустимые пути блока: description.test_profile, description.components.<имя>, machine.commit_author`;
   прежняя строка остаётся началом перечня.
3. Для пути `machine.commit_author` действуют те же проверки файла блока, та же
   сверка, та же копия прежнего файла, та же строка журнала и вывода, что у
   прежних путей блока. Отказ проверки формы `commit_author` (например, файл
   только с `name` или с лишним ключом) — отказ `merge_local` с её текстом;
   слой побайтно прежний, копии прежнего файла нет.
4. Прочие пути `machine.*` с `--from-file` (`machine.submodule_tokens`,
   `machine.url` и т. д.) — по-прежнему отказ с перечнем `BLOCK_PATHS`; прочие
   формы `target-set` — без изменений.
5. Справка: `TARGET_SET_USAGE` и строки справки `target-set` в
   `orchestrator/artel.py` — без изменения формы вызова; если строки
   перечисляют виды путей блока — дописать `machine.commit_author` (на main
   они пишут путь блока общим `<путь блока>` и видов не перечисляют).
   `docs/codebase-map.md` — только генерацией.

## Критерии приёмки
AC-1. Дано: вымышленная запись локального слоя без `machine.commit_author` и
файл блока с `name` и `email`. Когда: `target-set <проект> machine.commit_author
--from-file <файл>`. Тогда: `machine.commit_author` разобранного слоя равен
отображению файла; `gitcmd.commit_author(<проект>)` возвращает пару
(name, email) из файла; прочие поля записи и прочие записи слоя по разобранным
значениям прежние; создана копия прежнего файла; строка журнала — по формату
формы `--from-file` с `листов было (нет)`.

AC-2. Дано: запись с уже заданным `machine.commit_author`. Когда: та же команда
с файлом с другими значениями `name` и `email`. Тогда: поле заменено целиком
значениями файла; строка журнала несёт число листов было/стало.

AC-3. Дано: файл блока только с `name` либо с `name`, `email` и лишним ключом
`login`. Когда: `target-set <проект> machine.commit_author --from-file <файл>`.
Тогда: отказ, вывод содержит «нужно {name, email}»; файл слоя побайтно прежний;
копии прежнего файла нет.

AC-4. Дано: путь `machine.submodule_tokens` или `machine.url` с `--from-file`.
Когда: команда. Тогда: отказ, вывод содержит перечень
`допустимые пути блока: description.test_profile, description.components.<имя>, machine.commit_author`;
файл слоя побайтно прежний.

AC-5. Существующий тест `tests/test_01m6qz4rr80b2bym9axg5zmas4_target_set_block.py`
(проверка перечня вхождением `PATHS_LITERAL`, `:42-43`, `:417`) проходит без
правки файла теста.

Безопасность тестов (из ТЗ): локальный слой, записи и файлы — вымышленные во
временной песочнице (фикстура `initialized_tmp_root`,
`tests.sandbox.InitializedTmpRootTest`); никогда — настоящий
`.artel/targets.yaml`; ни имён, ни адресов реальных проектов и учётных
записей; без сети.

## Оценка объёма и деление
Сработавшие сигналы: «число затрагиваемых модулей/файлов» и, как его
следствие, «прогноз диффа не дан». Первый сигнал считает все пути
`orchestrator/*.py`/`scripts/*.py`, упомянутые в тексте SPEC, а среди них
четыре файла только для чтения (`orchestrator/targets.py`,
`orchestrator/gitcmd.py`, `orchestrator/yamlmini.py`, `scripts/codebase_map.py`
— адреса фактов ТЗ). Правится только `orchestrator/projects.py` (строка
`BLOCK_PATHS` и третья ветка `_block_keys`); правка `orchestrator/artel.py`
условная и на main не нужна; ещё сгенерированная карта и новый долгоживущий
тест задачи в `tests/`.

Прогноз диффа: 12 КиБ

Обоснование монолита: изменение — одна новая ветка проверки пути блока плюс
дописанный перечень, а тест критериев проверяет обе части вместе (AC-4 ждёт в
перечне новый путь, AC-1..AC-3 — что путь принят). Если разрезать, первая
часть либо принимает путь, которого нет в перечне отказа, либо перечисляет
путь, который не принимается: такое промежуточное состояние противоречит
требованию 2. Решение утверждает Оператор на гейте SPEC.

## Не входит
- Проверка doctor «автор коммитов пульта совпадает с учётной записью токена» —
  отдельной задачей.
- Запись прочих полей `machine` блоком.
- Переписывание уже сделанных коммитов артефактных веток.
- Правка настоящего локального слоя `.artel/targets.yaml` в тестах и при
  разработке.
- Правка `orchestrator/targets.py`, `orchestrator/gitcmd.py`,
  `orchestrator/yamlmini.py`, `scripts/codebase_map.py` и существующих тестов
  (`tests/test_01m6qz4rr80b2bym9axg5zmas4_target_set_block.py`,
  `tests/test_projects_target_set.py`,
  `tests/test_01m6kbd9fc36warwsy9z0jdmg5_target_set.py`,
  `tests/test_01m6phs9xqtppz73v80acgszjs_target_set_key.py`,
  `tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py`, `tests/sandbox.py`)
  — только чтение по ТЗ. Покраснение существующего теста — эскалация с именем
  теста, без его правки.
- Зелёный полный набор `tests/` — её держит пульт.

## Материалы
- `orchestrator/projects.py:370-380` (`TARGET_SET_USAGE`, `BLOCK_PATHS`),
  `:617-670` (`_target_set_block`, `_block_keys`), `:496-515`
  (`_target_set_write`), `:900` (`_target_set_block_mismatches`).
- `orchestrator/targets.py:715-720` — проверка формы `commit_author`.
- `orchestrator/artel.py:200` — строка справки формы `--from-file`.
- Рамка Оператора в ТЗ — $20; `budget_usd` поставлен $25 — нижняя планка
  калибровки (skills/spec-authoring.md: «не ниже $25 ни для одной задачи»).
