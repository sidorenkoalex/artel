---
task: 01M6Y2P1JDCFFC88NR1JCRWWH9
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Правила guard для общего состояния: фикстуры уровня модуля только через shared_readonly, build — помощник гейта неослабления (ADR-0032, этап 5, часть б)

## Фаза A: план
- Таблица покрытия полна (требования 1–7), шаг 6 добавлен под R1-F1/R1-F2 и привязан к требованию 3.
- Приложения 1–2 не менялись с итерации 1 (текст совпадает со SPEC).
- «Влияние на систему» совпадает с инкрементальным diff: `scripts/guard.py` (`_imported_names`, `long_lived_errors_from_files`, `_SandboxRefs`), `tests/test_guard_shared_readonly_rules.py` (+2 теста), карта. Ослаблений нет: diff `tests/` только добавляет методы, существующие утверждения не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | без изменений с итерации 1 |
| 2 | OK | `_imported_names` дополнительно узнаёт `import tests[.x]` и `import tests as p`; вызывающих две (`scripts/guard.py:2095`, `:5053`), обе с модулями `tests.*` — расширение не задевает разбор чужих модулей |
| 3 | OK | `long_lived_errors_from_files` передаёт `sandbox_sources or None` (`scripts/guard.py:4575`) — `{}` вызывающих теперь означает модули `config.ROOT` (указание Оператора, п. 1); прямой вход `pytest_style_errors_from_files(…, {})` остаётся пустым перечнем (AC-4, `test_ac4_empty_sandbox_sources_no_sandbox_classes` зелёный); правила размера по-прежнему получают `sandbox_sources` как есть |
| 4 | OK | без изменений |
| 5 | OK | без изменений |
| 6 | OK | вызывающие не менялись; копилка в PLAN |
| 7 | OK | приложения без изменений |

## Замечания

Новых замечаний нет. R1-F1 и R1-F2 закрыты (реестр ниже).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | scripts/guard.py:4575 | `sandbox_sources={}` из `long_lived_errors_from_files` давал пустой перечень классов песочниц | при профиле без `size_marks` песочницы в модуле с общей фикстурой проходили без отказа | исправлено `sandbox_sources or None`; `test_long_lived_empty_sandbox_sources_reads_root_sandboxes` краснеет при откате правки (проверено временной мутацией) |
| R1-F2 | accepted | scripts/guard.py:2069-2076, 4796-4828 | `import tests` + `tests.sandbox.*` не распознавались | общая фикстура и создание песочницы в этой форме не проверялись | `_imported_names` и `_SandboxRefs.packages` учитывают имя пакета и его псевдоним; `test_bare_package_import_names_shared_fixture_and_sandbox` (три формы импорта) краснеет при снятии `packages.add(TESTS_PACKAGE)` (проверено временной мутацией) |

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -p no:cacheprovider -q tests/test_01m6y2p1jdcffc88nr1jcrwwh9_construct_failure.py tests/test_01m6y2p1jdcffc88nr1jcrwwh9_shared_state_rules.py tests/test_guard_shared_readonly_rules.py` — 114 passed.
- Временная мутация (обе правки разом): `sandbox_sources=sandbox_sources or None` → `sandbox_sources=sandbox_sources` в `long_lived_errors_from_files` и `self.packages.add(TESTS_PACKAGE)` → `pass` в `_SandboxRefs.__init__`; прогон `tests/test_guard_shared_readonly_rules.py` + `tests/test_01m6y2p1jdcffc88nr1jcrwwh9_shared_state_rules.py` — 2 failed (`test_long_lived_empty_sandbox_sources_reads_root_sandboxes`, `test_bare_package_import_names_shared_fixture_and_sandbox`), 110 passed; код возвращён `git checkout scripts/guard.py`, `git status` чист.
- `grep -n "_imported_names(" scripts/guard.py` — две вызывающих точки, обе с модулями `tests.sandbox`/`tests.fixtures`.
- Планки у задачи нет (итерация 1: `plank-run` — «нет файлов test_*.py»); все тесты задачи долгоживущие и прогнаны выше.

## Предложения системе
- Пустой словарь как «правило выключено» у `sandbox_sources` вызывающих (`tests_writing.py:651`, `amend.py:313`, `:1390`) остаётся неявным сигналом; здесь закрыт подменой `or None` в одном месте — следующий потребитель параметра унаследует ту же ловушку. Явный `None` у вызывающих снял бы класс.
