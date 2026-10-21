---
task: 01M5ENWTDD8NP9SMPFX3JN08J9
type: spec_audit
author_role: spec_auditor
status: ready
verdict: pass
signals: в) пути-признаки (тесты): tests/, tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py; в) пути-признаки (гейты): orchestrator/advance_gates/acceptance.py, orchestrator/advance_gates/plan_appendix.py; в) пути-признаки (песочница ролей): orchestrator/runner.py; в) защищённые пути: skills/review-checklist.md, skills/test-authoring.md; в) SPEC требует приложения PLAN; д) ТЗ ссылается на ADR: ADR-0026.
spec_sha: fa6275410675e1a188b0e993193c751d2bc2cfdc
schema_version: 5
---

# SPEC-AUDIT: G5б — задание test_author по правилу планки, сводки Vitest, итоговая строка plank-run, скилы приложением

Круг 3. Проверяемый SPEC — `git hash-object SPEC.md` = fa627541… (совпадает
с миссией). Отличие от круга 2 — внесено решение Оператора на гейте SPEC №2
(форма строки `Duration`, строки между `Tests` и `Duration`).

## ТЗ и SPEC
- Требования ТЗ пп. 1–5 отражены: п. 1 → требование 1 + AC-1/AC-2; п. 2 →
  требования 2–5 + AC-3…AC-7; п. 3 → требование 6 + AC-8/AC-9; п. 4 →
  требование 7 + AC-10; п. 5 → требование 8 и состав фикстур AC-3/AC-5/AC-7.
- Решения гейта SPEC №1 (6 пунктов): п. 1 — «Не входит» (проба на sled);
  п. 2 — требование 1 «Меченый компонент без `plank_layout`» и AC-2; п. 3 —
  подстановки в требовании 1, два знака секунд в требовании 2 и AC-3; п. 4 —
  требование 3, AC-5, AC-9; п. 5 — раздел «Оценка объёма и деление»,
  «Прогноз диффа: 45 КиБ»; п. 6 — требование 7 и AC-10 (название раздела
  «Изменённые утверждения тестов»). Все отражены.
- Решение гейта SPEC №2: требование 2 (хвост `Duration`, строки `Errors`/
  `Start at` в пределах четырёх строк, `Test Files`/`Tests` без хвоста) и
  AC-3 (фикстура с хвостом `(transform …)` и строкой `Start at`). Отражено.
- Требований сверх ТЗ и решений нет: «Профиль не определён» (требование 3)
  — из решения №1 п. 4; остальное — переформулировки ТЗ.

## Факты против кода
Подтвердилось:
- `orchestrator/role_prompt.py:70` — ветка `test_author`; п. 2 «напиши
  unittest … метод test_ac<n>_...» — `:80-82`; пометки `# AC-n` — `:84-88`;
  `_long_lived_author_note` вызывается на `:83`, `_plank_run_point` — `:89`.
- `orchestrator/project_profile.py:328` `REPORT_VITEST = "pult-vitest"`;
  `:470` `plank_rule` — артель/`test_profile`/нет `components` →
  `DEFAULT_PLANK_RULE`; метка `LABEL_AC` у компонента с `tests` и командой
  не pytest (`:497-503`); все `LABEL_TEST_AC` → умолчание (`:504`).
  `Profile.component` — `:95`; `decide` — `:184`, `profile=None` при
  отказе/пропуске — `:166-176`.
- `scripts/guard.py:2880` `labelled_components` — имена компонентов с
  `LABEL_AC` в порядке записи.
- `orchestrator/advance_gates/acceptance.py:254` —
  `plank_layout.replace('<id>', task_id)` (подстановка «как есть»).
- `orchestrator/agent_log.py:221` `PYTEST_RUN_ACTION`, `:354` `OutputPump`,
  `:363` параметр `on_pytest_summary`, вызов `:413-423`.
- `orchestrator/runner.py:1708-1711` — единственный в коде вызов
  `OutputPump(` с `on_pytest_summary`.
- `orchestrator/watch.py:221`, `:288`, `:446` — сравнения с
  `PYTEST_RUN_ACTION`; `orchestrator/report.py:99` `_PYTEST_SECONDS_RE`
  (` in <число>s` — деталь «… in 0.52s» читается без правки регулярки),
  `:969` — сравнение действия.
- `orchestrator/plank_run.py:286-291` — `run_summary_line(output) or
  "итоговой строки нет"`, строки `:289` (оборван) и `:291` (код выхода).
- `orchestrator/review.py:72` `CHANGED_ASSERTIONS_SECTION = "Изменённые
  утверждения тестов"`.
- `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py`: проекты «pair»
  и «template» — `pult-vitest` с масками `tests` и без `plank_layout`
  (`:54-61`, `:95-104`); тесты `:177`, `:249` закрепляют только пункты 2а и
  5 (`assertIn`), не пункт 2 — новое задание (без фразы о выкладке, по
  решению №1 п. 2) их не ломает. Тестов, закрепляющих «напиши unittest» или
  «итог pytest» у `pult-vitest`, в `tests/` нет (поиск по `unittest в`,
  `итог pytest` в файлах с `cmd_plank_run`).

Не подтвердилось: —

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | новый пункт 2 применён безусловно / к `junit-xml` с pytest (у `plank_rule` это умолчание) — эталон расходится |
| AC-2 | да | признак взят по `report` вместо правила планки (у `junit-xml` с командой не pytest текст прежний); маски в ином порядке/без кавычек; `<id>` не подставлен или переведён в нижний регистр; фраза о выкладке оставлена без `plank_layout` |
| AC-3 | да | `ms` не переведены / секунды без двух знаков (`1.5s`); `Duration` требует конца строки (хвост `(transform …)`); `Duration` только сразу за `Tests` (`Start at`); ANSI не снят; `Tests` без `Test Files` перед ней принят; блок без `Duration` принят; `no tests`/`todo`/`skipped` не разобраны |
| AC-4 | да | колбэк не вызывается или пишет с `PYTEST_RUN_ACTION`; деталь не по разбору |
| AC-5 | да | `on_vitest_summary` передаётся безусловно / при `profile is None` падает `AttributeError`; разбор Vitest включён в насосе без колбэка |
| AC-6 | да | смена значения `PYTEST_RUN_ACTION` или детали pytest |
| AC-7 | да | дозор/отчёт сравнивают действие только с `PYTEST_RUN_ACTION`; отдельный бюджет строк для vitest |
| AC-8 | да | у `pult-vitest` остаётся «итог pytest»; правится только одна из двух строк; деталь не по разбору |
| AC-9 | да | слово «vitest» или разбор Vitest применены у прочих / при `profile is None` |
| AC-10 | да (гейт применимости и проверка текста) | приложение не применяется (`git apply --check`); дописка к review-checklist без «Изменённые утверждения тестов» |

Замечание без отклонения: строка `Errors  …` между `Tests` и `Duration`
разрешена требованием 2, но фикстурой AC-3 не покрыта (состав фикстуры задан
решением №2); реализация, допускающая между строками только `Start at`,
прошла бы AC-3. Решение Оператора прямо задало фикстуру — не поднимаю.

## Зоны
- Зоны SPEC = зоны ТЗ: шесть модулей `orchestrator/` + `tests/`. Все
  требуемые правки (задание — `role_prompt.py`; разбор/параметр насоса —
  `agent_log.py`; признак — `runner.py`, `plank_run.py`; читатели —
  `watch.py`, `report.py`) внутри зон. `project_profile.decide`,
  `plank_rule`, `labelled_components`, `run_summary_line` только
  вызываются — подписи не меняются.
- Защищённые пути `skills/test-authoring.md`, `skills/review-checklist.md`
  — только приложением PLAN (требование 7), в зоны не внесены. `templates/`,
  `gates.yaml`, `roles.yaml` не трогаются.
- Песочница ролей (`runner.role_env`, `role_cmd`) не расширяется: правка
  `runner.py` — только аргумент насоса в `_spawn_and_wait`.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Задание test_author (`role_prompt.py:70-95`) | пункты 2а/5 — `tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py:177`, `:249` | да, побайтно (требование 1) | те же тесты без правок (требование 8) + AC-1, AC-2 | оставить |
| Насос `OutputPump` (`agent_log.py:354`) и запись «прогон pytest» (инвариант 11, `docs/invariants.md:41`) | `PYTEST_RUN_ACTION` `agent_log.py:221`, `runner.py:1710` | да; добавляется только новое действие | AC-6, AC-5 | оставить |
| Дозор/отчёт (`watch.py:221/288/446`, `report.py:969`) | класс `pytest`, бюджет строк, секунды | да, расширение пары действий | AC-7, AC-6 | оставить |
| Итог `plank-run` (`plank_run.py:289-291`) | существующие тесты plank-run (`tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `..._plank_run_role.py`) | да у прочих побайтно | эти тесты без правок + AC-9 | оставить |
| Скилы (приложение PLAN) | гейт применимости `advance_gates/plan_appendix.py` | да | AC-10 | оставить |

Раздела «Меняемое поведение» в SPEC нет и не нужно: утверждения
существующих тестов не меняются (требование 8).

## Пути обхода гейтов
- Признак задания взят по `report == pult-vitest` вместо правила планки —
  `junit-xml` с командой не pytest получил бы unittest-задание при
  `//`-правиле guard. Закрыто: признак явно `labelled_components()`
  (требование 1), AC-2 требует случай `junit-xml` с командой не pytest.
- «Тривиальный» разбор, ловящий любую `Tests` — закрыто AC-3 (листинг кода,
  блок без `Duration`).
- Обход неослабления правкой существующих тестов — запрещён требованием 8;
  тестов, закрепляющих прежнее поведение у `pult-vitest`, нет (см. «Факты»).
- Обход гейта применимости приложением, не меняющим строк, — AC-10 требует
  наличие раздела, вводной фразы и названия раздела пакета ревьювера.
Иных путей не нашёл.

## Вердикт
pass — отклонений нет. Все решения Оператора на гейте SPEC (№1 пп. 1–6,
№2) отражены (SPEC требования 1–3, 7, AC-2/3/5/9/10, раздел деления); места
кода сверены (`orchestrator/role_prompt.py:70-89`,
`orchestrator/agent_log.py:221/354/413`, `orchestrator/runner.py:1708-1711`,
`orchestrator/watch.py:221/288/446`, `orchestrator/report.py:99/969`,
`orchestrator/plank_run.py:286-291`, `orchestrator/project_profile.py:328/470`,
`scripts/guard.py:2880`, `orchestrator/advance_gates/acceptance.py:254`,
`orchestrator/review.py:72`). Замечание к сведению (не отклонение): строка
`Errors` между `Tests` и `Duration` фикстурой AC-3 не покрыта — состав
фикстуры задан решением №2.
