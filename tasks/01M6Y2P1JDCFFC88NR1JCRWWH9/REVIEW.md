---
task: 01M6Y2P1JDCFFC88NR1JCRWWH9
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Правила guard для общего состояния: фикстуры уровня модуля только через shared_readonly, build — помощник гейта неослабления (ADR-0032, этап 5, часть б)

## Фаза A: план
- Таблица покрытия полна (требования 1–7), шаги — проверяемые единицы.
- Приложения 1–2 перенесены в PLAN.md без изменений текста (сверено с SPEC построчно).
- «Влияние на систему» совпадает с diff: `scripts/guard.py`, `tests/sandbox.py`,
  новый `tests/test_guard_shared_readonly_rules.py`, карта. Ослаблений
  существующих тестов нет: diff `tests/` — только новый файл; ветки освобождения
  `lint_base` прежних нарушений не изменены (`statements` у них пуст).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_shared_state_violations` проверяет все вызовы `pytest.fixture` (декоратор, присваивание, псевдоним модуля, `from pytest import fixture` — проверено пробой); `"function"`/`None`/без scope — без отказа |
| 2 | OK | `_shared_readonly_calls` + `_imported_names`; `_fixture_table` кладёт `build` с `shared=True`, `records` не тянет параметры `build`; `_changed_fixture_names` называет имя общей фикстуры |
| 3 | реализовано не так в одном пути | правило работает (пробы: `pytestmark`, метод класса, `usefixtures` на классе, фикстура класса, autouse, модульный `RealGitSandbox()` — отказ), но `sandbox_sources={}` через `long_lived_errors_from_files` выключает часть правила — R1-F1; `import tests` — R1-F2 |
| 4 | OK | `tests/sandbox.py:2539-2555`; временная мутация подтверждена |
| 5 | OK | `PLANK_LABEL_RE` в `_size_rules_apply`, `tests/acceptance_tests/…` правил не теряет |
| 6 | OK | вызывающие не менялись; копилка — в PLAN «Предложения системе» одной строкой про оба пути |
| 7 | OK | приложения без изменений |

## Замечания

- major — `scripts/guard.py:4560-4562` (`long_lived_errors_from_files` → `pytest_style_errors_from_files(..., sandbox_sources=sandbox_sources)`) — пустой словарь `sandbox_sources` пробрасывается как есть, и в `pytest_style_errors_from_files` (`:5085-5090`, `is not None`) даёт пустой перечень классов песочниц. Указание Оператора на гейте SPEC, п. 1: «`None` и пустой словарь — модули `config.ROOT`». Все три вызывающих отдают именно `{}`, когда у профиля нет `size_marks: required`: `orchestrator/advance_gates/tests_writing.py:651-652` (`... if size_marks else {}`), `orchestrator/amend.py:313-314` (`_sandbox_sources` → `{}`), `orchestrator/amend.py:1390-1391` (`if checked else {}`), плюс `orchestrator/preflight.py:261`. Сценарий: профиль без `size_marks` (или артель его снимет), test_author кладёт в долгоживущий файл общую фикстуру и `class L(RealGitSandbox)` / `RealGitSandbox()` — выход из `tests_writing` пропускает файл без отказа «в модуле с общей фикстурой других песочниц нет». Проверено пробой: `long_lived_errors_from_files([(…, src)], …, sandbox_sources={})` → строки отказа нет, с `None` — есть. Предложение: в `long_lived_errors_from_files` передавать проверке стиля `sandbox_sources or None` (прямой вход `pytest_style_errors_from_files(…, sandbox_sources={})` остаётся пустым перечнем, как требует AC-4 и `test_ac4_empty_sandbox_sources_no_sandbox_classes`), и закрыть это тестом в `tests/` на `long_lived_errors_from_files(…, sandbox_sources={})` с классом-наследником `RealGitSandbox`.
- minor — `scripts/guard.py` `_imported_names` (`:2052-2068`) и `_SandboxRefs.__init__` (`:4772-4785`) — форма `import tests` с вызовом `tests.sandbox.shared_readonly(…)` / `tests.sandbox.RealGitSandbox()` не распознаётся: `import tests` кладёт в `modules` «tests», а префикс вызова — «tests.sandbox». Проба: файл с общей фикстурой и `tests.sandbox.RealGitSandbox()` после `import tests` — отказа нет; общая фикстура через `import tests` + `tests.sandbox.shared_readonly(...)` молча не считается ни общей фикстурой, ни «иным вызовом». Формы нет в перечне требования 2, поэтому minor; предложение — учесть префиксы `import <пакет>` (atтрибутная цепочка `tests.sandbox.*`) либо явно записать форму в принятый пробел копилкой.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | scripts/guard.py:4560-4562 | `sandbox_sources={}` из `long_lived_errors_from_files` даёт пустой перечень классов песочниц вопреки указанию Оператора п. 1 («пустой словарь — модули `config.ROOT`») | при профиле без `size_marks` (все вызывающие отдают `{}`) классы/создания песочниц в модуле с общей фикстурой проходят выход `tests_writing`, `preflight`, `amend-tests` без отказа | передавать проверке стиля `sandbox_sources or None`; тест в `tests/` на путь `long_lived_errors_from_files(…, sandbox_sources={})`; developer, итерация 2: сделано как предложено — `long_lived_errors_from_files` передаёт проверке стиля `sandbox_sources or None` (прямой вход `pytest_style_errors_from_files(…, {})` по-прежнему пустой перечень, AC-4); тест `tests/test_guard_shared_readonly_rules.py::test_long_lived_empty_sandbox_sources_reads_root_sandboxes` (мутация проверена — красный) |
| R1-F2 | fixed | scripts/guard.py:2052-2068, 4772-4785 | `import tests` + `tests.sandbox.shared_readonly(…)`/`tests.sandbox.RealGitSandbox()` не распознаются | общая фикстура в этой форме не проверяется ни одним правилом, создание песочницы проходит | распознать префикс `import <пакет>` либо записать форму в принятый пробел; developer, итерация 2: `_imported_names` — `import tests[.<модуль>]` без псевдонима даёт `tests.sandbox.shared_readonly`, `import tests as p` — `p.sandbox.shared_readonly`; `_SandboxRefs.packages` — имя пакета (или его псевдоним) ведёт к классам песочниц любого модуля пакета; тест `tests/test_guard_shared_readonly_rules.py::test_bare_package_import_names_shared_fixture_and_sandbox` (три формы импорта; мутация проверена — красный) |

## Вердикт
changes_requested: закрыть R1-F1 (major — расхождение кода с указанием Оператора на гейте SPEC, п. 1), R1-F2 — исправить или обоснованно отклонить.

Наблюдение для Оператора: в указании п. 1 «пустой словарь — модули `config.ROOT`, как для правил размера» внутренне расходится — правила размера (`scripts/guard.py:4547-4549`, `is not None`) пустой словарь читают как пустой перечень, а AC-4 SPEC и долгоживущий `test_ac4_empty_sandbox_sources_no_sandbox_classes` требуют того же у `pytest_style_errors_from_files`. Предложенное решение R1-F1 совмещает оба (подмена только на пути `long_lived_errors_from_files`); если Оператор имел в виду «как для правил размера» буквально — R1-F1 снимается ответом.

## Проверено исполнением
- `artel.py plank-run 01M6Y2P1JDCFFC88NR1JCRWWH9` — отказ «планки нет: … нет файлов test_*.py» (все тесты задачи — долгоживущие, pytest не запускался).
- `python3 -m pytest -p no:cacheprovider -q tests/test_01m6y2p1jdcffc88nr1jcrwwh9_construct_failure.py tests/test_01m6y2p1jdcffc88nr1jcrwwh9_shared_state_rules.py tests/test_guard_shared_readonly_rules.py` — 112 passed.
- Временная мутация: удалена строка `fixtures += [(None, s.build, s.name) …]` в `_changed_fixture_names` — `test_weakened_helpers_names_shared_fixture_on_build_change` красный (заявка подтверждена); код возвращён `git checkout`.
- Временная мутация: `_run_cleanups(sb)` без проверки `sb is not None` в `construct` — оба теста `…_construct_failure.py` красные; код возвращён, `git status` чист.
- Проба (временный скрипт в каталоге документов, удалён `task-rm`): `pytest_style_errors_from_files` на `from pytest import fixture` + `scope='module'`, `pytestmark usefixtures('tmp_root')`, метод класса с `tmp_root`, `usefixtures('real_git')` на классе, фикстура класса с `tmp_dir`, autouse-фикстура с `tmp_root`, модульный `RealGitSandbox()` — отказ есть; чистый файл — отказов нет; `import tests` + `tests.sandbox.RealGitSandbox()` — отказа нет (R1-F2); `long_lived_errors_from_files(…, sandbox_sources={})` — отказа нет, `None` — есть (R1-F1).

## Предложения системе
- Пустой словарь как «правило выключено» у `sandbox_sources` вызывающих (`tests_writing.py:651`, `amend.py:313`, `:1390`) — неявный сигнал, который новый потребитель параметра (здесь проверка стиля) наследует молча; явный флаг или `None` вместо `{}` убрал бы класс.
