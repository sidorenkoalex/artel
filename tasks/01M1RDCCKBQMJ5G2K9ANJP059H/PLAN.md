---
task: 01M1RDCCKBQMJ5G2K9ANJP059H
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: объявленный стек пульта, часть 2 — CI на объявленной версии Python

## Подход

Эскалация предыдущей итерации закрыта ANSWER-1.md: Оператор дал мандат
на минимальное расширение зон на `orchestrator/stack.py` (вариант (a)
обоих вопросов) — раздел «## Расширение зон» ниже фиксирует это.

Часть 1 («манифест стека») смержена в main; рабочая ветка была заведена
до того мержа и позже ещё раз отстала (main продвинулся коммитами задач
01M1R9YEK08XEQWBFX0929WFVJ/01M1RA0N6FCFEQBB82K58GM12X/др. после первой
подтяжки этой ветки) — вторая подтяжка `git merge origin/main`
(коммит `6c3a55eb`) довела ветку до актуального `main` (`1aed801c`);
единственный конфликт (`docs/codebase-map.md`) разрешён регенерацией
(`python3 scripts/codebase_map.py`) тем же коммитом
(skills/conventions-core.md — подтяжка main, меняющая `*.py`, требует
регенерации карты отдельным шагом).

Реализация:
- `orchestrator/stack.py`: добавлены `CURRENT_STABLE_PYTHON = (3, 13)`
  (ANSWER-1, ответ 2 — версия основных джобов CI/локальной разработки)
  и `python_version_string()`, возвращающая её в формате `major.minor`
  (идиома требования 1 SPEC: `from orchestrator import stack;
  print(stack.python_version_string())`). Существующая публичная
  поверхность части 1 (`REQUIRED_PYTHON`, `REQUIRED_TOOLS`,
  `THIRD_PARTY_EXCEPTIONS`, `check_stack`) не тронута —
  `tests/test_stack.py` (постоянная регрессия части 1) зелёный без
  изменений.
- `scripts/stack_ci.py` (новый): без флагов печатает
  `stack.python_version_string()` (версия основных джобов CI, требование
  1); с флагом `--min` печатает `stack.REQUIRED_PYTHON`, отформатированную
  так же (`major.minor`) — вторая нога матрицы требования 2. Вся логика
  чтения манифеста и форматирования — здесь, не в `ci.yml` (требование
  3/AC-6): диф-приложение только вызывает скрипт и передаёт его вывод в
  `actions/setup-python` через `$GITHUB_OUTPUT`.
- `tests/test_stack_ci.py` (новый): сравнивает вывод скрипта (сабпроцессом,
  оба режима) с `orchestrator.stack.python_version_string()`/
  `REQUIRED_PYTHON`, вызванными в этом же процессе — расхождение (в т.ч.
  через `mock.patch.object(stack, "python_version_string", ...)`) ловится
  (AC-4; согласовано с уже залоченным `acceptance_tests/
  test_ac4_stack_ci_matches_manifest.py`, который гоняет именно этот файл
  как чёрный ящик и проверяет тот же контракт).
- Диф-приложение к `.github/workflows/ci.yml` (раздел «Приложение» ниже):
  во все три джоба, исполняющие `python3` (`guard`, `python`,
  `codebase-map` — остальные джобы `id-format-greplint`/
  `canary-guid-leak`/`protected-paths` используют только `git`/`grep`,
  `python3` не исполняют), добавлен шаг чтения версии через
  `python3 scripts/stack_ci.py` (output шага) и `actions/setup-python@v5`
  перед первым `python3`-шагом джоба. Джоб `python` дополнительно, ПОСЛЕ
  основного прогона `discover -s tests`, переключает интерпретатор на
  минимальную версию (`scripts/stack_ci.py --min`) вторым вызовом
  `actions/setup-python@v5` и гоняет `python3 -m unittest
  tests.test_invariants -v` уже на ней (требование 2/AC-2: «шаг» —
  прямой вызов на конкретной версии, без `strategy.matrix`, чтобы не
  дублировать весь `discover -s tests` дважды сверх необходимого AC-2
  минимума — тот же дух «минимально необходимого», что AC-6 явно требует
  для самого диффа). Литерала версии Python в `ci.yml` нет нигде — обе
  версии получены вызовом `scripts/stack_ci.py`/`scripts/stack_ci.py
  --min`.

`git apply --check` дифа на чистом `main` (отдельный `git worktree` от
`main` @ `1aed801c`, без изменений рабочего дерева этой ветки) —
пройден, `APPLY_CHECK_OK` (AC-5). Диф сгенерирован временной правкой
`.github/workflows/ci.yml` в рабочем дереве этой роли с последующим
`git checkout -- .github/workflows/ci.yml` — сам файл в код этой ветки
НЕ закоммичен (защищённый путь, skills/conventions-core.md); применяет
Оператор.

## Расширение зон

Пути: orchestrator/stack.py

Мандат: ANSWER-1.md, вариант (a) обоих вопросов («Расширение зон
разрешено: orchestrator/stack.py») — минимальное расширение на
`python_version_string()` и `CURRENT_STABLE_PYTHON`, без изменения
существующей публичной поверхности части 1.

## Шаги

1. `orchestrator/stack.py`: `CURRENT_STABLE_PYTHON` и
   `python_version_string()` (см. «Подход», «Расширение зон»).
2. `scripts/stack_ci.py`: `main()`/вывод версии, `--min` для нижней
   границы матрицы.
3. `tests/test_stack_ci.py`: сверка вывода скрипта с манифестом,
   падение при расхождении (AC-4).
4. Диф-приложение к `.github/workflows/ci.yml` (раздел «Приложение»):
   `setup-python` перед каждым python3-джобом + шаг матрицы требования
   2 в джобе `python`; `git apply --check` подтверждён.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2, 4 |
| 2 | 1, 2, 4 |
| 3 | 2, 4 |
| 4 | 2, 3 |

## Влияние на систему

`orchestrator/stack.py`: расширение аддитивное — новая константа и новая
функция, ни одна существующая публичная точка входа части 1
(`REQUIRED_PYTHON`, `REQUIRED_TOOLS`, `THIRD_PARTY_EXCEPTIONS`,
`check_stack`) не изменена и не переименована; `tests/test_stack.py`
(постоянная регрессия части 1) прогнан зелёным без правок с его стороны.
`scripts/stack_ci.py`/`tests/test_stack_ci.py` — новые файлы, не
пересекаются с существующими гейтами; используют только stdlib и
`orchestrator.stack` — не создают новую зависимость сверх инварианта
«сторонних пакетов нет» (docs/invariants.md, подтверждено прогоном
`tests.test_invariants::StdlibOnlyImportsInvariantTest` после добавления
файлов — зелёный).

Диф-приложение к `.github/workflows/ci.yml` не меняет ни одного
существующего шага и не убирает ни одной существующей проверки — только
добавляет шаги `setup-python`/чтения версии перед уже существующими
python3-шагами трёх джобов и один дополнительный шаг проверки
`tests.test_invariants` на нижней границе версии в джобе `python`;
порядок и содержимое существующих шагов (guard.py, py_compile, discover
-s tests, снимок/сверка ссылок репозитория, генератор карты и сверка
свежести) не тронуты. Применяет диф Оператор отдельным MR — сам файл в
этой ветке не менялся (см. `git status` в конце шага).

Подтяжка main (коммит `6c3a55eb`) не меняла ничего, кроме объединения
уже смерженных в main изменений и регенерации карты (сверено
построчно — единственный конфликт был в `docs/codebase-map.md`,
разрешён регенерацией).

## Риски

- Диф-приложение к `ci.yml` содержит `python3 scripts/stack_ci.py` —
  до применения Оператором `scripts/stack_ci.py` уже должен быть в
  main (эта же ветка его добавляет) — порядок применения (сначала мерж
  этой задачи, затем диф Оператором) уже заложен в SPEC («Не входит»:
  «Применение дифа к ci.yml… делает Оператор по диф-приложению из
  PLAN.md» — после мержа кода задачи).
- Второй `setup-python@v5` в джобе `python` (переключение на
  минимальную версию) физически меняет активный интерпретатор для всех
  ПОСЛЕДУЮЩИХ шагов джоба — в текущем дифе после него шагов больше нет
  (это последний шаг джоба), поэтому побочных эффектов на остальные
  шаги того же джоба нет; если в будущем в конец джоба `python` добавят
  шаг после этого — он неожиданно окажется на минимальной версии, а не
  на текущей стабильной. Отметил в диффе комментарием у последнего шага
  нет — минимальность дифа (AC-6) не позволяет добавлять предупреждающий
  комментарий сверх необходимого; фиксирую риск здесь для истории.

## Предложения системе

- SPEC 01M1RDCCKBQMJ5G2K9ANJP059H объявляет `zones` без
  `orchestrator/stack.py`, но требование 1 буквально задаёт идиому
  `stack.python_version_string()`, которой в части 1 нет — класс «zones
  SPEC не покрывают маленькое расширение API модуля, который требование
  того же SPEC подразумевает» стоит иметь в виду analyst'у при нарезке
  многочастных задач, зависящих от API предшественника.
- За время работы над этой веткой main продвинулся ещё на десяток
  коммитов дважды подряд (первая подтяжка — часть 1, вторая — уже после
  неё) — для многочастных задач с паузой на эскалацию расстояние до
  main успевает вырасти быстрее, чем ожидается: возможно, стоит явно
  упомянуть в conventions-core.md, что подтяжка main перед сдачей — не
  разовое действие «в начале шага», а то, что стоит повторить прямо
  перед PLAN.md `status: ready`, если между началом работы и сдачей был
  долгий блокирующий простой (эскалация).

## Приложение: диф `.github/workflows/ci.yml`

`git apply --check` на чистом `main` (`1aed801c`, отдельный
`git worktree`) — пройден.

```diff
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index 3b662dff..ef5a705b 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -14,6 +14,12 @@ jobs:
     runs-on: ubuntu-latest
     steps:
       - uses: actions/checkout@v4
+      - name: версия Python из манифеста стека (01M1RDCCKBQMJ5G2K9ANJP059H)
+        id: stack-python
+        run: echo "version=$(python3 scripts/stack_ci.py)" >> "$GITHUB_OUTPUT"
+      - uses: actions/setup-python@v5
+        with:
+          python-version: ${{ steps.stack-python.outputs.version }}
       - name: guard.py по всем артефактам задач
         run: |
           # Ветка task/** — не источник истины для tasks/<id>/ (SPEC
@@ -146,6 +152,12 @@ jobs:
     runs-on: ubuntu-latest
     steps:
       - uses: actions/checkout@v4
+      - name: версия Python из манифеста стека (01M1RDCCKBQMJ5G2K9ANJP059H)
+        id: stack-python
+        run: echo "version=$(python3 scripts/stack_ci.py)" >> "$GITHUB_OUTPUT"
+      - uses: actions/setup-python@v5
+        with:
+          python-version: ${{ steps.stack-python.outputs.version }}
       - run: python3 -m py_compile orchestrator/artel.py scripts/guard.py
       - name: снимок ссылок репозитория до прогона тестов (SPEC 01M1KVGD18P9H5WR7VM8TGPV1T, требование 1)
         run: git for-each-ref --format='%(refname) %(objectname)' refs/heads/ refs/artifacts/ > /tmp/refs-before.txt
@@ -165,6 +177,14 @@ jobs:
             echo "::error::прогон tests/ изменил набор ссылок репозитория — см. diff выше"
             exit 1
           fi
+      - name: минимальная версия Python из манифеста (01M1RDCCKBQMJ5G2K9ANJP059H, требование 2)
+        id: stack-python-min
+        run: echo "version=$(python3 scripts/stack_ci.py --min)" >> "$GITHUB_OUTPUT"
+      - uses: actions/setup-python@v5
+        with:
+          python-version: ${{ steps.stack-python-min.outputs.version }}
+      - name: tests.test_invariants на минимальной объявленной версии Python (AC-2)
+        run: python3 -m unittest tests.test_invariants -v
 
   protected-paths:
     name: Enforcement, конфиги системы меняет только Оператор
@@ -195,6 +215,12 @@ jobs:
     steps:
       - uses: actions/checkout@v4
         with: { fetch-depth: 0 }
+      - name: версия Python из манифеста стека (01M1RDCCKBQMJ5G2K9ANJP059H)
+        id: stack-python
+        run: echo "version=$(python3 scripts/stack_ci.py)" >> "$GITHUB_OUTPUT"
+      - uses: actions/setup-python@v5
+        with:
+          python-version: ${{ steps.stack-python.outputs.version }}
       - name: генератор отрабатывает без ошибок (AC-7, AC-8)
         run: python3 scripts/codebase_map.py
       - name: закоммиченная карта не стухла (AC-9; ред. Оператора 26.08 — сверка содержимым)
```
