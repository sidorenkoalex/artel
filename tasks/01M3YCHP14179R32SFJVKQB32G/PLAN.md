---
task: 01M3YCHP14179R32SFJVKQB32G
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Наборы моделей: файл model_sets.yaml и команда допуска пары

## Подход

Вся механика — в `orchestrator/models.py` (зона SPEC), рядом с разрешением
моделей, которым определяется «боевая» модель роли. Имена публичной
поверхности заданы долгоживущей планкой
`tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`:
`models.autogate_refusal_blame(text)`, `models.set_admitted(conn, name)`,
команда `artel.py admit [--revoke] <роль> <модель> --basis <текст>`.

Ключевые решения:

1. **Файл** `model_sets.yaml` в корне, три пустых раздела и шапка-комментарий.
   Путь — `config.MODEL_SETS_REL` (строка) и `models.model_sets_path()`,
   читающий `config.ROOT` в момент вызова (тот же приём, что
   `notes._work_dir()`): песочница подменяет `ROOT`, а `ALL_CONFIG_ATTRS`
   в `tests/sandbox.py` трогать не нужно.
2. **Сводка прогона** разбирается из `models_summary` формата канарейки
   (`«роль → модель, …; источник: …»`, `canary._plan_summary`): часть до
   `"; источник: "`, пары через `", "`, роль и модель через `" → "`.
   Прогон пары — `сводка[роль] == модель`; прогон набора — совпадение по
   ВСЕМ ролям набора.
3. **Правило вины** — по префиксам реальных текстов `fsm_autogate`/
   `acceptance` после снятия `«автогейт: »`: «роль» — `критерии manual`,
   `критерии skip`, `полный набор tests/ красный`, `критерий ci не пройден`;
   «пульт/пул» — `перечень долгоживущих файлов не прочитан`, `долгоживущий
   файл планки не прочитан` (ошибки источника планки), `каталог приёмочных
   тестов пуст`, `полный набор tests/ не проверен — worktree задачи не
   заведён`, `прогон полного набора tests/ превысил` (таймаут),
   `acceptance.FULL_SUITE_NO_TESTS_NOTE`, `бюджет задачи исчерпан`, а также
   текст, который `failure_classification.classify_attempt_failure`
   относит к классу; прочее — «не установлена». Пустая причина — `None`
   (отказа не было). Роль проверяется первой.
4. **Чистый прогон** — `verdict=green`, `review_iterations=0`, эскалаций нет
   либо ожидаемая (`expected_escalation` задан, `actual_escalation=1`,
   `marker_mismatch=0`), `autogate_refusal` пуст или «пульт/пул».
5. **Допуск пары**: ≥3 чистых прогона пары, ≥2 различных шаблона среди них,
   ≥1 чистый на шаблоне класса `средний`; для `analyst` — ≥1 прогон пары с
   правильным исходом неясности ТЗ (по SPEC — любой прогон пары, не только
   чистый). Шаблоны чистых прогонов без записи класса называются в перечне
   недостающего по «среднему». Сводка всегда печатает «повторы developer:
   нет данных». Роль сверяется с картой исполнителей (`roles.model_tier`),
   модель — с каталогом (`catalog_model`): опечатка — отказ до записи.
6. **Запись** — пересборка текста файла из разобранного документа
   (шапка-комментарий сохраняется, разделы в порядке `sets`, `pairs`,
   `canary_templates`); скаляр, который `yamlmini.scalar` прочёл бы иначе
   (число, `#`, `:` и т.п.), уходит в кавычки; основание, не переживающее
   обратный разбор, — именованный отказ. Коммит — новая публичная
   `notes.doc_commit_content(rel, content, message)`: та же запись
   `DOC_COMMIT_KIND`, тот же `_run` (окно тишины, удержание, гейт полного
   набора на пути конфигурации); `cmd_doc_commit` переведён на неё же —
   один путь, без копии.
7. **Допуск набора** `set_admitted(conn, name) -> (bool, причина)`: каждая
   пара набора, чья модель отличается от `resolve_role(роль).model`, — в
   `pairs:` с `state: допущена` (боевая модель не разрешилась — пара
   считается не-боевой, fail-closed), и есть строка `verdict=green` со
   сводкой, совпадающей с набором по всем его ролям, на шаблоне класса
   `трудный`. Неизвестный набор — `(False, причина)`.
8. Чтение `canary_runs` — после `store._ensure_canary_tables(conn)` (таблица
   заводится лениво; `store.py` вне зон задачи, публичного читателя всех
   строк нет — см. «Предложения системе»).

Оценка SPEC ($40) не пересматривается.

## Шаги

1. `model_sets.yaml` (три пустых раздела); `config.MODEL_SETS_REL`,
   `model_sets.yaml` в `config.PROTECTED_PATHS` и
   `notes.DOC_COMMIT_CONFIG_PATHS`; `notes.doc_commit_content`.
2. `models.py`: разбор файла и сводки, `autogate_refusal_blame`,
   `clean_run`, проверка допуска пары, `set_admitted`, `cmd_admit`
   (сводка, отказ с перечнем, запись, `--revoke`); диспетчер `admit` и
   справка в `artel.py`.
3. Раздел `docs/stack.md` о файле, допуске пары и набора и команде `admit`.
4. Юнит-тесты `tests/test_model_sets.py` на свойства, не покрытые
   долгоживущим файлом: правило вины на текстах, построенных самими
   производителями (`acceptance.FULL_SUITE_NO_TESTS_NOTE`, таймаут),
   ошибка источника планки, пустая причина; разбор сводки; round-trip
   записи с кавычками; отказ `admit` на модели вне каталога; неизвестный
   набор. Регенерация `docs/codebase-map.md`.
5. Прогон планки (долгоживущий + приёмочный), тестов затронутых модулей
   (`test_models`, `test_doc_commit`, `test_doc_commit_suite_gate`,
   `test_notes`, `test_protected_paths_gate`, `test_ci_protected_paths`,
   `test_artel_role_restricted_commands`, `test_codebase_map`), guard.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1, 2 |
| 4 | 2 |
| 5 | 2 |
| 6 | 2 |
| 7 | 3 |
| 8 | 4, 5 |

## Влияние на систему

- `config.PROTECTED_PATHS` расширяется (только строгость гейта зон и
  `scripts/ci_protected_paths.py` растёт); `DOC_COMMIT_CONFIG_PATHS` —
  новый путь получает тот же канал и тот же гейт полного набора, что
  `models.yaml`.
- `cmd_doc_commit` меняется только выносом хвоста (путь → запись → `_run`) в
  общую функцию; порядок отказов (роль → путь → `--message` →
  `--accept-red` → `--from`) сохраняется — его держат `test_doc_commit*`.
- `admit` не в белом списке ролей (`_ROLE_ALLOWED_COMMANDS`) — под ролью
  отказывает диспетчер; дополнительно `notes.doc_commit_content` несёт тот
  же рубеж `in_role_environment`.
- `canary.py`, `fsm_autogate.py`, `failure_classification.py`, `store.py`
  не меняются (только чтение). Существующие тесты не правятся.
- Откат — revert одного merge-коммита; `model_sets.yaml` пуст, ни один
  путь пульта (кроме `admit`) его не читает до части 2.

## Риски

- `admit` при достаточных прогонах гоняет полный набор `tests/` (гейт
  `doc-commit` на путях конфигурации) — минуты ожидания; это следствие
  требования «тем же механизмом, что doc-commit» и AC-2, флага обхода
  SPEC не вводит.
- Правило вины опирается на тексты отказов `fsm_autogate`: их правка без
  правки списка префиксов уведёт причину в «не установлена» (fail-closed —
  прогон не засчитывается, не наоборот). Юнит-тест сверяет тексты,
  построенные самими производителями, где они доступны константами.
- Пересборка файла теряет комментарии внутри разделов (сохраняется только
  шапка до первого ключа) — файл пишет пульт, Оператор правит его
  `doc-commit`; отмечено в шапке файла.

## Итог реализации (шаг 1 разработчика)

Реализованы шаги 1–4 и прогон шага 5, кроме одного существующего теста
(см. «Эскалация»):

- планка задачи: `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py` и
  `acceptance_tests/test_model_sets_repo_facts.py` — 15 passed;
- свои тесты `tests/test_model_sets.py` — 11 passed; каждый проверен
  временной мутацией (12 мутаций правила вины, чистоты, разбора сводки,
  записи файла, отказов `admit`, неизвестного набора — все красные, код
  возвращён);
- затронутые модули (`test_models`, `test_doc_commit`,
  `test_doc_commit_suite_gate`, `test_notes`, `test_notes_apply`,
  `test_protected_paths_gate`, `test_ci_protected_paths`,
  `test_artel_role_restricted_commands`, `test_codebase_map`,
  `test_yaml_parsing`, `test_stack_*_section`, `test_stack_parity_table`) —
  272 passed; `test_canary_template_flag`, `test_guard_path_mentions`,
  `test_model_tariffs`, `test_plan_appendix`, `test_zones_gate`,
  `test_invariants`, `test_models_doctor`, `test_new_argv_parsing`,
  `test_protected_test_settings` — 227 passed, 1 failed (ниже);
- `docs/codebase-map.md` регенерирован; `model_sets.yaml` добавлен в
  индекс git (`git add`), чтобы AC-1 (`git ls-files`) видел его до
  коммита пульта.

## Предложения системе

- `orchestrator/store.py`: нет публичного читателя всех строк
  `canary_runs` (есть только `green_canary_runs` с фильтром набора) —
  `models` зовёт приватный `_ensure_canary_tables`; к частям 2–3 деления
  стоит завести `store.canary_runs(conn)`.
- `tests/test_protected_test_settings.py` пиннит ЧИСЛО записей
  `config.PROTECTED_PATHS` (`== 17`): любая задача, заводящая новый
  защищённый путь (а `config.py` прямо приглашает вносить его «тем же
  изменением, что создаёт сам файл»), упирается в эскалацию по
  утверждению существующего теста. Сторож «прежние записи не потеряны»
  выразим без числа — `[:12] == LEGACY` уже есть, плюс `assertIn` по
  каждой записи.

## Исполнение ANSWER-1 (шаг 2 разработчика)

Эскалация шага 1 (мандат на утверждение числа записей
`config.PROTECTED_PATHS`; реализация шагов 1–4 закоммичена пультом,
d6984ceb) снята ответом Оператора ANSWER-1, вариант (а). Исполнено строго
в рамках мандата:

- `tests/test_protected_test_settings.py::RealProtectedPathsCompositionTest::test_real_list_keeps_legacy_entries_and_adds_test_settings`:
  старое `self.assertEqual(len(config.PROTECTED_PATHS), 17)` -> новое
  `self.assertEqual(len(config.PROTECTED_PATHS), 18)`, добавлено
  `self.assertIn("model_sets.yaml", config.PROTECTED_PATHS)`; докстринг —
  «плюс пять записей настроек сбора тестов и `model_sets.yaml`». Имя
  метода, `[:12] == LEGACY_PROTECTED_PATHS` и проверки пяти записей
  настроек тестов не тронуты.
- Прогоны (передний план, таймаут 120 с): `test_protected_test_settings`,
  долгоживущий `test_01m3ychp14179r32sfjvkqb32g_model_sets`,
  `test_model_sets`, `test_protected_paths_gate`, `test_ci_protected_paths`
  — 62 passed, 92 subtests passed; `acceptance_tests/` — 2 passed.
- `docs/codebase-map.md` регенерирован (`built_at_sha` после коммита
  пульта).

## Исполнение ANSWER-2 (шаг 3 разработчика, возврат из verifying)

Причина возврата — CI красный на инварианте «SQL только в store.py»
(`tests/test_multitarget.py::SqlOnlyInStoreTest::test_no_sql_outside_store`,
`orchestrator/models.py:1154`). Исправлено в рамках мандата ANSWER-2
(зона `orchestrator/store.py`, только одна функция, без миграций схемы):

- `orchestrator/store.py`: новая `all_canary_runs(conn)` рядом с
  `green_canary_runs` — `_ensure_canary_tables` + `SELECT * FROM
  canary_runs ORDER BY id`;
- `orchestrator/models.py::_canary_rows` зовёт `store.all_canary_runs`;
  обращения к приватному `store._ensure_canary_tables` больше нет (этим же
  закрыто наблюдение «Предложений системе» о публичном читателе
  `canary_runs`; п.8 «Подхода» устарел).
- Класс ошибки: grep `execute|SELECT|INSERT|UPDATE` по
  `orchestrator/models.py`, `notes.py`, `config.py` — других вхождений
  нет. `test_no_sql_outside_store` не менялся.
- `docs/codebase-map.md` регенерирован.

Прогоны (передний план, таймаут 120 с на тест). Полный набор одной
командой отказывает сторож роли в `conftest.py` («полный прогон набора
тестов внутри шага запрещён»), поэтому все файлы `tests/test_*.py`
прогнаны тремя пачками:

- `test_multitarget`, `test_model_sets`, долгоживущий
  `test_01m3ychp14179r32sfjvkqb32g_model_sets`, `test_canary`, `test_pin`,
  `test_codebase_map` + `acceptance_tests/` — 211 passed;
- `tests/test_[0-9a-c]*.py` — 1268 passed, 16 failed: все в
  `test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, причина
  `artel.py approve: команда недоступна процессу роли developer` (тест
  зовёт команды Оператора через CLI, диспетчер отказывает процессу шага
  роли) — окружение шага, не код задачи;
- `tests/test_[d-m]*.py` — 1250 passed, 4 failed: `test_main_ci_line.py`
  (3, тот же отказ процессу роли) и
  `test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`
  (`terminate_process_group` вернул 0 — сигнал группе процессов из
  песочницы шага не доставлен; `liveness.py` задачей не тронут);
- `tests/test_[n-z]*.py` — 1300 passed.

Эти 20 падений не касаются поверхности задачи (`models.py`, `store.py`,
`notes.py`, `config.py`); до возврата CI ветки был красным только на
`test_no_sql_outside_store`. Окончательный вердикт по полному набору —
за CI ветки.
- Предложение системе: ANSWER-2 требует «прогнать полный набор `tests/`»,
  а сторож роли в `conftest.py` такой прогон в шаге запрещает — указание
  Оператора и механика противоречат; падения, зависящие от окружения
  роли (`main_ci`, `main_ci_line`, `liveness`), делают пачечный прогон
  в шаге неокончательным.

## Расширение зон

Пути: orchestrator/store.py

Основание: мандат ANSWER-2/ANSWER-3 («Расширение зон разрешено:
orchestrator/store.py») — инвариант «SQL только в store.py»
(`tests/test_multitarget.py::SqlOnlyInStoreTest::test_no_sql_outside_store`)
требует, чтобы чтение `canary_runs` для `models.py` жило функцией
`store.all_canary_runs`.
