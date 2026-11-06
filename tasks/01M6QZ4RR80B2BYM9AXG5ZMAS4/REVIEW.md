---
task: 01M6QZ4RR80B2BYM9AXG5ZMAS4
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: target-set — замена блока профиля или компонента из файла

## Фаза A: план
- Таблица покрытия полна (требования 1–8 → шаги 1–3); шаги размера MR.
- Подход (ветка `rest[2] == "--from-file"` до прежних форм, общий хвост
  `_target_set_load`/`_rendered`/`_target_set_write`) не конфликтует с
  архитектурой. «Влияние на систему» совпадает с diff: правятся только
  `orchestrator/projects.py`, одна строка справки `orchestrator/artel.py`
  и карта (генерация); `targets.py`, `yamlmini.py`, тесты не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `projects.py` `_target_set_block`: `len(rest) != 4` → отказ с `TARGET_SET_USAGE`; ветка ловит `--from-file` третьим аргументом до прежней формы значения. |
| 2 | OK | `_block_keys`: ровно `description.test_profile` или три сегмента `description.components.<имя>`; писуемость имени — пробный `_render({имя: None}, 0, "")` до сборки; отказ несёт `BLOCK_PATHS` целиком. Проверил: `''`, `a:b`, `#x` → `_Unwritable`. |
| 3 | OK | `_block_file`: OSError/UnicodeDecodeError — текстом; «пуст» до разбора; `_comment_line` (строка и хвост); `YamlError`; `_duplicate_key` по стеку отступов (номер с 1, родитель учтён); пустое отображение; неписуемое значение — отказ `_rendered` «не записать». |
| 4 | OK | Присваивание по ключу в deepcopy: заменённый компонент на месте, новый — в конец; блок заменяется целиком. |
| 5 | OK | `_target_set_block_mismatches`: префикс кортежа для изменённых/добавленных/снятых листов (`_changed_leaves`), равенство значения файлу (`_differences`), порядок ключей родителя, затем `_merge_mismatches`. Сборка — только через `_rendered`→`_render`. |
| 6 | OK | Строка `<путь>: блок из <аргумент> (листов было N|(нет) → стало M)`, N/M по `_leaves`; `Path(file_arg)` от cwd, аргумент дословно; «без изменений» до проверки журнала; `db_usable` — отказ до записи. |
| 7 | OK | Прежние ветки не тронуты, изменён только текст `TARGET_SET_USAGE` (хвост). |
| 8 | OK | `TARGET_SET_USAGE` и справка `artel.py:200` называют форму; отступ продолжений сохранён; карта содержит новые функции (11 вхождений в `docs/codebase-map.md`, последний коммит карты — c0b3417f0). |

## Замечания

Замечаний к разработчику нет.

Наблюдение для Оператора (не замечание разработчику): требование 5 (сверка
строже `_merge_mismatches`, порядок компонентов на уровне сверки) после
мержа охраняется только разовой планкой `acceptance_tests/test_target_set_block_seam.py`
(AC-10) — долгоживущему `tests/` подмена закрытого `projects._render`
запрещена конвенцией. Мутация «сверка только через `_merge_mismatches`»
после мержа сторожа в CI не имеет. Разработчик это честно отметил в
PLAN «Риски»; закрыть можно только решением о шве (публичный шов сборки
или исключение для `_render`).

Мелочь вне замечаний: `_duplicate_key` берёт ключ как текст до первого
`:`; `yamlmini` кавычек ключа не снимает (`"a": 1` и `a: 2` — разные
ключи разбора, проверил), так что расхождения с разбором нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest -q -p no:cacheprovider tests/test_01m6qz4rr80b2bym9axg5zmas4_target_set_block.py tests/test_projects_target_set.py tests/test_01m6kbd9fc36warwsy9z0jdmg5_target_set.py tests/test_01m6phs9xqtppz73v80acgszjs_target_set_key.py tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py` — 116 passed, 11 subtests passed (AC-8: существующие тесты зелёные без правки).
- `artel.py plank-run 01M6QZ4RR80B2BYM9AXG5ZMAS4` — 7 passed, код выхода pytest 0.
- Временная мутация в `orchestrator/projects.py` (N = `len(current)` вместо `_leaves`; `_duplicate_key` без снятия кадров стека — повтор без учёта родителя) → долгоживущий файл задачи: 3 failed (AC-1, AC-3, AC-5 «разные родители»); код возвращён `git checkout -- orchestrator/projects.py`, `git status` чистый.
- Пробы `_duplicate_key`/`yamlmini.mapping` на кавычённых и вложенных ключах и `_render({k: None}, 0, "")` для `''`, `a:b`, `#x`, `a.b` — поведение соответствует требованиям 2–3.

## Предложения системе

- Конвенция «долгоживущим `tests/` нельзя подменять закрытые имена» +
  SPEC, называющий шов закрытым именем (`projects._render`, AC-10), дают
  свойство без сторожа после мержа (ADR-0018 п. 3). Аналитику стоит
  называть шов, допустимый в `tests/`, либо Оператору — разрешить
  подмену шва, названного SPEC.
