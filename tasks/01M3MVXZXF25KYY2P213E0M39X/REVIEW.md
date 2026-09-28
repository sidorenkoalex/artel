---
task: 01M3MVXZXF25KYY2P213E0M39X
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Защищённые пути — настройки сбора тестов (conftest.py, pyproject.toml и родственные)

## Фаза A — план

- Таблица покрытия полна: требования 1–12 привязаны к шагам 1–5. Шаг 5
  теперь прямо называет сторожей долгоживущих свойств в `tests/` (R1-F1).
- «Влияние на систему» совпадает с диффом итерации 2: коммит `ff0bd09a`
  трогает только `tests/test_protected_test_settings.py` и карту
  (`git diff --stat 6cb9ae0f..ff0bd09a` без артефактов). Код пульта в
  итерации 2 не менялся, поэтому вердикт итерации 1 по требованиям 1–11
  остаётся в силе.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | без изменений с итерации 1; состав теперь сторожит `RealProtectedPathsCompositionTest` |
| 2 | OK | без изменений с итерации 1 |
| 3 | OK | без изменений; `tests/pytest.ini` вошёл в `UNPROTECTED_PATHS` сторожей |
| 4 | OK | без изменений с итерации 1 |
| 5 | OK | каждое из шести мест на реальном перечне проверяет свой тест в `SixCheckPointsOnRealListTest` |
| 6 | OK | без изменений с итерации 1 |
| 7 | OK | без изменений с итерации 1 |
| 8 | OK | `test_real_config_source_carries_the_entries_for_ci_job` сверяет текст `config.py` через `protected_paths_from_source` |
| 9 | OK | без изменений с итерации 1 |
| 10 | OK | `FullSuiteTestSettingsTest` проверяет все семь путей и ложь на `skills/spec-authoring.md` |
| 11 | OK | без изменений с итерации 1 |
| 12 | OK | R1-F1 закрыт: долгоживущие свойства сторожит `tests/`, а не только планка |

## Замечания

Blocker и major нет.

- minor (перенесено из итерации 1, в реестр не заводилось) —
  `orchestrator/fsm_merge_gate.py:568`. Имя `_FULL_SUITE_APPENDIX_PREFIXES`
  теперь хранит и маску. Имя закреплено SPEC, комментарий на месте, правка
  не нужна.

Сверка «набор не ослаблен»: 10 удалённых строк диффа приходятся на
докстринг модуля и две строки импорта, которые заменены расширенными.
Ни одного `assert` не удалено и не изменено, прежние классы
(`MaskEntryTest` и следующие) не тронуты.

Заявки «Ловит мутацию» у девяти новых тестов проверены мутантами (см.
«Проверено исполнением»): каждая заявленная мутация краснит именно свой
тест.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_protected_test_settings.py:1; orchestrator/config.py:662; orchestrator/fsm_merge_gate.py:568 | состав перечня, новые записи условия полного прогона и опознание маски шестью местами на реальном перечне не сторожились в `tests/` | удаление маски или откат места сверки проходил CI зелёным | Исправлено в `ff0bd09a`. Мутанты ревьювера: откат каждого из шести мест к префиксной формуле краснит ровно свой тест `SixCheckPointsOnRealListTest`; прежнее `_FULL_SUITE_APPENDIX_PREFIXES` краснит `test_appendix_to_test_settings_needs_full_suite`; перечень из 12 записей краснит тест состава и пять мест; удаление `"**/conftest.py"` из ТЕКСТА `config.py` убирает маску из разбора CI (`is_violation("tests/sub/conftest.py")` даёт False), поэтому краснеют `test_real_config_source_carries_the_entries_for_ci_job` и CI-тест мест |

## Вердикт

approved. R1-F1 закрыт: долгоживущие свойства задачи (AC-1, AC-9, маска
в шести местах, текст исходника для джоба CI) теперь сторожат тесты в
`tests/` на реальном перечне. У каждого теста исполнимая заявка «Ловит
мутацию». Реализация требований 1–11 не менялась и верна (итерация 1).

## Проверено исполнением

- `python3 -m pytest tests/test_protected_test_settings.py
  tasks/01M3MVXZXF25KYY2P213E0M39X/acceptance_tests
  tests/test_protected_paths_gate.py tests/test_ci_protected_paths.py
  tests/test_plan_appendix.py tests/test_zones_gate.py
  tests/test_github_adapter.py tests/test_guard_zones.py
  tests/test_guard_mutation_claim.py -q -p timeout -o timeout=120` на HEAD
  `ff0bd09a`: 164 passed, 173 subtests passed.
- Мутанты в процессе (`mock.patch.object`, код не правился), unittest
  модуля `tests.test_protected_test_settings`, 16 тестов, базовый прогон
  без провалов:
  - `fsm_merge_gate._touches_protected_path` получает префиксную формулу →
    красный `test_merge_gate_diff_check`;
  - `zones._protected_paths_touched` получает префиксную формулу →
    красный `test_zones_gate_check`;
  - `ci_protected_paths.is_violation` откатывается к `startswith` → красный
    `test_ci_job_check_on_real_config_source`;
  - `guard._appendix_path_is_protected` получает префиксную формулу →
    красный `test_plan_appendix_check`;
  - `guard.protected_zones` получает префиксную формулу → красный
    `test_spec_protected_zones_check`;
  - `_FULL_SUITE_APPENDIX_PREFIXES = ("tests/", ".github/")` → красный
    `test_appendix_to_test_settings_needs_full_suite`;
  - `config.PROTECTED_PATHS[:12]` → красные тест состава и пять мест
    (merge, zones, appendix, spec_zones, draft MR).
- Мутант текста: из исходника `orchestrator/config.py` в памяти удалён
  литерал `"**/conftest.py", `, затем прогнан
  `protected_paths_from_source`. Результат: 16 записей, маски нет,
  `is_violation("tests/sub/conftest.py", …)` даёт False. Значит,
  настоящее удаление из исходника покраснит оба теста, которые читают
  текст `config.py`.
- `orchestrator/github_adapter.py:73-78`: при `repo=None`
  `_touched_protected_paths` зовёт `gitcmd.git`, поэтому подмена
  `gitcmd.git` в `test_draft_mr_highlight_check` проверяет сверку реально.

## Предложения системе

- В итерации 1 мутант с подменой перечня в памяти не краснил CI-место:
  его тест читает текст файла. Тест, который читает исходник, ловит
  только правку текста, и мутант в памяти такое место не проверяет.
  Стоит отметить это в `skills/review-checklist.md` рядом с «Проверено
  исполнением»: мутанты мест, читающих исходник, делать правкой текста.
