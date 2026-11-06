---
task: 01M6R8W7TSA6G85PVZZFDMRY25
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: target-set: запись автора коммитов пульта machine.commit_author

# target-set: запись автора коммитов пульта machine.commit_author

## Факты

1. Поле `machine.commit_author` локального слоя — автор коммитов пульта проекта (`orchestrator/targets.py:410`, `DELIVERY_MACHINE_FIELDS`, `:434`); проверка формы — `orchestrator/targets.py:715-720`: отображение ровно с ключами `name` и `email`, оба — непустые строки, иначе отказ «нужно {name, email} — обе непустые строки». Читает поле `gitcmd.commit_author` / `gitcmd.pult_identity` (`orchestrator/gitcmd.py:567-582`).
2. Записать поле командой пульта нельзя: `target-set <проект> machine.commit_author.<поле> <значение>` — отказ «ведёт во вложенное отображение» (`_field_keys`, `orchestrator/projects.py`); `--key` — только для перечня `KEY_FIELDS` (`machine.submodule_tokens`); `--from-file` — только для путей `BLOCK_PATHS` (`orchestrator/projects.py:379-380`: `description.test_profile`, `description.components.<имя>`). Правка по одному ключу через `--key` невозможна и по существу: промежуточная запись с одним `name` не проходит проверку факта 1.
3. Опыт 06.11: GitLab с правилом сервера «email автора коммита совпадает с учётной записью отправителя» отклоняет push артефактной ветки пульта, пока `commit_author` не задан адресом учётной записи токена; поле пришлось вписать ручной правкой слоя по решению Оператора (строка копилки 06.11).
4. Форма `--from-file` (задача 01M6QZ4RR80B2BYM9AXG5ZMAS4) уже несёт разбор файла блока, проверки файла, сверку `_target_set_block_mismatches` (листы только под путём блока, значение равно файлу, порядок ключей родителя, `_merge_mismatches`), копию прежнего файла и журнал. Существующий тест `tests/test_01m6qz4rr80b2bym9axg5zmas4_target_set_block.py:417` проверяет перечень путей вхождением строки `PATHS_LITERAL` (`:42-43`).

## Требуется

1. Путь блока `machine.commit_author` — третий допустимый вид пути формы `--from-file`, наравне с `description.test_profile` и `description.components.<имя>`; поле может отсутствовать в записи (заводится) или быть (заменяется целиком).
2. `BLOCK_PATHS` дописывается в конец: `допустимые пути блока: description.test_profile, description.components.<имя>, machine.commit_author` — прежняя строка остаётся началом перечня (тест факта 4 зелёный без правки).
3. Все проверки, сверка, копия, журнал и строка вывода — те же, что у прежних путей блока; отказ проверки факта 1 (например, файл только с `name` или с лишним ключом) — отказ `merge_local` с её текстом, слой побайтно прежний, копии нет.
4. Прочие пути `machine.*` с `--from-file` (`machine.submodule_tokens`, `machine.url` и т. д.) — по-прежнему отказ с перечнем; прежние формы `target-set` — без изменений.
5. Справка: `TARGET_SET_USAGE` и строки справки `target-set` в `orchestrator/artel.py` — без изменения формы вызова (путь блока там общий), если строки перечисляют виды путей — дописать `machine.commit_author`; `docs/codebase-map.md` — только генерацией.

## Критерии приёмки

- Given вымышленная запись без `machine.commit_author` и файл с `name` и `email`, When `target-set <проект> machine.commit_author --from-file <файл>`, Then `machine.commit_author` разобранного слоя равен файлу, `gitcmd.commit_author(<проект>)` возвращает (name, email), прочие поля записи и записи слоя по разобранным значениям прежние; копия прежнего файла и строка журнала по формату формы `--from-file` (`было (нет)`);
- Given запись с `commit_author`, When файл с другими значениями, Then поле заменено целиком, строка журнала с числом листов было/стало;
- Given файл только с `name` или с лишним ключом `login`, When команда, Then отказ с текстом «нужно {name, email}», слой побайтно прежний, копии нет;
- Given `machine.submodule_tokens` или `machine.url` с `--from-file`, Then отказ с перечнем, который содержит `machine.commit_author`, слой побайтно прежний;
- существующие тесты, включая `tests/test_01m6qz4rr80b2bym9axg5zmas4_target_set_block.py`, — зелёные без правки.

Безопасность тестов: локальный слой, записи и файлы — вымышленные во временной песочнице, фикстура `initialized_tmp_root` (`tests.sandbox.InitializedTmpRootTest`); никогда — настоящий `.artel/targets.yaml`; ни имён, ни адресов реальных проектов и учётных записей; без сети.

Существующие тесты: правка не должна сделать красным ни один существующий тест; если краснеет — эскалация с именем теста, без правки.

Зоны: `orchestrator/projects.py` (`BLOCK_PATHS`, проверка пути блока формы `--from-file`), `orchestrator/artel.py` (только строки справки `target-set`, если они перечисляют виды путей), `docs/codebase-map.md` (только генерацией), `tests/` (долгоживущие файлы задачи).

Только чтение: `orchestrator/targets.py`, `orchestrator/gitcmd.py`, `orchestrator/yamlmini.py`, `scripts/codebase_map.py`, `tests/test_01m6qz4rr80b2bym9axg5zmas4_target_set_block.py`, `tests/test_projects_target_set.py`, `tests/test_01m6kbd9fc36warwsy9z0jdmg5_target_set.py`, `tests/test_01m6phs9xqtppz73v80acgszjs_target_set_key.py`, `tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py`, `tests/sandbox.py`.

Не входит:
- проверка doctor «автор коммитов пульта совпадает с учётной записью токена» — отдельной задачей;
- запись прочих полей `machine` блоком;
- переписывание уже сделанных коммитов артефактных веток;
- правка настоящего локального слоя `.artel/targets.yaml` в тестах и при разработке.

Приоритет 2.

Рамка: $20. Набор моделей — по умолчанию.
