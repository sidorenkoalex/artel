---
task: 01M3MVXZXF25KYY2P213E0M39X
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Защищённые пути — настройки сбора тестов (conftest.py, pyproject.toml и родственные)

## Фаза A — план

- Таблица покрытия полна: требования 1–12 привязаны к шагам 1–5; шаги —
  единицы размера MR.
- Подход (помощник в `orchestrator/config.py`, шесть вызовов, явный
  перечень для CI-джоба и условия полного прогона) не конфликтует с
  архитектурой. Вставка корня в `sys.path` у `scripts/ci_protected_paths.py`
  повторяет приём `scripts/guard.py:45`. Джоб CI (`.github/workflows/ci.yml:247+`)
  и раньше исполнял скрипт из checkout ветки, так что перенос формулы в
  незащищённый `orchestrator/config.py` нового вектора ослабления не
  открывает: `scripts/ci_protected_paths.py` защищённым тоже не был.
- «Влияние на систему» соответствует диффу: 8 файлов, все в зонах SPEC и
  мандате ANSWER-1. `zone_lock.py`, `fsm_advance.py` и `gates.py` не
  тронуты.
- Замечание к плану: шаг 5 и докстринг модуля
  `tests/test_protected_test_settings.py` сознательно оставляют основные
  свойства задачи только планке, см. R1-F1.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `config.py`: 12 прежних записей на местах, +5 в конце, всего 17 |
| 2 | OK | ветка маски сверяет `path.rsplit("/",1)[-1]`; `conftest.py.bak` и `tests/test_conftest_role_guard.py` не покрыты |
| 3 | OK | литералы корневые, префиксная формула; `tests/pytest.ini` не покрыт (AC-3 в планке зелёный) |
| 4 | OK | помощник в `config.py`, новых импортов в модуле нет |
| 5 | OK | все шесть мест зовут `config.is_protected_path`, имена и сигнатуры сохранены. Grep `PROTECTED_PATHS` по `orchestrator/` и `scripts/` седьмого места сверки не нашёл |
| 6 | OK | для записей без маски формула та же. `protected_zones` расходится с `_covered_by` (`zone_lock.py:231`) только на «записи-файле плюс суффикс» |
| 7 | OK | тот же текст отказа (AC-4/AC-5 планки зелёные) |
| 8 | OK | `protected_paths_from_source` не менялся; маска — строковый литерал |
| 9 | OK | AC-8 зелёный |
| 10 | OK | `_FULL_SUITE_APPENDIX_PREFIXES` пополнен, сверка идёт помощником; для `tests/` и `.github/` вердикт прежний |
| 11 | OK | `docs/stack.md:524`: строка после таблицы, таблица не тронута |
| 12 | реализовано не полностью | см. R1-F1: долгоживущие свойства покрыты только планкой |

## Замечания

- major — `tests/test_protected_test_settings.py:1-9` (плюс отсутствие
  тестов для `orchestrator/config.py:662-664` и
  `orchestrator/fsm_merge_gate.py:568-570`). Основные долгоживущие
  свойства задачи в `tests/` не сторожит никто, только планка задачи
  (ADR-0018, п. 3). Докстринг модуля прямо говорит, что тесты берут
  «грани, которые приёмочная планка намеренно не проверяет». Без сторожа
  остались:
  (а) наличие `**/conftest.py`, `pyproject.toml`, `pytest.ini`,
  `setup.cfg`, `tox.ini` в `config.PROTECTED_PATHS` (AC-1);
  (б) новые записи в `_FULL_SUITE_APPENDIX_PREFIXES`: класс
  `FullSuiteLegacyPrefixesTest` проверяет только `tests/`, `.github/`
  (AC-9);
  (в) шесть мест сверки опознают маску на реальном перечне. Возврат
  любого из них (`zones._protected_paths_touched`,
  `fsm_merge_gate._touches_protected_path`,
  `github_adapter._touched_protected_paths`,
  `guard._appendix_path_is_protected`, `guard.protected_zones`,
  `ci_protected_paths.is_violation`) к префиксной формуле молча снимает
  защиту `tests/sub/conftest.py` (AC-4/5/6/8/10/11).
  Сценарий: `orchestrator/config.py` не защищён, и следующая задача
  убирает `"**/conftest.py"` из перечня либо откатывает одно место к
  своей формуле. CI зелёный, планку смерженной задачи не гоняет ни один
  джоб, и дыра, против которой задача заведена, открывается снова.
  Проверено мутантом (см. «Проверено исполнением»): при перечне из 12
  записей и прежнем условии полного прогона восемь затронутых модулей
  `tests/` проходят; единственный красный тест — артефакт подмены в
  памяти.
  Предложение: добавить в `tests/` (тем же модулем или отдельным) тесты
  на реальный `config.PROTECTED_PATHS`:
  - состав: пять новых записей присутствуют, прежние 12 на местах;
  - `_appendix_needs_full_suite` истинна для `conftest.py`,
    `tests/sub/conftest.py`, `pyproject.toml`, `pytest.ini`,
    `setup.cfg`, `tox.ini`;
  - каждое из шести мест признаёт `tests/sub/conftest.py` и
    `pyproject.toml` защищёнными и не признаёт `tests/test_store.py`.
  У каждого теста — заявка «Ловит мутацию: …».

- minor — `orchestrator/fsm_merge_gate.py:568`. Имя
  `_FULL_SUITE_APPENDIX_PREFIXES` теперь несёт маску, а не только
  префиксы. Имя закреплено SPEC (требование 10), поэтому достаточно
  комментария, который уже есть. Правка не обязательна.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | tests/test_protected_test_settings.py:1; orchestrator/config.py:662; orchestrator/fsm_merge_gate.py:568 | состав перечня (5 новых записей), новые записи условия полного прогона и опознание маски шестью местами на реальном перечне в `tests/` не сторожатся — только планкой | удаление записи-маски или откат одного места к префиксной формуле после мержа проходит CI зелёным (подтверждено мутантом) | добавить в `tests/` тесты на реальный перечень: состав, `_appendix_needs_full_suite` на шести новых путях, шесть мест на `tests/sub/conftest.py`/`pyproject.toml`, с заявками «Ловит мутацию». Разработчик (ff0bd09a): в `tests/test_protected_test_settings.py` добавлены `RealProtectedPathsCompositionTest` (состав 12+5 в памяти и в тексте `config.py`), `SixCheckPointsOnRealListTest` (шесть мест на реальном перечне), `FullSuiteTestSettingsTest` (полный прогон на семи путях); мутант «перечень 12 + прежнее условие» краснит 7 тестов |

## Вердикт

changes_requested. Исправить R1-F1: перенести сторожа основных свойств
задачи (AC-1, AC-9, маска в шести местах) в `tests/`. Реализация кода по
требованиям 1–11 верна, правок кода не требуется.

## Проверено исполнением

- `python3 -m pytest tasks/01M3MVXZXF25KYY2P213E0M39X/acceptance_tests
  tasks/01M31DRD81092HB69J0MAKZMGH/acceptance_tests
  tests/test_protected_test_settings.py tests/test_protected_paths_gate.py
  tests/test_ci_protected_paths.py tests/test_plan_appendix.py
  tests/test_zones_gate.py tests/test_github_adapter.py
  tests/test_stack_parity_table.py tests/test_guard_zones.py
  tests/test_guard_path_mentions.py -p timeout -o timeout=120`: 172
  passed, 103 subtests passed.
- Мутант R1-F1, в процессе, код не правился: `config.PROTECTED_PATHS =
  PROTECTED_PATHS[:12]`, `fsm_merge_gate._FULL_SUITE_APPENDIX_PREFIXES =
  ("tests/", ".github/")`, затем unittest по восьми модулям
  (`test_protected_test_settings`, `test_protected_paths_gate`,
  `test_ci_protected_paths`, `test_plan_appendix`, `test_zones_gate`,
  `test_github_adapter`, `test_guard_zones`, `test_stack_parity_table`).
  Результат: 129 тестов, 1 failure —
  `test_ci_protected_paths.ProtectedPathsParsingTest.test_real_config_text_yields_the_live_protected_paths`.
  Этот тест сверяет текст файла с живым значением, и падает он только
  из-за подмены в памяти. При настоящей правке исходника текст и живое
  значение совпали бы, и тест был бы зелёным. Значит, удаление записей
  `tests/` не ловит.
- `grep -rn PROTECTED_PATHS orchestrator scripts`: мест кода, сверяющих
  путь с перечнем, кроме шести из требования 5, нет (прочие вхождения —
  докстринги и комментарии).
- `.github/workflows/ci.yml:247-272`: джоб `protected-paths` исполняет
  скрипт из checkout ветки с `fetch-depth: 0`, так что импорт
  `orchestrator.config` в раннере доступен.

## Предложения системе

- Шаблон для классов «планка покрывает AC, `tests/` — только грани»:
  разработчик сознательно назвал набор `tests/` дополнением к планке, а
  не сторожем. Стоит явно добавить в `skills/test-authoring.md`, что
  критерии, задающие постоянные свойства (состав перечней, гейты), обязаны
  дублироваться в `tests/` (ADR-0018 п. 3), — сейчас это правило живёт
  только в чек-листе ревьювера.
