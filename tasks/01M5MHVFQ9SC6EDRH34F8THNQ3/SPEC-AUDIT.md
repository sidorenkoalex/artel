---
task: 01M5MHVFQ9SC6EDRH34F8THNQ3
type: spec_audit
author_role: spec_auditor
status: ready
verdict: pass
signals: в) пути-признаки (тесты): tests/.
spec_sha: deba830b9f956628657846e45d627743714812da
schema_version: 5
---

# SPEC-AUDIT: Одна функция открытия БД пульта только на чтение вместо пяти копий

Круг 2: SPEC после решений Оператора на гейте SPEC №1 (23.10.2026).

## ТЗ и SPEC
- ТЗ требование 1 → SPEC требование 1 дословно; свойства (а)–(в), (д) ТЗ
  требования 4 → AC-1, AC-2, AC-3, AC-5; (г) → AC-4.
- ТЗ требование 2 → SPEC требование 2 + AC-6 (вызов из пяти мест) + AC-7
  (тексты отказов/коды выхода).
- ТЗ требование 3 (grep) заменено формулировкой по AST — так велит решение
  Оператора №1 п.2; AC-4 держит его целиком. Не отклонение.
- ТЗ ограничение зон по смыслу расширено в «Не входит» (переменная `uri = …`,
  импорт `store`) — решение Оператора №1 п.1, перенесено дословно.
- Решение №1 п.3 (компонент пути, меняемый `resolve()`) — в AC-3.
- ТЗ требование 5 → SPEC требование 5; «Только чтение»/«Не входит» ТЗ — в
  «Не входит» SPEC. Требований сверх ТЗ и решений нет (AC-6/AC-7 —
  проверяемая форма ТЗ требования 2).

## Факты против кода
Подтверждено по рабочему каталогу:
- `?mode=ro` ровно в пяти строках: `orchestrator/store.py:337`,
  `orchestrator/knowledge_cards.py:767`, `orchestrator/suite_run.py:179`,
  `orchestrator/preflight.py:84`, `scripts/test_rule_stats.py:72`. Прочие
  упоминания (`artel.py:2177,2179` — комментарии; докстринги
  `store.py:332`, `knowledge_cards.py:762`, `suite_run.py:274`,
  `preflight.py:15`, `test_rule_stats.py:8,69`) пишут `mode=ro` без `?` и
  AC-4 не задевают.
- Поведение вызывающих совпадает с таблицей ТЗ: `db_usable` —
  `is_file()`→False, `except sqlite3.Error`→False (`store.py:334-340`);
  knowledge — `sys.exit` «knowledge: БД пульта … не найдена»
  (`knowledge_cards.py:766`), `row_factory=Row` (:768); suite_run —
  без проверки файла (`suite_run.py:178-182`); preflight — `None` и код 2
  (`preflight.py:80-95`); journal — `StatsError` до и после connect
  (`test_rule_stats.py:70-82`).
- `store.py` функции открытия на чтение не несёт; `db()` — на запись.
- `scripts/test_rule_stats.py` импортирует `orchestrator.config` и
  `orchestrator.advance_gates.test_integrity` (:41-43), который сам
  импортирует `store` (карта) — новый `from orchestrator import store`
  цикла/новой тяжести не вносит.
- Существующие шпионы патчат атрибут модуля `sqlite3.connect` глобально:
  canary AC-11 (`tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py:484-496`,
  разрешён вызывающий `orchestrator.store` — `db_readonly` в store его
  сохраняет), knowledge AC-5 (`…knowledge_command.py:641-649`), developer
  suite-run AC-1 (`…developer_suite_run.py:344-358`), rule_stats AC-9
  (`…rule_stats.py:437-445`, `mock.patch("sqlite3.connect")`). Вызов
  через `store.db_readonly` с `sqlite3.connect(..., uri=True)` атрибутом
  модуля их не ломает.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | убран `?mode=ro` (запись проходит); `row_factory` не ставится при `rows=True` или ставится при `rows=False` |
| AC-2 | да | `db_readonly` зовёт `store.db()`/`connect` без `mode=ro` (файл создаётся) или глушит исключение |
| AC-3 | да | убран `.resolve()` (симлинк/`..` даёт иную строку); `uri` передан позиционно; иной суффикс |
| AC-4 | да | возвращена своя копия `?mode=ro` в любом из пяти мест или новом модуле |
| AC-5 | да | `path=config.DB` значением по умолчанию (чтение при импорте) |
| AC-6 | да | одно из пяти мест открывает соединение мимо `store.db_readonly`; `db_usable`/`journal` без `rows=False`, `journal` без `path=db_path` |
| AC-7 | да (зелёный с рождения) | перенос проверки файла/перехвата в `db_readonly` меняет текст или код отказа |

Замечание (не отклонение): AC-6 не фиксирует `rows` для knowledge/suite_run/
preflight; мутацию «`rows=False` там» держат существующие тесты этих команд
(обращение к строке по имени) и требование 5.

## Зоны
Зоны SPEC (`store.py`, `knowledge_cards.py`, `suite_run.py`, `preflight.py`,
`scripts/test_rule_stats.py`, `docs/codebase-map.md`, `tests/`) покрывают
всё, что меняют требования 1–4; карта — для регенерации после правки `*.py`.
Защищённые пути (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`,
`.github/`) не затронуты; песочница ролей не расширяется.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Открытие БД в `canary runs` (не меняется) | `sqlite3.connect` только из store — `tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py:476` | да | тот же тест без правки | остаётся |
| knowledge: открытие через store | `mode=ro` + `uri=True` — `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py:629` | да | тот же тест + AC-6 | остаётся |
| suite_run: `_readonly_db` через store | `mode=ro` у developer — `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py:325`; `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py` | да | те же тесты + AC-6 | остаётся |
| preflight: открытие через store | код 2 без БД — `tests/test_preflight.py::test_missing_db_exits_2_and_creates_no_db`; `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py::test_ac8_readonly_db_file_same_output_and_code` | да | те же тесты + AC-7 | остаётся |
| test_rule_stats.journal через store | readonly-соединение — `tests/test_01m3xr84299td6v6e16d2pnxh4_rule_stats.py:415`; отказ без БД — `tests/test_test_rule_stats.py::FailClosedTest::test_missing_db_is_exit_2_without_summary` | да | те же тесты + AC-7 | остаётся |
| `db_usable` через store | подмены `store.db_usable` — `tests/test_reference_command.py` | да | тот же тест + AC-7 | остаётся |

Существующие тесты не правятся (SPEC требование 5); раздел «Меняемое
поведение» не нужен и отсутствует.

## Пути обхода гейтов
- Обход линтера AC-4 склейкой `"?mode" + "=ro"` возможен, но исполнителю он
  ничего не даёт: AC-6 требует вызова `store.db_readonly` из каждого из пяти
  мест, AC-3 фиксирует точную строку внутри `db_readonly`. Пути обхода
  смысла задачи не найдено.
- Перенос проверки файла в `db_readonly` противоречит требованию 1 и ловится
  AC-2 (`OperationalError` наружу) и AC-7.

## Вердикт
pass — отклонений нет. Оба отклонения круга 1 сняты решением Оператора №1
(«Не входит» SPEC — расширенные правки вызывающих; требование 3 — по AST, держится
AC-4), заметка к AC-3 внесена. Факты SPEC о коде подтверждены (см. «Факты против
кода»). Замечание без статуса отклонения: AC-6 не задаёт `rows` у трёх
вызывающих — держится существующими тестами.
