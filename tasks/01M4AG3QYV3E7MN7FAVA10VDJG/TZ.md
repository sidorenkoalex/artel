---
task: 01M4AG3QYV3E7MN7FAVA10VDJG
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Рост долгоживущих тестов: правило автора тестов и замер времени файлов задачи

# ТЗ: рост долгоживущих тестов — правило автора тестов и замер времени файлов задачи

Источник: строка бэклога «Рост долгоживущих тестов: правило автора тестов и
замер времени файлов задачи» (решение Оператора 06.10); анализ 07.10;
строки копилки 07.10 о двух неустойчивых тестах. Решение Оператора 07.10:
завести.

Факты (main d13bf792, сверка 07.10):
- Тестов 4 757 методов / 136,9 тыс. строк при 57 тыс. строк кода (2,4:1);
  последние 12 задач добавили 14 947 строк тестов на 2 794 строки кода
  (5,3:1), 73 % новых методов — долгоживущие. Долгоживущих файлов 0 (25.09)
  → 94 (07.10), 851 метод; 63 % из них — на `RealGitSandbox` (настоящий git,
  часто FSM), 27 % — на `TmpRootTest`, 9 % — без песочницы. Полный прогон при
  -n 4: 632 с (05.10, 4 369 тестов) → 688 с (07.10, 4 587).
- Два долгоживущих теста 07.10 краснели случайно из-за ожидания по
  реальному времени: `tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py::Ac6NoCommitWarningTest::test_ac6_warning_once_per_step_and_again_for_new_step`
  (CI main 158aa0da) и `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py::SuiteRunProfileLimitTest::test_ac5_suite_run_cuts_at_profile_limit_and_reports_it`
  (CI гейта мержа 01M48WTP12, зелёный на ре-ране).
- Правила автора тестов — `skills/test-authoring.md` (защищённый путь:
  правка только приложением к PLAN).
- Рубеж `in_dev -> verifying` прогоняет планку и долгоживущие файлы задачи:
  `orchestrator/advance_gates/acceptance.py::_acceptance_run_body` (~260),
  пути прогона — `orchestrator/acceptance.py` (~195, ~258, ~316).

Требуется:
1. Правило в `skills/test-authoring.md` (приложением к PLAN, точный текст):
   (а) свойство, проверяемое без песочницы (чистая функция, разбор, формат
   текста, таблица решений), проверяется модульным тестом без `TmpRootTest`/
   `RealGitSandbox`; песочница с git/FSM — только для свойства самой связки
   «команда — FSM — база — git», и тогда в докстринге сказано, какую связку
   тест держит; (б) короткий конечный перечень вариантов перебирается
   целиком в одном тесте (`subTest`), а не методом на вариант; (в) тест не
   ждёт по реальному времени (sleep/опрос с таймаутом ради наступления
   события): время и паузы подменяются; предел времени в тесте — только
   страховка от зависания, не условие проверки.
2. На рубеже `in_dev -> verifying` пульт пишет время прогона долгоживущих
   файлов задачи по файлам (журнал задачи) и предупреждает (не отказывает),
   если файл дольше порога — именованная константа `config` (решение SPEC,
   с обоснованием по замеру). Итог — в карточке приёмки (запись «приёмка: что проверит
   approve», orchestrator/fsm_autogate.py, orchestrator/fsm.py) и в ревью-пакете
   ревьювера (orchestrator/review.py::review_package).
3. Тесты в `tests/` с заявками «Ловит мутацию»: время по файлам пишется в
   журнал; файл сверх порога даёт предупреждение, файл в пределах — нет;
   предупреждение не меняет исход рубежа; итог виден в карточке приёмки и
   ревью-пакете. Существующие тесты не ослабляются.
4. В PLAN — замер времени долгоживущих файлов текущего main по файлам
   (топ-20) как основание порога.

Зоны: orchestrator/advance_gates/acceptance.py, orchestrator/acceptance.py,
orchestrator/config.py, orchestrator/review.py, orchestrator/fsm_autogate.py,
orchestrator/fsm.py, tests/, docs/codebase-map.md.

Приложением: skills/test-authoring.md

Только чтение (не менять): conftest.py, tests/test_invariants.py,
docs/invariants.md, docs/adr/, docs/roadmap.md, docs/backlog.md,
docs/operator-session.md, templates/, CLAUDE.md, models.yaml, roles.yaml,
targets.yaml, .github/workflows/ci.yml, scripts/codebase_map.py,
orchestrator/brief.py.

Не входит: перевод существующих тестов в модульные и правка двух
неустойчивых долгоживущих тестов (отдельно, через amend-tests/задачу);
отказ рубежа по времени (только предупреждение); правка skills/review-checklist.md.

Рамка: $35.
