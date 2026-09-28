---
task: 01M3N0BWYQ9KHVN41Z4G72706R
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Приёмочные тесты двух групп — строка группы и проверки долгоживущих файлов (ADR-0020, задача 1)

## Фаза A — план

- Таблица покрытия полна: требования 1–9 разнесены по трём шагам; шаги
  размера MR (guard / гейт + amend + тесты / приложения).
- Подход не конфликтует с архитектурой: одно место правила в
  `scripts/guard.py`, гейт в `advance_gates/tests_writing.py` по образцу
  `_tests_writing_artifact_source_gate`, подключение в тот же `_run_gates`,
  что сухой сбор.
- «Влияние на систему» совпадает с diff: 4 кодовых файла зоны, 6 файлов
  `tests/` (в 4 старых — только добавлена строка `Группа: разовый` в
  фикстуры и сдвинут `DISK_READ_LINENO` 9→10 той же вставкой; ассерты
  не тронуты). Новая зависимость `guard -> orchestrator.stack` заявлена.
- Четыре приложения к `skills/` в PLAN; AC-13 планки (он проверяет и
  `git apply --check`, и неизменность временного правила ревьювера) —
  зелёный.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `guard.GROUP_LINE`/`GROUP_VALUES`/`plank_file_group`; нет строки, неизвестное значение, две разные — ошибки с меткой файла; только `test_*.py` (`acceptance_test_files`). |
| 2 | OK, но есть замечание | Выход из `tests_writing` — гейт `_tests_writing_test_groups_gate`; `amend-tests` — оба пути (`amend.py:347`, `amend.py:483`). «До мержа» определяется по наличию строк группы в локе — эвристика, но корректная: после мержа гейт не пропускает лок без них. Подключение к `amend-tests` без сторожа в `tests/` — R1-F1. |
| 3 | OK | Все девять признаков в `long_lived_sign_hits`, у каждого свой метод в `tests/test_guard_test_groups.py`; исключения признака 9 (`self`/`cls`/`super()`, stdlib, `tests`) — по букве SPEC. |
| 4 | OK | `test_functions_without_mutation_claim(None, source)` — тот же узел, что у `_mutation_claim_gate`; «Зелёный с рождения» не засчитывается (`MUTATION_CLAIM`). |
| 5 | OK | Сухой сбор не тронут и идёт после гейта групп; `CollectFromTestsDirTest` собирает долгоживущий файл из зеркала `tests/`. |
| 6 | OK | Отказ через `_run_gates`, подсказка и в `detail`, и в `hint`; тест повтора после исправления есть. |
| 7 | OK | `target != config.DEFAULT_TARGET -> None`; канарейка проверяется (тест). |
| 8 | OK | Четыре приложения, содержимое соответствует требованию; временное правило «Долгоживущие свойства — в `tests/`» не тронуто. |
| 9 | OK | Новые методы несут «Ловит мутацию»; ослаблений в `tests/` нет. Одна заявка не исполняется — R1-F1. |

## Замечания

- major — `tests/test_fsm_advance_tests_writing_test_groups.py:212`
  (`AmendGroupLineTest.test_post_rule_plank_is_checked`) при
  `orchestrator/amend.py:347-350` и `orchestrator/amend.py:483-486` —
  заявка «Ловит мутацию: проверка строки группы не подключена к
  `amend-tests` — ошибок нет» не исполняется: тест зовёт
  `amend._group_line_errors` напрямую и подключения не видит. Проверил
  временной мутацией: заменил `if group_errors:` на `if False:` в обоих
  путях amend, прогнал `tests/test_fsm_advance_tests_writing_test_groups.py`
  и `tests/test_amend.py` — 42 passed, ни одного красного; код вернул.
  Значит, отказ `amend-tests` по строке группы (требование 2, AC-4) —
  долгоживущее свойство, которое сейчас сторожит только планка
  (`acceptance_tests/test_ac4_amend_tests_group_line.py`). После мержа её
  не запускает ни CI, ни автогейт (временное правило ревьювера, ADR-0018
  п. 3), поэтому регрессия в `amend.py` пройдёт незамеченной. Предложение:
  добавить в `tests/` сквозной тест через `amend.cmd_amend_tests` (или
  через тот вход, который зовёт `_cmd_amend_tests` /
  `_cmd_amend_tests_from_branch`) на песочнице `tests/sandbox.py` —
  по сценарию на каждый путь (worktree и `--from-branch`): лок со
  строкой группы, правка без неё → `SystemExit` с именем файла, запись
  журнала «amend-tests отклонён», `tests_locked_sha` не сдвинут. Заявку
  `test_post_rule_plank_is_checked` переписать под то, что метод
  действительно ловит (различение лока «до/после правила» внутри
  `_group_line_errors`), либо перенести её на новый сквозной тест.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_fsm_advance_tests_writing_test_groups.py:212; orchestrator/amend.py:347, orchestrator/amend.py:483 | Подключение проверки строки группы к обоим путям `amend-tests` не покрыто тестом в `tests/`; заявка мутации `test_post_rule_plank_is_checked` не исполняется (временная мутация «отказ отключён» — все тесты зелёные) | После мержа регрессия AC-4 в `amend.py` не ловится ничем: планку задачи не гоняет ни CI, ни автогейт | Сквозной тест в `tests/` на каждый путь amend (worktree и `--from-branch`): отказ с именем файла, запись журнала, лок не сдвинут; заявку существующего метода привести к тому, что он ловит |

## Вердикт

changes_requested — исправить R1-F1: добавить в `tests/` сторож на отказ
`amend-tests` по строке группы для обоих путей и поправить неисполнимую
заявку. Остальное соответствует SPEC.

## Проверено исполнением

- `python3 -m pytest -q -p no:cacheprovider tests/test_guard_test_groups.py tests/test_fsm_advance_tests_writing_test_groups.py tests/test_amend.py tests/test_fsm_advance_tests_writing_artifact_source.py tests/test_fsm_advance_tests_writing_dry_collect.py tests/test_acceptance_tests_flow.py tests/test_mutation_claim_gate.py` —
  164 passed, 37 subtests.
- `python3 -m pytest -q -p no:cacheprovider tasks/01M3N0BWYQ9KHVN41Z4G72706R/acceptance_tests` —
  34 passed, 45 subtests (включая AC-13: приложения проходят
  `git apply --check`).
- Временная мутация `orchestrator/amend.py` (`if group_errors:` → `if False:`
  в обоих путях) → `tests/test_fsm_advance_tests_writing_test_groups.py`
  и `tests/test_amend.py`: 42 passed — мутацию никто не поймал (R1-F1).
  Код вернул через `git checkout -- orchestrator/amend.py`, дерево чистое.
- Проба `guard.long_lived_errors_from_files` на долгоживущем файле с
  `namedtuple(...)._replace(...)` и `p._fields`: признак «закрытый
  атрибут» срабатывает на обе строки. Это буква требования 3 (признак 9),
  а не дефект реализации — см. «Предложения системе».

## Предложения системе

- ADR-0020 / SPEC требования 3, признак 9: исключения «закрытого
  атрибута» не покрывают публичный API namedtuple (`_replace`, `_asdict`,
  `_fields`) у объектов, которые вернул код. Долгоживущий файл с таким
  обращением отклоняется гейтом, хотя интерфейс публичный. Стоит решить
  в задаче 2 или 3 внедрения: сузить признак или завести явный перечень
  исключений.
