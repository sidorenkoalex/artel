---
task: 01M29BANMM8X8JWJ5GDTJWKB0Z
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: прогоны тестов ролями и шаг CI на минимальной версии Python — через pytest с таймаутом, тем же раннером, что у пульта

## Подход

Единственная правка кода — пункт 5 миссии test_author в
`orchestrator/role_prompt.py`: команда `python3 -m unittest discover -s
<task_ref>/acceptance_tests` заменена на команду той же формы, что
`orchestrator/acceptance.py::_pytest_command` (требование 1), с
таймаутом, подставленным из `stack.PER_TEST_TIMEOUT_SEC` f-строкой, не
литералом — интерпретатор в тексте миссии остаётся литеральным
`python3` (как и была буквальная старая команда), не
`stack.pytest_python_executable()`: миссия — промпт для CLI-агента, а
не код, который сам резолвит venv пульта. Остальной текст пункта 5
(автокоммит, неприкосновенность кода и SPEC.md) не тронут — правка
заменяет ровно одну f-строку команды.

Регрессионный тест в основной набор `tests/` (требование 4, AC-3) —
новый файл `tests/test_role_prompt_test_author_mission.py`: собирает
миссию test_author через `role_prompt.mission_brief_package` (мокая
`brief.test_author_answer_component`, как это уже делает планка
задачи) и проверяет и форму pytest-команды с таймаутом из константы, и
отсутствие `unittest discover`. Отдельного файла не было — заводить его
обязывает само требование 4: без него регрессию (например, случайный
откат на `unittest discover`) после мержа никто не ловит, только
одноразовая планка `tasks/<id>/acceptance_tests/`, которую CI не
гоняет.

Два защищённых пути правит только Оператор — оба приложены ниже
unified-диффом, каждый проверен `git apply --check` на чистом дереве
кодовой ветки этой задачи (без единой правки самого файла в этой
ветке):
- `.github/workflows/ci.yml` (требования 2, AC-5/AC-6): шаг
  «tests.test_invariants на минимальной объявленной версии Python»
  ставит `requirements.lock` для интерпретатора минимальной версии и
  переходит на ту же форму pytest-команды, что и основной прогон, с
  литералом `timeout=120` (YAML не читает Python-константу — то же
  известное ограничение, что уже несёт основной шаг `unit-тесты`,
  тот же комментарий рядом); заданию `python` — `timeout-minutes: 40`
  как страховка от зависшего раннера, не рабочий ориентир.
- `skills/test-authoring.md` и `skills/coding-standards.md`
  (требование 3, AC-7): команды unittest в обоих разделах заменены на
  pytest той же формы с фразой про общий раннер/таймаут с пультом;
  слова «в переднем плане с таймаутом» — в обоих файлах после правки
  (`coding-standards.md` уже нёс эту точную фразу отдельным
  предложением, `test-authoring.md` её не нёс буквально — формулировка
  соседнего предложения слегка сокращена, чтобы нести её тоже, без
  потери смысла: «в переднем плане и с явным таймаутом команды» ->
  «в переднем плане с таймаутом (параметр `timeout` команды)»).

## Шаги

1. `orchestrator/role_prompt.py`: импорт `stack`, пункт 5 миссии
   test_author — pytest-команда с `stack.PER_TEST_TIMEOUT_SEC` вместо
   `unittest discover`.
2. `tests/test_role_prompt_test_author_mission.py` — новый
   регрессионный тест основного набора на форму команды и на
   отсутствие `unittest discover`.
3. Приложения к этому PLAN.md ниже (правит Оператор отдельным MR,
   защищённые пути `.github/`, `skills/`):
   - дифф `.github/workflows/ci.yml`;
   - дифф `skills/test-authoring.md` + `skills/coding-standards.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 3 (приложение `.github/workflows/ci.yml`) |
| 3 | 3 (приложение `skills/test-authoring.md`, `skills/coding-standards.md`) |
| 4 | 2 |

## Влияние на систему

Зона правки по SPEC — `orchestrator/role_prompt.py`, `tests/`;
приложенные диффы — вне зоны кода этой роли (защищённые пути),
применяет их Оператор. Изменение `role_prompt.py` — замена ровно одной
f-строки команды внутри одной ветки `if role == "test_author"`: три
другие роли (`analyst`, `developer`, ревьювер) не затронуты ни по
тексту, ни по коду — правка синтаксически локальна одному блоку.
Публичный контракт `mission_brief_package` (сигнатура, тройка
`(mission, brief_text, package)`) не изменился — остальные
потребители (`orchestrator/runner.py`) читают то же самое.

Существующие тесты `orchestrator/role_prompt.py` (бриф/миссии всех
четырёх ролей) не ослаблены и не удалены этой задачей — только
добавлен новый файл `tests/test_role_prompt_test_author_mission.py`
(AC-4). Инвариант «pytest-таймаут отдельного теста читается из
`stack.PER_TEST_TIMEOUT_SEC`, не литерала» проверен подменой константы
на 999 — тест ловит и литеральную регрессию, и рассинхрон при будущей
правке `stack.PER_TEST_TIMEOUT_SEC` без обновления миссии.

Откат — один revert коммита этой задачи: `role_prompt.py` возвращается
к прежней f-строке, новый тестовый файл удаляется, оба защищённых
диффа откатывает тем же MR Оператор (или их можно вовсе не
применять — код-часть задачи от них не зависит).

Известное ограничение (по образцу прежней задачи
01M291M2Z76M84GVP25J387A66): значение таймаута в приложенном диффе CI
(`timeout=120`) — литерал, дублирующий `stack.PER_TEST_TIMEOUT_SEC` в
YAML; сам дифф — защищённый путь, эта роль не вправе заводить там код,
читающий Python-константу на этапе генерации workflow.

## Риски

- Приложенные диффы — текст внутри этого PLAN.md, не факт применения:
  до коммита Оператора по защищённым путям `.github/workflows/ci.yml`
  и `skills/*.md` остаются старыми (unittest, без
  `timeout-minutes`) — код-часть задачи (требования 1, 4) от этого не
  зависит и работает независимо от того, когда Оператор применит
  приложения.
- Изменение формулировки `skills/test-authoring.md` («в переднем плане
  и с явным таймаутом команды» -> «в переднем плане с таймаутом»)
  — минимальное урезание слова «явным»; смысл (таймаут — параметр
  команды, до 10 минут) сохранён следующим же словом в скобках.

## Проверено исполнением

- `python3 -m pytest tasks/01M29BANMM8X8JWJ5GDTJWKB0Z/acceptance_tests
  -p no:cacheprovider -p timeout -o timeout=120 -v` — 5 тестов, все
  зелёные (было красных 3 из 5 до правки `role_prompt.py`, по докстрокам
  планки).
- `python3 -m pytest tests/test_role_prompt_test_author_mission.py
  tests/test_agent_prompt.py tests/test_brief.py
  tests/test_advance_refusal_history.py -p no:cacheprovider -p timeout
  -o timeout=120 -q` — 44 теста (12 + 6 subtests + 32), все зелёные.
- Оба приложенных unified-диффа проверены `git apply --check` на чистом
  дереве кодовой ветки этой задачи (без единой правки затрагиваемых
  файлов на момент проверки).

## Приложение 1: дифф `.github/workflows/ci.yml`

Защищённый путь — правит только Оператор отдельным MR. Проверено
`git apply --check` на чистом дереве кодовой ветки этой задачи.

```diff
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index e29195f5..48e95bc2 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -193,6 +193,9 @@ jobs:
     # `changes` даёт пустой output, и тесты ИДУТ (fail-closed).
     if: ${{ !cancelled() && needs.changes.outputs.code != 'false' }}
     runs-on: ubuntu-latest
+    # Страховка от зависшего раннера (01M29BANMM8X8JWJ5GDTJWKB0Z) — не
+    # рабочий ориентир для длительности job, реальные прогоны много короче.
+    timeout-minutes: 40
     steps:
       - uses: actions/checkout@v4
       - name: версия Python из манифеста стека (01M1RDCCKBQMJ5G2K9ANJP059H)
@@ -232,8 +235,14 @@ jobs:
       - uses: actions/setup-python@v5
         with:
           python-version: ${{ steps.stack-python-min.outputs.version }}
+      - name: зависимости из файла закреплённых версий для минимальной версии Python (01M29BANMM8X8JWJ5GDTJWKB0Z)
+        run: python3 -m pip install -r requirements.lock
       - name: tests.test_invariants на минимальной объявленной версии Python (AC-2)
-        run: python3 -m unittest tests.test_invariants -v
+        run: |
+          # Литерал timeout=120 дублирует stack.PER_TEST_TIMEOUT_SEC —
+          # известное ограничение (YAML не читает Python-константу), тот
+          # же класс, что и в шаге unit-тестов выше.
+          python3 -m pytest tests/test_invariants.py -p no:cacheprovider -p timeout -o timeout=120
 
   protected-paths:
     name: Enforcement, конфиги системы меняет только Оператор
```

## Приложение 2: дифф `skills/test-authoring.md`

Защищённый путь — правит только Оператор отдельным MR. Проверено
`git apply --check` на чистом дереве кодовой ветки этой задачи.

```diff
diff --git a/skills/test-authoring.md b/skills/test-authoring.md
index 7dc92d81..f829058b 100644
--- a/skills/test-authoring.md
+++ b/skills/test-authoring.md
@@ -148,15 +148,17 @@ T062, когда Оператор поднял потолок до 5 — main п
 от `config.<имя>`, а не от сегодняшнего значения.
 
 ## Перед завершением
-`python3 -m unittest discover -s tasks/<id>/acceptance_tests` — все
+`python3 -m pytest tasks/<id>/acceptance_tests -p no:cacheprovider -p
+timeout -o timeout=120` — тот же раннер и таймаут, которыми пульт
+принимает планку (`orchestrator/acceptance.py::_pytest_command`); все
 написанные тесты обязаны быть синтаксически рабочими (падать на
 отсутствующей пока реализации — нормально, падать на опечатке в самом
 тесте — нет), краснота каждого файла объяснена маркером (см. выше).
 Коммитить каталог в ветку задачи не нужно — автокоммит оркестратора сам
 перенесёт его в артефактную ветку (SPEC 01M1NKTF173WV5CPDZ1C3WW69K).
 
-Прогоны — только в переднем плане и с явным таймаутом команды
-(параметр `timeout`, до 10 минут), по одному файлу планки. Команда,
+Прогоны — только в переднем плане с таймаутом (параметр `timeout`
+команды, до 10 минут), по одному файлу планки. Команда,
 которую клиент увёл в фон, результата шагу не даёт: не жди её и не
 планируй «проснуться позже» — шаг заканчивается вместе с твоим
 последним сообщением (инцидент 05.09: test_author написал тесты по
```

## Приложение 3: дифф `skills/coding-standards.md`

Защищённый путь — правит только Оператор отдельным MR. Проверено
`git apply --check` на чистом дереве кодовой ветки этой задачи.

```diff
diff --git a/skills/coding-standards.md b/skills/coding-standards.md
index c54b248e..af778ac9 100644
--- a/skills/coding-standards.md
+++ b/skills/coding-standards.md
@@ -75,8 +75,10 @@ PLAN вправе один раз, при первой сдаче, поднят
   и записывай итог каждого.
   Полный набор `tests/` в шаге НЕ запускай: он идёт 3–4 минуты и
   уводится в фон, а его и так гоняет CI на каждый пуш ветки. В шаге —
-  планка задачи и тесты затронутых модулей (`python3 -m unittest
-  tests.test_<модуль>`), каждый вызов в переднем плане с таймаутом.
+  планка задачи и тесты затронутых модулей (`python3 -m pytest
+  tests/test_<модуль>.py -p no:cacheprovider -p timeout -o
+  timeout=120` — тот же раннер и таймаут, которыми пульт принимает
+  планку), каждый вызов в переднем плане с таймаутом.
   Решение Оператора 05.09: восемь таймаутов шагов за сутки на ожидании
   полного набора.
 
```

## Предложения системе
<Пусто.>
