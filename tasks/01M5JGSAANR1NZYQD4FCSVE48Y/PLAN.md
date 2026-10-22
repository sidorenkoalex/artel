---
task: 01M5JGSAANR1NZYQD4FCSVE48Y
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: G3б-3: компонент задачи по зонам, компоненты гейтов по диффу и снятие отказа записи из нескольких компонентов

## Подход
Один источник решения в контексте задачи — `project_profile.for_task`.
Выбор компонента включается только у записи из нескольких компонентов
(`is_multi(target)` = `repo_context.profile_of(target).multi`), иначе
возвращается `decide(target)` как есть. Поэтому у артели, `test_profile`
и записи из одного компонента вывод побайтно прежний.

- `project_profile`:
  - `task_components(target, zones)` — компоненты, чьи `paths` или маски
    `test_support` задевают путь зон, в порядке записи, без `depends_on`.
    Зона-каталог («…/») сопоставляется файлами базы: `git ls-tree -r
    --name-only` по `origin/<base>`, если такая ссылка есть, иначе по
    `<base>` в клоне. Сбой — `ZoneListingError`, и тогда отказ.
  - `decide_task` / `for_task` / `for_task_target(target, task_id,
    conn=None)` / `for_row(row)` — общее тело `_by_zones`: сначала
    `decide`, а зоны строки задачи читаются лениво и только у записи из
    нескольких компонентов (таблица без колонок `zones` у прочих записей
    не ломается — AC-5). Строка задачи читается функциями store
    (`store.task_exists` + `store.get_task`), без SQL в
    `project_profile.py` — возврат из verifying: CI красил
    `tests/test_multitarget.py::SqlOnlyInStoreTest::test_no_sql_outside_store`.
  - Тексты трёх отказов дополняются причиной `decide` через «; ».
  - Ровно один компонент — та же проверка обязательных подполей, что у
    `profile_of`: `repo_context` — модуль «только чтение», поэтому
    проверка продублирована. Дальше `_with_component_fields`, как у
    `with_tools`.
  - Требование 7: поле `layers_declared` (вне сравнения) и `layers_of`
    различают «поля нет» и «поле пусто». `profile.layers` остаётся `()`,
    как требуют тесты G3б-2.
- Места таблицы SPEC переведены на `for_task_target` с тем же `target`,
  который место брало раньше: у прочих записей зовётся тот же
  `decide(target)`. Где SPEC требует отказа вместо пропуска, отказ
  включается только при `is_multi`:
  - `acceptance_suite` — не зелёный итог `FULL_SUITE_NOT_STARTED` и
    запись `checks_local компонента` с причиной;
  - `full_suite` — предел `component_limit` компонента задачи, при
    отказе — «прогон не начат» с причиной;
  - `_test_integrity_diff_gate` — `MERGE_PROFILE_REFUSAL_ACTION`;
  - `_external_helpers` — `ComponentsPending`, без отката на область по
    умолчанию;
  - `matrix_refusals` — отказ с причиной;
  - `suite_run` — `_component_command` с `component_limit`;
  - автогейт по правилу планки — граница по компоненту задачи и не
    канарейка;
  - подтяжка — `Refused` с причиной;
  - чекпоинт — причина дописывается в записи восстановления удалений и
    посторонних файлов.
- Гейт исходов (требование 3): `outcome_integrity._components_gate`.
  - Голова, база, затем `gitcmd.diff_names`; сбой — отказ подготовки.
  - Компоненты — `select_components` с потребителями, профили —
    `component_profiles`.
  - Компонент в границе — свой `_gate` и своя запись `PASSED_ACTION`, в
    конец которой дописываются строки «компонент X: вне границы гейта
    исходов».
  - Вне границы все — запись пропуска `journal_skip(«гейт неослабления
    по исходам»)` с «голова <sha>».
  - Отказ — деталь «компонент X: …».
  - База на мерже кешируется на один гейт: фетч main делается один раз.
  - Отказ `for_task` на in_dev — `REFUSAL_ACTION`. На мерже —
    `MERGE_PROFILE_REFUSAL_ACTION` и `sys.exit`, без эскалации.
  - `review_lines` у записи из нескольких компонентов выдаёт последнюю
    запись головы по каждому ключу компонента, а при одной записи
    пропуска — «не исполнялся» и её строки компонентов.
  - В `review._outcome_gate_lines` фильтр по границе профиля задачи
    снят только у записи из нескольких компонентов.
- Планка чужого компонента (требование 4): новый
  `_tests_writing_foreign_plank_gate` стоит первым в списке гейтов выхода
  из `tests_writing`. Он относит файл планки к компоненту X правилом
  планки и отказывает `FAIL_TO_PASS_REFUSAL_ACTION`, если X ≠ Y и X в
  `in_outcome_bounds` — независимо от границы Y. Условие `fsm_advance.py`
  для гейта FAIL_TO_PASS не тронуто.
- Мандаты: `_record_outcome_profiles` (компоненты записи в границе),
  `_path_in_outcome_area`, `_record_test_id_refusal`, покрытие ячейки
  матрицы любым компонентом в границе. Всё это — только у записи из
  нескольких компонентов.
- Расхождения с оценкой бюджета SPEC нет.

## Шаги
1. `project_profile`: `task_components`, `decide_task`, `for_task`,
   `for_task_target`, `for_row`, `is_multi`, `layers_declared`; текст
   `targets.MULTI_COMPONENT_PENDING`.
2. Места таблицы на `for_task_target`/`for_row`: `acceptance`, `amend`,
   `brief`, `checkpoint`, `fsm_advance`, `fsm_autogate`, `fsm_merge_gate`,
   `plank_run`, `preflight`, `pull`, `review`, `role_prompt`, `runner`,
   `suite_run`, `advance_gates/{acceptance,review,test_integrity,zones}`.
   `fsm_merge_gate.py:858/:912/:1093` не тронуты: по SPEC они
   недостижимы.
3. Гейт исходов по компонентам диффа, строки пакета ревьювера.
4. Гейт планки чужого компонента.
5. Мандат и матрица по компонентам записи.
6. Карта `docs/codebase-map.md`, прогоны долгоживущих тестов, планки и
   тестов затронутых модулей.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2, 5 |
| 3 | 3 |
| 4 | 4 |
| 5 | 2 (brief/role_prompt/runner/plank_run) |
| 6 | 6 (тесты test_author: долгоживущие и планка) |
| 7 | 1 |

## Влияние на систему
- Затронуты все места решения профиля в контексте задачи. У записей не
  из нескольких компонентов зовётся тот же `decide(target)`, что прежде:
  новые ветки кода закрыты условием `is_multi`. Это держат AC-2, AC-10,
  AC-15 и AC-26 (эталон пина `test_pin_etalon.py`).
- Гейты не ослабляются. У записи из нескольких компонентов прежние
  пропуски заменены отказами: `_bounds`/гейт исходов, гейт текста на
  мерже, `checks_local`, `_external_helpers`, матрица. Гейт исходов
  гоняет и потребителей по `depends_on`; планка чужого компонента в
  границе получает отказ. Ослабление по SPEC (матрица SPEC, решение
  Оператора 22.10, 1-А) — только годность мандата и покрытие матрицы для
  компонента записи в границе гейта исходов.
- Существующие тесты не правились.
- Откат — revert merge-коммита задачи: схема БД и форматы записей прежних
  записей не меняются. Новые действия журнала не заводятся; запись
  пропуска — прежнее действие `SKIP_ACTION`.

## Риски
- `for_task_target` без `conn` открывает `store.db()` — только у записи
  из нескольких компонентов (`long_lived_manifest`, `amend._task_profile`,
  `plank_run`, `preflight`).
- `_external_helpers` поднимает `ComponentsPending`, если компонент не
  выбран. Все три входа отказывают раньше по тому же `for_task`, так что
  исключение — страховка fail-closed.

## Предложения системе
- В песочнице шага роли нет `cat`/`ls`, а длинный heredoc в Bash
  обрывается «Parser aborted» — большие правки кода приходится делать
  только через Edit. Стоит упомянуть это в скиле или миссии.
