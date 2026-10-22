---
task: 01M5J0JYW3GZSSHHK3TYCYTQ3J
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: G3б-2 — гейт неослабления по исходам: прежние версии, строгий режим, исключения в коде, заменяемые тесты; автогейт по правилу планки

## Фаза A: план
- Таблица покрытия PLAN полна (требования 1–11 → шаги 1–4); шаг 5 (итерация 2) адресно закрывает R1-F1..F3. Шаги размера MR, подход не конфликтует с архитектурой.
- «Влияние на систему» сверено с инкрементальным diff 51f588ca..HEAD: `outcome_integrity._added_lines` (argv, разбор `+++ `), `_code_exception_findings` (вид файла по пути головы), новые тесты `tests/test_fsm_autogate_plank_rule.py` и случаи в `tests/test_outcome_integrity_added_lines.py`. Ничего вне зоны. Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | без изменений с итерации 1 |
| 2 | OK | без изменений; см. комментарий к 7 о новом пути `R`/`C` |
| 3 | OK | без изменений |
| 4 | OK | без изменений |
| 5 | OK | без изменений |
| 6 | OK | без изменений |
| 7 | OK | вид файла — по пути головы (переименование тест→код проверяется как код); правило «новый на ветке путь под `weakening_scope` с записями в отчёте головы — тестовый» у компонента без `tests` распространено с `A` на новый путь `R`/`C`. Буквально SPEC (треб. 2) называет только `A`, но новый путь переименования — тоже путь, новый на ветке; путь с записями в отчёте головы — тестовый файл по смыслу ANSWER-2/круга 2; без этого переименованный тест давал бы ложную находку. Ослаблением не считаю: файл кода без записей в отчёте головы по-прежнему проверяется |
| 8 | OK | `_added_lines`: префиксы, `--no-relative`, `--no-textconv` заданы явно; `+++ ` не `/dev/null` и не `b/…` — `_Prepare` |
| 9 | OK | без изменений |
| 10 | OK | код без изменений; сторож в `tests/` добавлен (R1-F3) |
| 11 | OK | новые тесты детерминированы, без сети и Node |

## Замечания

Новых замечаний нет. Все три записи итерации 1 проверены исполнением и временными мутациями (см. ниже) и переведены в `accepted`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/advance_gates/outcome_integrity.py `_added_lines` | разбор зависел от `diff.noprefix` конфига git пульта | fail-open: ноль находок «исключение в коде» | принято: argv с `--src-prefix=a/ --dst-prefix=b/ --no-relative --no-textconv`, неожиданный заголовок — `_Prepare`; тесты `test_noprefix_config_does_not_hide_added_lines` (краснеет без префиксов в argv), `test_unexpected_header_is_prepare_refusal` (краснеет, если заголовок снова даёт `path=None`), `test_deleted_file_header_dev_null_is_not_refusal` |
| R1-F2 | accepted | orchestrator/advance_gates/outcome_integrity.py `_code_exception_findings` | переименование тест→код исключало файл кода по старому пути | обход требования 7 | принято: вид файла по пути головы; `CodeExceptionRenameTest` краснеет при возврате проверки старого пути (2 провала) и при сужении правила новых путей до `A` (1 провал) |
| R1-F3 | accepted | orchestrator/fsm_autogate.py `_plank_rule_refusal` | AC-28/29 без сторожа в `tests/` | регрессия снятия отказа у канарейки/вне границы прошла бы после мержа | принято: `tests/test_fsm_autogate_plank_rule.py` на настоящем `_bounds`; мутация `_bounds(0, …)` (канарейка игнорируется) — красный `test_canary_in_bounds_keeps_g3b_refusal` |

## Вердикт
approved — R1-F1..F3 закрыты, новых blocker/major нет, реестр закрыт целиком.

## Проверено исполнением
- `python3 -m pytest -q -p no:xdist tests/test_outcome_integrity_added_lines.py tests/test_fsm_autogate_plank_rule.py tests/test_fsm_autogate.py tests/test_01m5j0jyw3gzsshhk3tycytq3j_profile_layers.py` — 37 passed, 23 subtests passed.
- `python3 -m pytest -q -p no:xdist -o timeout=600 tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py` — 44 passed, 26 subtests, 336.76 с.
- `python3 …/orchestrator/artel.py plank-run 01M5J0JYW3GZSSHHK3TYCYTQ3J` — 4 passed, код выхода 0.
- Временные мутации (код возвращён, `git status` чистый после каждой):
  - `fsm_autogate._plank_rule_refusal`: `_bounds(0, t["target"])` → `tests/test_fsm_autogate_plank_rule.py` 1 failed;
  - `_added_lines`: убраны `--src-prefix=a/ --dst-prefix=b/` → `tests/test_outcome_integrity_added_lines.py` 1 failed;
  - `_added_lines`: заголовок без `b/` → `path = None` → 1 failed;
  - `_code_exception_findings`: возвращена проверка `(path, old)` → 2 failed;
  - `_code_exception_findings`: правило новых путей сужено до `A` → 1 failed.
- Сверка неослабления: `git diff --stat 075806f2...HEAD -- tests/` — только четыре новых файла (два долгоживущих задачи, `test_fsm_autogate_plank_rule.py`, `test_outcome_integrity_added_lines.py`), существующие тесты не тронуты.

## Предложения системе
- Долгоживущий `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py` идёт 267–337 с при пороге 60 с — повторяю предложение итерации 1 про общий стенд песочниц гейта исходов в skills/test-authoring.md.
