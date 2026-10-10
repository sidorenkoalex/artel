---
task: 01M4K2767FXKZ8EW7AME81SZ9N
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Полный прогон — предел notes из профиля, сигнал «длительность близка к пределу»

## Подход
Одна точка на все три потребителя — `acceptance.run_full_suite`: гейт
(`full_suite`), `suite-run` (`suite_run._run`/`_base`) и `notes` идут
через неё, поэтому сигнал заводится там, а `suite_run.py` (только чтение)
не правится.

- Длительность меряется в `run_full_suite` всегда (`time.monotonic` до и
  после прогона); у наблюдаемого прогона (гейт, `suite-run`) берётся
  `duration_seconds` уже существующих метрик `_suite_metrics`.
- `_signal_near_limit(root, duration, limit, metrics)`: при
  `duration >= SUITE_NEAR_LIMIT_RATIO * предел` — строка вывода
  «полный прогон: длительность близка к пределу: … длился N с — P% предела
  L с (источник: …), порог 80%; нагрузка: …», запись журнала задачи
  (action `SUITE_NEAR_LIMIT_ACTION`, та же строка данных) и алерт
  kind=trigger `source=suite.near_limit` проекта, если открытого алерта с
  этим источником у target'а нет (один на проект, ANSWER-1 п.2; дедуп по
  источнику, а не по тексту `raise_alert` — текст несёт длительность).
  Сигнал не трогает `green`/`output` — исход прогона прежний; сбой записи
  ловится и дописывается в строку вывода.
- Задача прогона: `run_full_suite` её не знает, а сигнатуры
  `suite_run.py` менять нельзя. Её знает замок полных прогонов машины —
  держатель пишет `task_id` (гейт — `full_suite`, `suite-run` — фоновый
  процесс через `adopt`, `notes` — `None`). Новая
  `suite_lock.my_task_id()` — задача замка, если его держит текущий
  процесс (зона `suite_lock.py` нужна для сигнала, ANSWER-1 п.1). Target —
  `store.task_target` задачи, у `notes` — `config.DEFAULT_TARGET`.
- Повтор упавших (`suite-run --failed`, `targets` — id тестов) — не полный
  прогон: сигнал только при `targets == ("tests",)`.
- `notes._suite_limit_kwargs()`: предел `project_profile.full_suite_limit
  (config.DEFAULT_TARGET)`, строка вывода «полный набор tests/: предел L с
  (источник: …)»; предел «config» не передаётся (его подставит сама
  `run_full_suite`, как у `acceptance.full_suite`) — шпион `spy_suite(root)`
  `tests/test_doc_commit_suite_gate.py` остаётся без правки. Нечитаемый
  профиль (`TargetsError`) команду не роняет: запасной предел, причина в
  выводе.
- Порог — `acceptance.SUITE_NEAR_LIMIT_RATIO = 0.8` (вне `config.py`), имя
  названо в строке №32 `docs/triggers.md`.
- Долгоживущий тест задачи (`GateNearLimitTest.threshold_constant`) читает
  живой `docs/triggers.md` — линт `tests/test_invariants.py::
  DeterministicTestsLintTest::test_tests_tree_has_no_wall_clock_waits_or_live_file_reads`
  на нём красный уже на голове ветки (до кода). `tests/test_invariants.py`
  — защищённый путь: исключение с обоснованием — приложением Оператора
  ниже, тем же каналом, что у 01M4JN2EDQP8Q3WVYK0TS95ZVC/01M4G8MNEPECNX1TCEDW4T4RPX.

## Шаги
1. `orchestrator/suite_lock.py`: `my_task_id()`.
2. `orchestrator/acceptance.py`: замер длительности в `run_full_suite`,
   `SUITE_NEAR_LIMIT_RATIO`/`_ACTION`/`_SOURCE`, `_load_text`,
   `_signal_near_limit`.
3. `orchestrator/notes.py`: `_suite_limit_kwargs()` и вызов
   `run_full_suite(work_dir, **_suite_limit_kwargs())`.
4. `docs/triggers.md`: строка №32; `docs/codebase-map.md` регенерирован.
5. `tests/test_suite_near_limit.py`: `my_task_id` только у своего замка;
   повтор упавших у предела не сигналит, полный прогон — сигналит;
   нечитаемый профиль у `notes` — запасной предел с источником «config».
6. Приложение Оператора: исключение линта для `threshold_constant`.

Проверено: долгоживущий файл задачи — 12 passed; 22 файла тестов
затронутых модулей (acceptance, suite_lock, suite_run, doc_commit*,
full_suite_*, 01m46d5t8…, 01m4araxf…, 01m462qa…, pycache, fsm_autogate,
01m4fytb8…, 01m49b90…, 01m48wt5x7…, 01m46c776…suite_run_appendix) —
237 passed; `tests/test_invariants.py` с приложением — 79 passed;
`tests/test_suite_near_limit.py` — 3 passed, каждый тест краснеет на своей
временной мутации (снята сверка pid в `my_task_id`; снято условие
`targets`; `except TargetsError` заменён посторонним исключением).
`git apply --check` приложения на чистом дереве — проходит.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 3 |
| 2 | 1, 2 |
| 3 | 2 |
| 4 | 4 |
| 5 | 2 (пределы, замок, исход прогона не меняются) |
| 6 | — (существующие методы `tests/` не менялись; приложение добавляет запись перечня исключений, не меняет утверждений) |

## Влияние на систему
- Исход прогона не меняется: `_signal_near_limit` не трогает `green` и
  `output`, вызывается после прогона; отказ по истечению предела остаётся
  отказом (таймаут — тоже прогон «≥ 80% предела», он даёт и сигнал).
- Пределы не повышаются: у гейтов и `suite-run` предел прежний; у `notes`
  предел профиля вместо запасного — значение профиля, как у гейтов.
- Замок `suite_lock` не снимается раньше: добавлено только чтение.
- Запись журнала/алерта — только при пригодной БД (`store.db_usable()`),
  прямой вызов без БД state.db не создаёт; сбой записи прогон не роняет.
- Приложение к `tests/test_invariants.py` добавляет одну запись в перечень
  исключений линта с обоснованием (предмет приёмки — живой документ, как
  у соседних записей о `docs/operator-session.md`); иных проверок не
  снимает.
- Откат — revert merge-коммита; данные: открытые алерты `suite.near_limit`
  подтверждаются `alert-ack`.

## Риски
- Прогоны с крошечным пределом в чужих тестах (таймаут за 1–3 с) теперь
  печатают строку сигнала и при пригодной БД песочницы заводят алерт.
  Тесты затронутых модулей зелёные; полный набор — командой пульта.

## Приложение: исключение линта инвариантов для теста строки триггера

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index 86dfb77b..514349a9 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -2014,6 +2014,10 @@ class DeterministicTestsLintTest(unittest.TestCase):
             "docs/operator-session.md и docs/stack.md",
         "tests/test_01m4c954hbjwegd3azs7q3eha4_documentation.py::DocumentationAcceptanceTest::test_ac16_reviewed_position_is_shared_by_chats":
             "предмет приёмки — правило в живом docs/operator-session.md",
+        "tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py::GateNearLimitTest::threshold_constant":
+            "предмет приёмки (AC-10) — строка триггера в живом "
+            "docs/triggers.md, называющая константу порога кода; документ "
+            "правится Оператором, копии нет",
         "tests/test_models.py::DocsTemplateTest::test_example_file_equals_the_template":
             "сверяет пример docs/reference/models-local.example.yaml с "
             "шаблоном кода — расхождение живого файла и есть находка",
```

## Предложения системе
- test_author (`skills/test-authoring.md`): долгоживущий тест задачи,
  читающий живой документ репозитория, краснит линт
  `tests/test_invariants.py` (`_EXCEPTIONS`) уже в коммите test_author;
  запись исключения достаётся разработчику приложением. Стоит либо
  проверять линт на выходе `tests_writing`, либо давать test_author
  готовить это приложение самому.
