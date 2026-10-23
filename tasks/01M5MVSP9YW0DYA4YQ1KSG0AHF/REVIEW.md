---
task: 01M5MVSP9YW0DYA4YQ1KSG0AHF
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Тесты планки и долгоживущие тесты проверяются на ожидание по часам и чтение живых файлов до лока

## Фаза A: план
- Таблица покрытия полна (1–9). Требование 7 закрыто долгоживущими файлами
  test_author, а не шагом разработчика, и это верно: тесты пишет test_author.
- Шаги по размеру годятся для MR: модуль, guard, amend, приложение.
- Подход повторяет образец SPEC (`network_address_hits` через
  `long_lived_errors_from_files`). Цикла импорта нет: `test_lint`
  импортирует только `ast`.
- «Влияние на систему» совпадает с diff: изменены `orchestrator/amend.py`,
  `orchestrator/test_lint.py`, `scripts/guard.py` и карта. Защищённые пути
  не тронуты, `tests/test_invariants.py` в ветке не изменён — он меняется
  только приложением.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/test_lint.py` построчно совпадает с удалёнными методами приложения (`cls._X` → `X`). Импортирует только `ast`, `SyntaxError` пробрасывается. Сравнение на дереве `tests/` я повторил сам: 658 файлов, 62/62 ключа, `repr` равны. |
| 2 | OK | Приложение в PLAN побайтно равно приложению SPEC, `git apply --check` проходит. С наложенным приложением `DeterministicTestsLintTest`: 6 passed, 16 subtests. |
| 3 | OK | `scripts/guard.py:4023–4025`: линт стоит после пропуска не-`.py` без метки и до `plank_file_group`, только при `network_addresses`. `SyntaxError` в `lint_errors_from_files` даёт пропуск файла. Адрес имеет вид «метка::метод: строка N: …». |
| 4 | OK | `lint_base` в guard: гашение по совпадающим имени и `ast.dump`. В amend: `_plank_lint_errors` и `_plank_label` приводят метки снимка к виду `acceptance_tests/…` на трёх местах (`amend.py:945`, `1047`, `1304`) — отдельно от раннего выхода `_group_line_errors`. Рабочая копия: база — голова кодовой ветки (`amend.py:1061`). `--from-branch`: `_locked_long_lived_texts`/`_text_with_digest` находят ревизию по сумме blob из перечня, если её нет — базы нет. Пути `_by_rule` у артели не исполняются: `project_profile.plank_rule` для артели всегда возвращает `DEFAULT_PLANK_RULE`, `project_profile.py:652`. |
| 5 | OK | Отказ даёт существующий гейт групп или гейт долгоживущих файлов (`tests_writing.py:384`, `509`), классы отказа прежние. |
| 6 | OK | Флаг `network_addresses = is_artel` у всех вызывающих (`tests_writing`, `preflight`, `amend.py:293`, `317`, `725`). `_plank_lint_errors` проверяет `is_artel` сам. |
| 7 | OK | Три долгоживущих файла, у каждого метода есть «Ловит мутацию:», заявки исполнимы — ниже мутации, которые я проверил сам. |
| 8 | OK | Вывод сравнения приложен к PLAN, я его воспроизвёл. |
| 9 | OK | Существующие тесты в diff не тронуты, в `tests/` правок разработчика нет. |

## Замечания
Блокирующих и major-замечаний нет.

Сверка по классам проверки:
- Тесты: группы «долгоживущий» помечены верно (все — свойства кода).
  Повторов долгоживущих тестов у разработчика нет: своих тестов он не
  добавлял.
- Целостность: правило не ослаблено. Перечень `_EXCEPTIONS` гейтом не
  читается — это держит `test_ac8_exceptions_list_not_read`.
- Карта кодовой базы свежая: после `python3 scripts/codebase_map.py`
  расходится только `built_at_sha`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_test_lint.py tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_exit_gates.py tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_amend_lint.py -p no:cacheprovider -q` — 23 passed, 27 subtests passed.
- `artel.py plank-run 01M5MVSP9YW0DYA4YQ1KSG0AHF` — 3 passed, код выхода 0.
- Приложение 1, извлечённое из PLAN, побайтно равно приложению SPEC. `git apply --check` прошёл. Затем `git apply` и `pytest tests/test_invariants.py -k DeterministicTestsLintTest` — 6 passed, 16 subtests. После этого `git checkout -- tests/test_invariants.py`.
- Сравнение эквивалентности `DeterministicTestsLintTest.findings` и `test_lint.findings` на всех `tests/**/*.py` (до приложения): 658 файлов, 62/62 ключа, `repr` равны.
- Временные мутации, после каждой код возвращён `git checkout`:
  - в `guard.lint_errors_from_files` гашение только по имени, без `ast.dump` → красные `test_ac8_base_silences_only_unchanged_methods` и `test_ac6_worktree_long_lived_changed_locked_method_refused`;
  - линт в `long_lived_errors_from_files` перенесён после фильтра по группе → красный `test_ac4_one_off_plank_sleep_and_live_file_refused_before_lock` (оба подтеста);
  - `_text_with_digest` берёт не ревизию с суммой из перечня, а первую ревизию после головы → красный `test_ac6_from_branch_two_commits_first_added_method_refused`.
- `python3 scripts/codebase_map.py` → в diff `docs/codebase-map.md` только `built_at_sha`; изменение откачено.

## Предложения системе
- Каждый вызов `long_lived_errors_from_files` передаёт `network_addresses=is_artel(...)` одной и той же формой: `tests_writing.py`, `preflight.py`, `amend.py:293/317/725`. При этом умолчание параметра — `True`. Новый вызывающий без явного флага включит линт и сетевые адреса у чужого проекта. Умолчание `False` или обязательный параметр закрыли бы этот класс.
