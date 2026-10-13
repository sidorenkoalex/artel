---
task: 01M4RZBDFSHNESSBQREH5MKY9B
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Бриф: шаблон артефакта роли целиком

## Подход
В `orchestrator/brief.py` — одна таблица `ROLE_TEMPLATES` («роль →
шаблоны»: analyst — SPEC.md, QUESTIONS.md; developer — PLAN.md;
spec_auditor — SPEC-AUDIT.md) и один помощник `_template_components(conn,
task_id, role, run_id, render)`. Помощник читает каждый шаблон строки роли
вызовом `gitcmd.show(config.MAIN_BRANCH, "templates/<имя>",
repo=config.ROOT)` напрямую (не `_main_branch_text`: тот роняет шаг
`sys.exit`). Прочитан — компонент тем же `render`, что у соседей роли
(`_manifest_component` у developer/spec_auditor, `_journal_component` у
analyst), с общим `run_id` брифа: граница, опись и запись «бриф:
компонент» с sha256 исходного текста — штатной механикой. Не прочитан —
пометка вне границы «шаблон templates/<имя> не прочитан: <причина> —
прочитай его сам» и запись журнала от имени роли с действием «бриф: шаблон
не прочитан», деталь `templates/<имя>: <причина>`. Причина схлопывается в
одну строку (stderr git бывает многострочным).

Помощник зовётся в конце `analyst_map_component`, `developer_brief`,
`spec_auditor_brief` — после всех прежних компонентов и ДО
`context_package.discipline` (у developer/spec_auditor): шаблон проходит
деление на части с общим id запуска. `role_prompt.mission_brief_package`
не трогается структурно — шаблон читается внутри подменяемых тестами
функций брифа, поэтому тесты с `mission_brief_package(None, …)` не
меняются (AC-11). reviewer/test_author в таблице нет.

В `role_prompt.py` — формулировки миссий analyst, developer, spec_auditor:
«…по шаблону templates/<имя> — он в БРИФЕ РОЛИ ниже; …» и отдельная
строка-оговорка: файл `templates/<имя>` с диска читать, только если вместо
шаблона в брифе стоит пометка «шаблон … не прочитан». Каждая строка миссии
с именем шаблона несёт либо «БРИФ», либо «не прочитан» (AC-10).

Бюджет SPEC ($40) не пересматривается: дифф — таблица и помощник, три
вызова, три миссии, правка трёх ожиданий в тестах.

## Шаги
1. `orchestrator/brief.py`: `ROLE_TEMPLATES`, `TEMPLATE_UNREAD_ACTION`,
   `_template_components`; вызов в конце трёх функций брифа.
2. `orchestrator/role_prompt.py`: формулировки миссий трёх ролей.
3. Тесты: `tests/test_brief.py` — два литерала из «Меняемого поведения»
   (`3` → `4`, `1` → `3`); `tests/test_review_package.py::
   CmdRunReviewPackageTest::test_developer_step_has_no_package` — одна
   вставка `["-C", root, "show", "main:templates/PLAN.md"]` между
   `ls-tree … tasks/<id>` и `["config", "--get", "user.name"]`
   (ANSWER-1, требование 7). Свойства требования 6 покрывает долгоживущий
   файл `tests/test_01m4rzbdfshnessbqreh5mky9b_role_templates.py`
   (не правится); свой тест — только на не покрытое им: схлопывание
   многострочной причины git в одну строку пометки.
4. `python3 scripts/codebase_map.py`, планка `plank-run`, тесты затронутых
   модулей, `suite-run`; guard на PLAN.md.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1, 3 |
| 5 | 2 |
| 6 | 3 |
| 7 | 3 |
| 8 | 4 |
| 9 | 4 |

## Влияние на систему
Бриф трёх ролей растёт на размер шаблона (единицы КБ); опись и потолок
файла/части `context_package` действуют на шаблон как на любой компонент —
лимиты не трогаются. Чтение шаблона не роняет шаг (в отличие от
`_main_branch_text` для CLAUDE.md): неудача — видимая пометка и запись
журнала. Ревью-пакет и бриф reviewer/test_author не меняются. Тесты
меняются только в объявленных местах: два литерала раздела «Меняемое
поведение» и одна вставка по мандату ANSWER-1; утверждения не
ослабляются. Если иной метод покраснеет из-за шаблона/пометки в брифе —
эскалация (требование 8), не подгонка. Откат — revert merge-коммита
задачи.

## Риски
- Тесты вне перечня, сверяющие точный список git-вызовов или журнал шага
  developer/analyst/spec_auditor, могут покраснеть от нового `show` —
  проверяется полным прогоном `suite-run`; такой случай — эскалация.

## Проверка
- `tests/test_01m4rzbdfshnessbqreh5mky9b_role_templates.py`: 16 passed.
- Планка `plank-run`: 3 passed (AC-11, AC-12, AC-14).
- `suite-run` №1, полный набор: прошло 5364, упало 0, пропущено 2.
- Свой сторож `tests/test_brief.py::TemplateUnreadReasonTest` краснеет на
  мутации «причина без схлопывания» (проверено временной мутацией).
- Отказ гейта заявки мутации (итерация 2): двум методам из «Меняемого
  поведения» (`DeveloperBriefTest::test_assembles_three_components_and_journals_their_hashes`,
  `AnalystMapComponentTest::test_adds_only_the_map_and_journals_one_hash`)
  добавлены докстринги с «Ловит мутацию: …»; утверждения не тронуты.
  Временные мутации `ROLE_TEMPLATES` (analyst без QUESTIONS.md, developer
  без PLAN.md) — каждый метод красный, после возврата 2 passed;
  `guard.test_functions_without_mutation_claim` по всем изменённым против
  main файлам `tests/` — пусто. `tests/test_brief.py` + долгоживущий файл
  задачи: 41 passed.

## Предложения системе
- Песочница роли не даёт `ls`/`sed -i` в Bash (только python/grep/git):
  временная мутация сторожа делается правкой через Edit туда-обратно;
  скил coding-standards описывает мутацию так, будто shell-правка доступна.
- Смена литерала по «Меняемому поведению» делает метод «изменённым» для
  гейта заявки мутации, хотя докстринга у старого метода не было: стоит
  назвать это в skills/coding-standards.md рядом с правилом о «Меняемом
  поведении» — иначе шаг сдаётся дважды (01M4RZBDFSHNESSBQREH5MKY9B).
