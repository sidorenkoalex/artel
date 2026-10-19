---
task: 01M59KMPG2ZMK10V556VZVQD65
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: G2а-1 — правило планки компонента

## Подход
Узел — описание правила в `scripts/guard.py` и его построение по записи
проекта в `orchestrator/project_profile.py`; остальные зоны — потребители,
которым правило передаётся необязательным параметром `rule` уже вызываемых
функций guard.

- `guard.PlankComponent` (имя, маски `tests`, вид метки `LABEL_TEST_AC` /
  `LABEL_AC`, синтаксис пометок `MARKER_HASH` / `MARKER_SLASH`) и
  `guard.PlankRule` (компоненты в порядке записи, `refusal`). Методы:
  `component_of`, `is_test`, `masks`, плюс `owns` (файл компонента, не
  общий) и `is_labelled` (файл с меткой `AC-<n>: `). `DEFAULT_PLANK_RULE =
  PlankRule()`: у правила без компонентов принадлежность — прежняя
  `is_extraneous_acceptance_test_file`, и все функции разбора идут прежним
  путём побайтно (`_by_rule`). Так держатся требования 3 и 10: тексты и
  области чтения артели не трогаются, новое поведение — отдельной веткой.
- Разбор `AC-<n>: `: голова вызова — регулярка `TEST_CALL_HEAD`
  (`^[ \t]*(it|test)(.concurrent|.sequential)*`), скобки `.each(…)` и
  литерал — разбор текста (`plank_test_names`, многострочная таблица,
  скобки внутри строк, `${` в обратных кавычках отсекается). Пометки `//`
  — `AC_SLASH_MARKER` / `INDENTED_SLASH_AC_MARKER`, текст отказа отступа —
  `INDENTED_AC_MARKER_REASON_TMPL` с заменой префикса. Маркер красноты
  не-pytest файла — `first_comment`; текст отказа общий, меняется только
  место («в первом комментарии файла»).
- `scan_ac_content` принимает элементы-тексты (Python, как прежде) и пары
  (имя, текст): у пары синтаксис по правилу. Поэтому в теле перехода не
  появилось ни одной новой функции guard — сторож предпроверки не
  правится (требование 11): ветка перехода фильтрует пути методами
  `rule.owns` / `rule.is_test`, у правила-умолчания — прежний
  `endswith(".py")`.
- `project_profile.plank_rule(target)`: артель, `test_profile`, непрочитанная
  запись, запись без компонентов с масками не-pytest — `DEFAULT_PLANK_RULE`;
  компонент `report: pult-vitest` без `tests` — `PlankRule(refusal=…)`.
  `decide` не зовётся; `acceptance.is_pytest_command` импортируется внутри.
  `journal_plank_default` пишет причину отказа (действие
  `PLANK_RULE_DEFAULT_ACTION`) для чекпоинта и документов перед мержем.
- Поля `Profile.tests` / `Profile.plank_layout` — `compare=False`,
  заполняет `_with_component_fields`.

Бюджет SPEC ($65) не пересматривается.

## Шаги
1. `scripts/guard.py`: `PlankComponent`/`PlankRule`/`DEFAULT_PLANK_RULE`,
   разбор метки, пометок `//`, первого комментария; параметр `rule` у
   `scan_ac_content`, `scan_acceptance_tests`, `count_test_methods`,
   `redness_marker_errors_from_files`, `scan_redness_markers`,
   `scan_id_format_samples`, `is_extraneous_acceptance_test_file`,
   `traceability_errors_from_content`, `acceptance_traceability_errors`,
   `indented_ac_marker_errors_from_files`, `scan_indented_ac_markers`.
2. `orchestrator/project_profile.py`: `plank_rule`, `journal_plank_default`,
   поля `Profile`.
3. Потребители:
   - `checkpoint._journal_stray_step_artifacts` — правило проекта задачи;
     запись отказа построения — до записи «посторонние файлы» (гейт
     `_tests_writing_stray_plank_files_gate` сверяет последнюю запись).
   - `fsm._tests_writing_ac_state` — отказ построения → отказ перехода
     (`project_profile.REFUSAL_ACTION`); оба пути по правилу.
   - `preflight` — отказ построения в проверке «профиль тестов»;
     `_filtered(rel, rule)`, `_plank_py_files(docs, rule)`, `_traceability`,
     маркер красноты по `rule.is_test`.
   - `amend` — `_plank_rule_or_exit` в обоих режимах; рабочая копия и
     голова ветки по правилу; `_collect_and_run` берёт маркер красноты по
     отдельному перечню тестовых файлов правила (`_rule_test_files`).
     `_test_files`, `_groups`, `acceptance_test_files` не меняются.
   - `dry_run` — тестовые файлы и имена тестов по правилу.
   - `fsm_autogate` — `_plank_sources(…, rule=)` у перечня «что проверит
     approve»; `_autogate_conditions` — fail-closed до чтения планки
     (`_plank_rule_refusal`), существующим путём отказа.
   - `acceptance.summary` — правило по имени каталога через БД
     (`_summary_plank_rule`); вызывающий не меняется.
   - `fsm_merge_gate._task_docs_violations(…, rule=None)` — правило проекта
     и без `guard_rules`; при отказе построения — умолчание; структура
     `.md` — только при `guard_rules`. `_guard_task_docs_or_refuse` пишет
     причину отказа построения в журнал.
4. Юнит-тесты `tests/test_guard_plank_rule_parsing.py` (счёт сводки по
   правилу, подсказка смешанного правила, скобки в строках `.each`),
   регенерация `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2, 3 |
| 3 | 1, 3 |
| 4 | 1, 4 |
| 5 | 1 |
| 6 | 3 (checkpoint) |
| 7 | 3 (fsm, preflight, amend) |
| 8 | 3 (dry_run, fsm_autogate, acceptance) |
| 9 | 3 (fsm_merge_gate) |
| 10 | 1 (прежний путь при умолчании) |
| 11 | 1, 3 (без новых функций guard в переходе) |
| 12 | 4; долгоживущий файл задачи и планка |

## Влияние на систему
- Артель и записи `test_profile` получают `DEFAULT_PLANK_RULE`, и каждая
  функция guard при нём идёт прежней веткой кода (`_by_rule` ложно) —
  тексты, области чтения и исходы не меняются; это закрепляют
  `ArtelUnchangedTest` долгоживущего файла и тесты AC-15 планки.
- Сторож предпроверки `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`
  не тронут и зелёный: множество функций guard тела перехода не изменилось,
  `INPUT_FILTERS` прежний.
- Автогейт при правиле не по умолчанию только строже (fail-closed до
  G2а-2); `acceptance.run` и прогон планки не менялись.
- Гейты, лимиты и тесты не ослаблялись; существующие тестовые методы не
  менялись. Откат — revert merge-коммита задачи.

## Риски
- Строки `it('AC-n: …')` в многострочных комментариях и
  `describe.skip` засчитываются текстом — принятый Оператором остаточный
  риск до G2б (SPEC «Не входит»).
- Ветка автокоммита пишет запись отказа построения при каждом чекпоинте
  такой задачи — шумно, но это и есть требуемое «пишут причину в журнал».

## Предложения системе
- Сторож роли `conftest.py` отказывает `pytest -n` даже на явном списке
  файлов — гонять двадцать затронутых модулей приходится последовательно
  (6 минут); формулировка скила «тесты затронутых модулей» об этом молчит.
