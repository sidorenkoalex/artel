---
task: 01M5KP57JXWKKKCJKY47HT21W8
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/role_prompt.py, tests/
budget_usd: 25
---

# SPEC: Правило о полном наборе тестов у ревьювера — одно, в миссии шага; приложения скилов (CR-2, CR-1)

## Контекст
Находка ревизии кода 22.10 CR-2026-10-22-2. Решение Оператора 23.10 (вариант А):
ревьюверу полный набор `tests/` запрещён, в шаге ревью он гоняет только планку и
тесты файлов задачи, полный набор — CI и гейты пульта. Сейчас правило размазано и
противоречиво: миссия ревьювера своего правила не несёт
(`orchestrator/role_prompt.py:141`–`151`), у внешнего проекта
`_reviewer_checks_note` (`orchestrator/role_prompt.py:323`, `:335`) прямо
разрешает `` `{pult} suite-run {task_id}` — полный набор тестов ``, скил
`skills/review-checklist.md` несёт два противоречащих абзаца (04.09 и 05.09), а
образец `templates/REVIEW.md` показывает полный прогон формой
`python3 -m unittest discover -s tests`. Задача сводит правило в одну константу
миссии ревьювера (по образцу `suite_run_note` разработчика,
`orchestrator/role_prompt.py:413`) и приложениями PLAN правит скил и образец.
Вторым приложением едет шаг «Разнос находок» в `skills/code-revision.md`
(решение Оператора 23.10 по CR-2026-10-22-1).

## Требования

1. В `orchestrator/role_prompt.py` — константа модуля `REVIEWER_FULL_SUITE_RULE`
   (строка), единственный источник правила для ревьювера. Текст побайтно:
   «Полный набор тестов в шаге ревью не запускай — ни командой пульта `suite-run`, ни `pytest` или `unittest` по всему `tests/`: его гоняют CI и гейты пульта (приёмка и мерж). В шаге — планка задачи и тесты файлов задачи.»
2. Миссия ревьювера (ветка `else` функции `mission_brief_package`) включает
   `REVIEWER_FULL_SUITE_RULE` ровно один раз — сразу после фразы
   `_reviewer_checks_note`, одинаково у задачи артели и у задачи внешнего
   проекта.
3. `_reviewer_checks_note` для внешнего проекта больше не называет `suite-run`:
   перечень команд — `` `{pult} guard {task_id} [<файл>]` — структура артефактов ``
   и `` `{pult} plank-run {task_id} [<файл>]` — планка и долгоживущие файлы задачи ``,
   затем прежнее «запускай их, когда они доказывают или опровергают замечание.».
   Фраза для артели — прежняя побайтно.
4. Миссии остальных ролей (analyst, spec_auditor, test_author, developer), в том
   числе текст `suite_run_note`, не меняются побайтно.
5. Промпт ревьювера в смысле этого SPEC — миссия
   `role_prompt.mission_brief_package(conn, task_id, t, "reviewer", cwd, docs_dir)`
   (подменены `brief.developer_brief`, `brief.step_notes_block`,
   `review.review_package`, `review.previous_verdict_sha` — как `components_empty`
   в `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`), к которой
   приклеены тексты скилов `roles.skills("reviewer")` из каталога `skills/`
   репозитория ветки и текст `templates/REVIEW.md` репозитория ветки — по образцу
   склейки `runner._build_prompt`. Для задачи артели и для задачи учебного
   внешнего проекта (запись `targets.yaml` песочницы — как в
   `test_ac7_external_reviewer_mission_keeps_suite_run`) такой промпт
   удовлетворяет AC-4 – AC-7. Тесты детерминированные, без сети.
6. Утверждения о тексте скила и образца (AC-5, AC-6) живут в тесте `tests/`, а не
   сторожем внутри приложения: набор `tests/` с приложениями PLAN гоняют CI ветки
   (`scripts/plan_appendix_ci.py`), рубеж `in_dev -> verifying`, автогейт
   приёмки, `approve`, `suite-run` (`orchestrator/appendix_tree.py::suite_tree`) и
   ворота мержа (`orchestrator/fsm_merge_gate.py`, `appendix_tree.apply_in_order`).
   На дереве ветки без приложений эти утверждения красны по построению — это
   ожидаемо; зелёными они обязаны быть на дереве «ветка плюс приложения PLAN».
7. PLAN.md задачи несёт оба приложения из раздела ТЗ «Приложения PLAN»
   дословно: приложение 1 (`skills/review-checklist.md`, `templates/REVIEW.md`) и
   приложение 2 (`skills/code-revision.md`), каждое применимо к дереву базы ветки
   (`git apply --check` на чистом дереве, `skills/conventions-core.md`).
8. Существующий тест
   `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py::MissionTest::test_ac7_external_reviewer_mission_keeps_suite_run`
   с решением варианта А несовместим. Его правка — только по мандату Оператора
   (строка «Ослабление тестов разрешено:» с матрицей неослабления в ANSWER, канал
   `answer` на эскалации роли; файл долгоживущий у задачи 01M5HDB1GS). Замена
   утверждения при прежнем сценарии: миссия ревьювера внешнего проекта содержит
   `role_prompt.REVIEWER_FULL_SUITE_RULE`, `` `<pult> plank-run <id>` `` и
   `` `<pult> guard <id>` ``, и в ней нет `suite-run <id>` без ` --failed`/` --wait`
   (форма проверки — `bare_full_run` того же файла). Без мандата — эскалация, не
   правка. Остальные существующие тесты не правятся.

## Критерии приёмки

AC-1. `orchestrator/role_prompt.py` определяет на уровне модуля строковую константу `REVIEWER_FULL_SUITE_RULE`, побайтно равную тексту требования 1.

AC-2. Миссия ревьювера из `role_prompt.mission_brief_package(..., "reviewer", ...)` содержит `REVIEWER_FULL_SUITE_RULE` ровно один раз, и он стоит сразу после фразы `_reviewer_checks_note` — и у задачи артели, и у задачи учебного внешнего проекта.

AC-3. `_reviewer_checks_note` внешнего проекта называет `` `{pult} guard {task_id} [<файл>]` — структура артефактов `` и `` `{pult} plank-run {task_id} [<файл>]` — планка и долгоживущие файлы задачи ``, затем «запускай их, когда они доказывают или опровергают замечание.», и не содержит `suite-run`; фраза для артели побайтно равна прежней («Права не сужены: тесты, guard и другие исполняемые проверки запускай, когда они доказывают или опровергают замечание.»).

AC-4. В промпте ревьювера (требование 5) текст `role_prompt.REVIEWER_FULL_SUITE_RULE` встречается ровно один раз — у задачи артели и у задачи учебного внешнего проекта.

AC-5. В промпте ревьювера (требование 5) нет `suite-run <id>` без ` --failed`/` --wait` (форма проверки — как `bare_full_run` в `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`) — у задачи артели и у задачи учебного внешнего проекта.

AC-6. В промпте ревьювера (требование 5) нет подстрок `unittest discover`, `Прогон полного набора`, `— полный набор тестов` — у задачи артели и у задачи учебного внешнего проекта (на дереве «ветка плюс приложения PLAN», требование 6).

AC-7. У задачи учебного внешнего проекта миссия ревьювера называет `` `<pult> plank-run <id>` `` и `` `<pult> guard <id>` `` полным путём пульта.

AC-8. Миссии ролей analyst, spec_auditor, test_author, developer, собранные одними входами до и после правки, побайтно совпадают и текста `REVIEWER_FULL_SUITE_RULE` не содержат.

AC-9. PLAN.md задачи несёт приложение 1 (`skills/review-checklist.md`, `templates/REVIEW.md`) и приложение 2 (`skills/code-revision.md`) с диффами из раздела ТЗ «Приложения PLAN» дословно, и каждое проходит `git apply --check` на дереве базы ветки.

## Оценка объёма и деление

Сработавшие сигналы: «число затрагиваемых модулей/файлов» (guard считает все
упомянутые в тексте пути `orchestrator/*.py`/`scripts/*.py`, большинство из
которых — «Только чтение» и «Не входит») и «прогноз диффа не дан».

Прогноз диффа: 12 КиБ

Обоснование монолита: изменяемый код — один файл `orchestrator/role_prompt.py`
(константа и две функции), плюс тест в `tests/` и два приложения PLAN. Разрезать
нельзя без нерабочего промежуточного состояния: правка `_reviewer_checks_note`
(снятие `suite-run`) без правки существующего
`test_ac7_external_reviewer_mission_keeps_suite_run` краснит набор, а
приложение 1 к скилу (абзац «правило — одно, в миссии шага») без самого правила
в миссии оставило бы ревьювера вовсе без правила. Приложение 2
(`skills/code-revision.md`) — та же защищённая область и тот же порядок
наложения по решению Оператора 23.10; отдельной задачей оно потребовало бы
отдельного цикла ради одного диффа.

## Не входит

- Отказ `suite-run <id>` без флагов для роли reviewer в `orchestrator/suite_run.py` (механическое закрепление запрета; задевает `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py::OtherCallersTest::test_ac6_other_callers_start_full_run_as_before`) — отдельная задача с мандатом Оператора.
- Слова «после прогона Оператора или ревьювера» в `suite_run_note` разработчика (их закрепляет `MissionTest::test_ac7_developer_mission_names_failed_wait_and_ci_gate`).
- Сторож `conftest.py` для формы `unittest` (защищённый путь).
- Правка `docs/operator-session.md`.
- Правка в `orchestrator/role_prompt.py` сверх константы `REVIEWER_FULL_SUITE_RULE`, ветки ревьювера в `mission_brief_package` и `_reviewer_checks_note`; правка `orchestrator/runner.py`, `orchestrator/brief.py`, `orchestrator/review.py`, `roles.yaml` и прочих путей «Только чтение» ТЗ.
- Правка `skills/`, `templates/` иначе как приложениями 1 и 2 PLAN (защищённые пути).
- Только чтение: orchestrator/appendix_tree.py, orchestrator/fsm_merge_gate.py, scripts/plan_appendix_ci.py — механика наложения приложений PLAN не меняется.
- Зелёный полный набор `tests/` («остальные существующие тесты остаются зелёными») — её держит пульт.

## Материалы

- ТЗ: `tasks/01M5KP57JXWKKKCJKY47HT21W8/TZ.md`, разделы «Факты» и «Приложения PLAN» (диффы переносятся в PLAN.md дословно).
- Находки: `docs/audits/code-revision-2026-10-22.md`, CR-2026-10-22-2 и CR-2026-10-22-1.
- Образец подмен и формы проверки: `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py` (`bare_full_run`, `MissionTest.components_empty`, `test_ac7_external_reviewer_mission_keeps_suite_run`).
- Требование 8 — смена вида утверждения (`assertIn` → `assertNotIn` плюс новые), поэтому раздел «Меняемое поведение» для него не годится; по ТЗ мандат Оператора 23.10 дан, строку с матрицей неослабления Оператор передаёт через `answer` на эскалации роли.
- `budget_usd`: ТЗ называет $20, пол калибровки `config.BUDGET_CALIBRATION_FLOOR_USD` = $25 («планка не ниже $25 ни для одной задачи», `skills/spec-authoring.md`) — поставлен пол.
