---
task: 01M1R66X5SMD3ZEDCVAJ0DR7K2
type: plan
author_role: developer
status: ready        # draft | ready | approved
schema_version: 4    # версия формата артефакта, см. scripts/guard.py
---

# PLAN: guard на артефактных ветках — черновики не красят CI, сданные артефакты проверяются строго

## Подход
Механизм включения режима — CLI-флаг `--artifact-branch` (не переменная
окружения): планка приёмки (`tasks/01M1R66X5SMD3ZEDCVAJ0DR7K2/
acceptance_tests/_sandbox.py`, докстринг модуля) фиксирует именно этот
внешний контракт первой, разработчик обязан либо принять его, либо
вынести несогласие в этот PLAN как предмет ревью (skills/test-authoring.md,
«Лок»). Флаг читается яснее в `run:`-шаге ci.yml и не оставляет скрытого
состояния окружения между шагами джоба — несогласия нет, принимаю как есть.

Внутри `scripts/guard.py`:

1. `check_content(label, text, artifact_branch_mode=False)` — новый
   необязательный параметр, дефолт `False`. Старое тело функции
   переименовано в приватную `_content_errors(label, text)` без единой
   правки — единственный источник правды о полном наборе правил
   содержания что для пути «без режима», что для пути «сдан» внутри
   режима (AC-1, AC-3). `check_content` с `artifact_branch_mode=False`
   вызывает `_content_errors` напрямую — байт-в-байт то же самое
   поведение, что было. Все существующие вызыватели (`check()`,
   `orchestrator/fsm.py::guard_refuses` и все переходы FSM через него,
   существующие тесты) не передают новый параметр — поведение не
   меняется ни на бит (AC-1).
2. `is_draft_lenient(meta)` — предикат требования 2/3: `type` — один из
   `DRAFT_LENIENT_TYPES = {spec, plan, review, test_report}` И
   `status == "draft"` буквально. Для `tz`/`questions`/`answer` — всегда
   `False` независимо от status (требование 3, AC-4).
3. `basic_frontmatter_errors(label, meta)` — базовые условия требования 2:
   `task`/`type`/`schema_version` на месте (в отличие от
   `_content_errors`, где отсутствие `schema_version` — версия 1 по
   умолчанию, НЕ ошибка: здесь оно обязано присутствовать явно — иначе
   не по чему судить, какие правила «сдан»-проверки к этому черновику
   позже применятся) + `schema_errors(label, meta)` (та же функция, что
   и полная проверка — граница `SUPPORTED_SCHEMA_VERSION` не дублируется
   новым кодом).
4. `check_content(..., artifact_branch_mode=True)`: если `meta`
   парсится и `is_draft_lenient(meta)` — возвращает только
   `basic_frontmatter_errors`; иначе — тот же `_content_errors`, что и
   без режима (требование 2 вторая часть, требование 3).
5. CLI: `main()` вынимает `--artifact-branch` из `sys.argv` (совместимо
   с `--all` в любом порядке), остаток разбирается как раньше.
   С флагом — новая функция `_artifact_branch_report(files)` на каждый
   файл считает `(errors, warnings)`: `full = _content_errors(...)`
   всегда (для сводки K — «и по сданным, и по черновикам», требование
   5); если файл — льготный черновик, `errors = basic_frontmatter_errors`
   и `warnings = full минус errors` (по строковому совпадению — сообщения
   `schema_errors` идентичны в обоих списках, поэтому не задваиваются;
   единственное новое сообщение `basic_frontmatter_errors` —
   «schema_version отсутствует» — в `full` его нет, вычитать нечего);
   иначе `errors = full`, `warnings = []`. `N`/`M` считаются по
   `status` файла (независимо от типа — требование 5 не сужает счётчик
   до четырёх типов). Первая строка вывода — сводка «сдано N /
   черновиков M / нарушений K», `K = len(errors) + len(warnings)`.
   Exit-код — 1, если `errors` непусты (по любому файлу набора), иначе 0
   (AC-6). Без флага — старая ветка `main()` не тронута ни строкой.

`.github/workflows/ci.yml` — защищённый путь, правится Оператором:
диф приложен ниже (раздел «Диф для Оператора»), сам файл в кодовой
ветке этой задачи НЕ изменён (`git status` подтверждает).

Решил НЕ добавлять новую запись в `docs/invariants.md` — SPEC («Не
входит») явно оставляет это на усмотрение разработчика, не критерий
приёмки. Существующая запись строки 82 (класс «новые правила guard
действуют на живые задачи») — про другой аспект (историю не
переписываем), не про сам факт различения draft/сдан; заводить под
единственную задачу отдельный пункт таблицы инвариантов, не подкреплённый
кодовым тестом сверх уже написанных `tests/test_guard_artifact_branch_
mode.py`, было бы структурой ради структуры. Оставляю решение видимым
здесь, не молчаливым пропуском.

## Шаги

1. `scripts/guard.py`: переименовать `check_content` в `_content_errors`
   (тело не менять), добавить `DRAFT_LENIENT_TYPES`, `is_draft_lenient`,
   `basic_frontmatter_errors`, новую `check_content(label, text,
   artifact_branch_mode=False)`-обёртку, `ARTIFACT_BRANCH_FLAG`,
   `_artifact_branch_report`, ветку `main()` под флаг + сводку. Обновить
   докстринг модуля (раздел «Использование»).
2. `tests/test_guard_artifact_branch_mode.py` (новый файл) — юнит-тесты
   `is_draft_lenient`/`basic_frontmatter_errors`/`check_content` на
   граничных случаях, которые приёмочная планка не обязана перечислять
   поимённо (тип вне набора, отсутствие `type`/`status` целиком,
   `schema_version: 0`, параметр по умолчанию).
3. Регенерировать `docs/codebase-map.md`
   (`python3 scripts/codebase_map.py`) — новые публичные функции
   `basic_frontmatter_errors`/`is_draft_lenient` в `scripts/guard.py`
   (conventions-core.md: «правишь `*.py` … — регенерируй карту тем же
   коммитом»).
4. `.github/workflows/ci.yml` — НЕ правится в этой ветке (защищённый
   путь). Диф-приложение для Оператора — ниже, `git apply --check`
   пройден на чистом дереве этой задачи.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 6 | 4 (диф-приложение) |

## Диф для Оператора (требование 6, `.github/workflows/ci.yml`)

Проверено на чистом дереве этой ветки: `git apply --check` проходит без
ошибок непосредственно перед сдачей PLAN.

```diff
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index cf24990a..ebfb4f79 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -16,8 +16,19 @@ jobs:
       - uses: actions/checkout@v4
       - name: guard.py по всем артефактам задач
         run: |
+          # На артефактной ветке пульта задачи (`artifact/<id>`) каждый
+          # автокоммит шага роли несёт промежуточные, по определению
+          # неполные артефакты (01M1R66X5SMD3ZEDCVAJ0DR7K2, требование 6):
+          # `--artifact-branch` понижает нарушения содержания черновика
+          # до предупреждения, оставляя нарушения frontmatter и полную
+          # проверку «сданных» артефактов ошибкой. На `main`/`task/**` —
+          # вызов без флага, поведение прежнее.
+          GUARD_ARGS="--all"
+          if [[ "${GITHUB_REF#refs/heads/}" == artifact/* ]]; then
+            GUARD_ARGS="--all --artifact-branch"
+          fi
           if ls tasks/*/*.md >/dev/null 2>&1; then
-            python3 scripts/guard.py --all
+            python3 scripts/guard.py $GUARD_ARGS
           else
             echo "артефактов пока нет — ок"
           fi
```

`pull_request`-триггер (job идёт и на PR) не подпадает под `if [[
"${GITHUB_REF#refs/heads/}" == artifact/* ]]` — `GITHUB_REF` для PR это
`refs/pull/<n>/merge`, флаг не включается, поведение как сегодня.

## Влияние на систему

- **Единственная точка правды сохранена.** `_content_errors` (бывший
  `check_content`) не продублирован и не расщеплён — и путь «без
  режима», и путь «режим + сдан» внутри режима зовут его напрямую;
  различение живёт только в тонкой обёртке и в CLI-классификации
  (`_artifact_branch_report`). Разойдись эти два пути — расхождение
  правил содержания между «просто guard.check» и «guard --all
  --artifact-branch на сданном» стало бы новым классом дефекта (тот же
  урок T011: чинить один путь и оставлять сестринский).
- **Инварианты.** Инвариант 17 (`docs/invariants.md`, PLAN без секции
  «Влияние на систему» не проходит guard) и инвариант из ANSWER-3
  («новые правила guard действуют на живые задачи») не ослаблены и не
  затронуты: режим — новая, по умолчанию выключенная ветка, ничего
  существующего не отключает. `tests/test_invariants.py::
  GuardKeepsTheIntegritySectionTest` и остальной `tests/test_guard*.py`
  прогнаны — зелёные без единой правки их кода (см. «Проверено
  исполнением» на гейте ревью).
- **Гейты FSM не затронуты.** Ни один переход (`orchestrator/fsm.py`,
  `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`) не
  передаёт `artifact_branch_mode=True` — режим используется
  ИСКЛЮЧИТЕЛЬНО из CLI (`scripts/guard.py --all --artifact-branch`),
  вызываемого CI-джобом на `artifact/**`. Гейт `spec_writing ->
  spec_gate` и все прочие продолжают получать полную, строгую проверку
  через `guard_refuses`, как до этой задачи (AC-1, `tasks/
  01M1R66X5SMD3ZEDCVAJ0DR7K2/acceptance_tests/
  test_ac9_required_scenarios.py::DraftSpecStillBlocksAdvanceTest`,
  зелёный с рождения).
- **Откат.** Правка изолирована в `scripts/guard.py` + новый тестовый
  файл; откат — `git revert` этого MR и отдельного MR Оператора с
  дифом `ci.yml`. Существующие вызовы `check`/`check_content` без
  нового параметра ничего не роняют при откате — контракт по умолчанию
  тот же, что был всегда.
- **Защищённый путь.** `.github/workflows/ci.yml` не правится этой
  веткой — диф выше приложен Оператору отдельным MR (skills/
  conventions-core.md: «эти пути меняет только Оператор»).

## Риски

- Сообщение `basic_frontmatter_errors` о недостающем `schema_version`
  — НОВОЕ правило, которого не было ни в одном из существующих путей
  (`_content_errors` трактует отсутствие как версию 1, не ошибку).
  Область действия узкая (только `artifact_branch_mode=True` +
  льготный черновик), но при чтении кода расхождение может показаться
  непоследовательным — оставляю явный комментарий у
  `basic_frontmatter_errors` и здесь, в PLAN, чтобы ревьювер видел
  обоснование (SPEC, требование 2, буквально «schema_version на
  месте» как часть базовых условий).
- Вычитание `warnings = [e for e in full if e not in errors]` по
  строковому совпадению теоретически может задвоить редкое сообщение,
  если у черновика ОДНОВРЕМЕННО отсутствуют `task`/`type` (входят и в
  комбинированное сообщение `_content_errors` про `REQUIRED_META`, и в
  отдельное сообщение `basic_frontmatter_errors`) — тогда `warnings`
  унесёт неудалённый дубль формулировки. Не влияет на корректность
  exit-кода (`task`/`type` всё равно попадают в `errors` через
  `basic_frontmatter_errors`, требование 2 «остаются ошибками»
  выполнено) — только на минорную избыточность текста предупреждения
  в этом маловероятном комбинированном случае (оба поля отсутствуют
  сразу, что практически не встречается: `task`/`type` заполняются
  инструментом заведения задачи с рождения артефакта).

## Предложения системе
