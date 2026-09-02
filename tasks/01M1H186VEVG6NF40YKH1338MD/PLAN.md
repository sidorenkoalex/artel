---
task: 01M1H186VEVG6NF40YKH1338MD
type: plan
author_role: developer
status: ready
schema_version: 3
---

# PLAN: Проверка формата идентификатора на выходе tests_writing, до лока

## Подход

Инцидент 02.09.2026: CI-job `id-format-greplint` ловил зашитый формат
id только на PR — когда `acceptance_tests/` уже зафиксирован локом
(ADR-0003, инвариант 27) и test_author не вправе его править. Нужна та
же проверка РАНЬШЕ, на выходе `tests_writing -> in_dev`, тем же местом,
где уже сидят трассируемость AC (T023) и маркер красноты (T064) —
`orchestrator/fsm.py::_tests_writing_ac_state`.

Решения:

1. **Общий источник образцов (требование 2, AC-3)**: новый файл
   `scripts/id_format_patterns.txt` — по одной ERE/Python-`re`-
   совместимой альтернативе на строку, извлечённые дословно из старого
   инлайн-`PATTERN` CI-job'а (набор образцов не меняется — «Не входит»
   SPEC). Оба потребителя читают ОДИН этот файл:
   - bash-шаг CI: `grep -Ef scripts/id_format_patterns.txt` вместо
     `grep -E "$PATTERN"` — job остаётся, меняется только источник
     (требование 2);
   - Python: `guard.id_format_patterns()` компилирует те же строки
     через `re.compile`.
   Файл без пустых строк — регресс-риск: пустая строка стала бы для
   `grep -Ef` пустым regex'ом, совпадающим с ЛЮБОЙ строкой (проверено
   тестом `IdFormatPatternsTest.test_patterns_file_has_no_blank_lines`,
   `tests/test_id_format_guard.py`).

2. **Ядро проверки (`scripts/guard.py`)** — тем же приёмом, что уже
   существующая пара
   `redness_marker_errors_from_files`/`scan_redness_markers` (T064):
   - `id_format_sample_errors(files)` — ядро без чтения файлов: по
     каждой строке каждого (label, текст) файла ищет совпадение с
     любым образцом, копит `"{label}:{lineno}: ... — {ID_FORMAT_HINT}"`
     (подсказка — дословно требование 1 SPEC);
   - `scan_id_format_samples(tdir)` — рабочая копия, ВСЕ `*.py` под
     `acceptance_tests/` (шире, чем `scan_redness_markers`, который
     смотрит только `test_*.py`: требование 1 SPEC говорит о
     «содержимом acceptance_tests/» целиком, не о конкретном шаблоне
     имени — образец формата может утечь и во вспомогательный файл
     вроде `_sandbox.py`).

3. **Подключение в `orchestrator/fsm.py::_tests_writing_ac_state`** —
   `errors` (список, который уже несёт ошибки трассируемости AC и
   маркера красноты) получает третье слагаемое от новой проверки, в
   ОБОИХ существующих ветках функции (диск и чтение с ВЕТКИ задачи при
   чужом чекауте, SPEC T031). Поскольку `tests_writing()`
   (`orchestrator/fsm_advance.py`) уже трактует непустой `errors` как
   именованный отказ БЕЗ эскалации (тот же путь, что трассируемость
   AC/маркер красноты — прецедент T064), требования 1 и 3 (отказ не
   эскалирует, чинится тем же `advance`) закрываются без нового кода в
   `fsm_advance.py` — только добавлением источника ошибок.

## Шаги

1. `scripts/id_format_patterns.txt` (общий источник образцов) +
   `scripts/guard.py` (`ID_FORMAT_PATTERNS_PATH`, `ID_FORMAT_HINT`,
   `id_format_patterns`, `id_format_sample_errors`,
   `scan_id_format_samples`) + подключение обеих проверок в
   `orchestrator/fsm.py::_tests_writing_ac_state` (диск и ветка) +
   юнит-тесты `tests/test_id_format_guard.py`.
2. Дифф защищённого пути `.github/workflows/ci.yml` для Оператора (не
   в ветке задачи — см. «Дифф для Оператора» ниже): `id-format-
   greplint` читает образцы из `scripts/id_format_patterns.txt`
   (`grep -Ef`) вместо инлайн-`PATTERN`.
3. Регенерация `docs/codebase-map.md` (`orchestrator/fsm.py` и
   `scripts/guard.py` правились Edit'ом — conventions-core требует
   регенерации тем же коммитом).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (проверка новых строк acceptance_tests/, отказ с файлом/строкой/подсказкой, до лока) | 1 |
| 2 (общий источник образцов для CI и перехода) | 1, 2 |
| 3 (отказ не эскалирует) | 1 (переиспользует существующий путь `tests_writing()`) |
| 4 (принцип целостности — ничего не ослаблено) | 1, 2 |

## Влияние на систему

- **Затронуто за пределами прямой правки**: `.github/workflows/ci.yml`
  — защищённый путь (CLAUDE.md/conventions-core: правит только
  Оператор). SPEC «Зоны» называет этот файл в объёме задачи, но право
  редактировать `.github/` этой роли не принадлежит ни при каких
  обстоятельствах — конфликт разрешён штатным механизмом
  conventions-core («Готовишь unified-диф по защищённому пути...»):
  диф подготовлен, `git apply --check` пройден на чистом `main`,
  сам файл в ветку задачи не входит — применяет Оператор отдельным MR.
  До применения диффа CI-job `id-format-greplint` продолжает работать
  по старому инлайн-`PATTERN` (байт-в-байт тот же набор образцов, что
  в `scripts/id_format_patterns.txt`) — расхождения источников в этом
  промежутке нет, только временное дублирование текста образцов.
- **Инварианты рядом**: ADR-0003 инвариант 27 (лок `acceptance_tests/`)
  — не тронут, проверка нарочно стоит ДО записи `tests_locked_sha`.
  T023 (трассируемость AC) и T064 (маркер красноты) — не изменены,
  только третье слагаемое добавлено в общий список `errors` тем же
  структурным приёмом; оба покрыты `tests/test_acceptance_tests_flow.py`
  (гонял полностью, зелёный).
  `docs/invariants.md` (эскалация только по решению кода FSM, не по
  сторонним отказам) — не нарушен: отказ этой проверки НЕ переводит в
  `escalated` (требование 3, AC-4; см. акцептанс `test_ac4_*`).
- **Как откатить**: удалить три вызова `guard.scan_id_format_samples`/
  `guard.id_format_sample_errors` из `_tests_writing_ac_state`,
  файл `scripts/id_format_patterns.txt` и функции в `guard.py` —
  локальная, полностью обратимая правка (не меняет схему БД, не пишет
  новых полей в артефакты).
- **Что НЕ ослаблено**: `scripts/guard.py` — существующие функции
  (`schema_errors`, `check_content`, `traceability_errors_from_content`,
  `redness_marker_errors_from_files`) не тронуты; регресс-прогон
  `tasks/01M1H186VEVG6NF40YKH1338MD/acceptance_tests/
  test_ac5_existing_checks_not_weakened.py` — зелёный. Полный
  `tests/` (1253 теста) — зелёный после правки.

## Риски

- Точная семантика отдельных альтернатив ERE-паттерна (например
  количество обратных слэшей в последней альтернативе) не
  переосмыслена — набор образцов перенесён байт-в-байт («Не входит»
  SPEC), проверено эквивалентным поведением на фикстуре инцидента
  (`r"T\d{3}"`) и в guard-юнит-тестах, не построчным аудитом каждой
  альтернативы ERE.
- До применения Оператором диффа `.github/workflows/ci.yml` набор
  образцов физически дублирован (файл + инлайн-`PATTERN`) — снимается
  самим применением диффа; до этого момента AC-3 (общий источник)
  структурно готов, но не действует в CI до мержа диффа Оператором.

## Предложения системе

- Класс «SPEC называет защищённый путь (`.github/`, `templates/`,
  ...) прямо в зоне разработчика» — уже описанный в
  conventions-core механизм (диф-приложение к PLAN.md) сработал без
  трения, но сам SPEC (аналитик) в «Зонах» не пометил файл как
  требующий такого механизма — стоило бы analyst-скилу явно сверяться
  с `config.PROTECTED_PATHS`/`CLAUDE.md` при перечислении зон и
  помечать такие пути пометкой «через дифф Оператору» прямо в SPEC.

---

# Дифф для Оператора

Унифицированный диф защищённого пути `.github/workflows/ci.yml` (SPEC
01M1H186VEVG6NF40YKH1338MD, требование 2/AC-3). Исполнитель его не
коммитит в ветку задачи; применяет и коммитит Оператор своим MR
отдельно (тот же приём, что T046/T094). Проверено `git apply --check`
на чистом дереве `main` перед сдачей — применяется без конфликтов.

## .github/workflows/ci.yml

```diff
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index f57f9c3..a5bde08 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -40,9 +40,13 @@ jobs:
           # protected-paths ниже) — существующий легаси-парсер
           # (orchestrator/store.py, TASK_ID, требование 6) не тронут этим
           # PR и линт его не видит.
-          PATTERN='T%0[0-9]|T\{[a-zA-Z_]*:0[0-9]+d\}|\\d\{3\}|TASK_ID *= *re\.compile|r["'"'"']\^?T\\\\?d'
+          #
+          # Образцы — общий источник с проверкой перехода tests_writing ->
+          # in_dev (SPEC 01M1H186VEVG6NF40YKH1338MD, требование 2/AC-3):
+          # scripts/id_format_patterns.txt, не инлайн-паттерн здесь —
+          # правка файла меняет обе проверки без правки этого job'а.
           ADDED=$(git diff "$BASE_SHA"...HEAD -- . ':!orchestrator/idgen.py' \
-            | grep -E '^\+' | grep -Ev '^\+\+\+' | grep -E "$PATTERN" || true)
+            | grep -E '^\+' | grep -Ev '^\+\+\+' | grep -Ef scripts/id_format_patterns.txt || true)
           if [ -n "$ADDED" ]; then
             echo "::error::диф добавляет парсинг формата id задачи вне orchestrator/idgen.py (SPEC T094, требование 4):"
             echo "$ADDED"
```
