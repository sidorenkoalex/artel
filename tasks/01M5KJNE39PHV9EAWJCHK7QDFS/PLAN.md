---
task: 01M5KJNE39PHV9EAWJCHK7QDFS
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Полный набор tests/: git в процессах тестов — напрямую, без системной обёртки xcrun

## Подход
Новый модуль `tests/direct_git.py` с `prefer_direct_git(environ, platform=sys.platform, developer_dir=None)`:
порядок проверок — платформа `darwin`; `PATH` в `environ`; первый git
`shutil.which("git", path=environ["PATH"])` после `normpath` равен
`/usr/bin/git`; есть элемент `/usr/bin` (сравнение после `normpath`, пустые
элементы пропускаются); каталог разработчика — `developer_dir()` /
`environ["DEVELOPER_DIR"]` / `xcode-select -p` (`timeout=5`, код выхода
проверяется, `OSError`/`SubprocessError` глотаются, пустой вывод — отказ);
`<каталог>/usr/bin/git` — файл с `X_OK`; каталог ещё не стоит раньше первого
`/usr/bin`. Тогда `<каталог>/usr/bin` вставляется в список элементов PATH
перед первым `/usr/bin`, прочие элементы (и пустые) не трогаются.
`shutil.which`/`subprocess.run` вызываются через модули — их подменяет
долгоживущий файл задачи.

`tests/__init__.py` (на базе пуст): `import os`, `from .direct_git import
prefer_direct_git`, `DIRECT_GIT_DIR = prefer_direct_git(os.environ)` —
вызов на самом `os.environ`, позиционно, как ждёт AC-6.

Бюджет SPEC не пересматривается.

## Шаги
1. `tests/direct_git.py` + `tests/__init__.py`; регенерация
   `docs/codebase-map.md` (`python3 scripts/codebase_map.py`).
2. Прогон долгоживущего файла задачи
   `tests/test_01m5kjne39phv9eawjchk7qdfs_direct_git.py`: 11 passed, 43
   subtests; AC-7 на этой машине не пропущен (`DIRECT_GIT_DIR =
   /Library/Developer/CommandLineTools/usr/bin`). Временные мутации
   «проверка платформы снята», «`exists` без `X_OK`», «сравнение с `/usr/bin`
   без `normpath`» — 10 failed; код возвращён, снова зелёный.
3. Замеры (ниже), планка `plank-run`.

## Замеры (AC-9)
Машина пульта (Darwin 25.2.0), одна сессия 23.10.2026 08:37–08:50, без
xdist, `python3 -m pytest <цель> -p no:cacheprovider -q`. «База» —
временно пустой `tests/__init__.py` (как на main), «ветка» — с вызовом;
правка `tests/__init__.py` переключалась перед каждым прогоном, итог —
состояние ветки. Загрузка — `uptime` перед каждым прогоном
(load average, 1/5/15 мин).

Цели: (A) `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac10EmptyPriorSetTest`;
(B) `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py` (17 тестов);
(C) `tests/test_01m446wv7s94ftzgjcgmpj667f_clone_refs.py` (5 тестов,
наследники `TmpRootTest` через `RealGitSandbox`).

| № | Состояние | (A) время | uptime перед (A) | (B) время | uptime перед (B) | (C) время | uptime перед (C) |
|---|---|---|---|---|---|---|---|
| 1 | база | 9,98 с | 18.57 14.57 8.65 | 186,77 с | 18.64 14.72 8.77 | 12,17 с | 22.72 18.44 11.53 |
| 2 | ветка | 5,16 с | 22.52 18.60 11.70 | 101,74 с | 22.48 18.66 11.76 | 6,16 с | 16.71 17.94 12.29 |
| 3 | база | 6,32 с | 15.90 17.72 12.28 | 91,60 с | 15.29 17.53 12.28 | 6,59 с | 9.81 15.13 11.88 |
| 4 | ветка | 2,65 с | 7.60 14.10 11.62 | 45,26 с | 7.32 13.93 11.57 | 4,43 с | 6.62 12.83 11.29 |
| 5 | база | 5,03 с | 5.66 12.21 11.10 | 124,85 с | 5.60 12.09 11.06 | 16,41 с | 16.49 13.23 11.59 |
| 6 | ветка | 5,79 с | 17.61 13.70 11.80 | 90,36 с | 18.04 13.85 11.86 | 5,48 с | 20.75 15.79 12.80 |

Загрузка машины в окне замеров плавала от 5 до 23 (параллельные задачи
пульта), поэтому пара 5–6 добавлена сверх «база — ветка — база — ветка».
Сравнение при близкой загрузке: (A) 9,98 с (база, 18.6) против 5,16 с /
5,79 с (ветка, 22.5 / 17.6); (B) 186,8 с (база, 18.6) против 101,7 с /
90,4 с (ветка, 22.5 / 18.0); (C) 12,2 с (база, 22.7) против 5,5 с (ветка,
20.8). Пара 3–4 сдвинута падением загрузки (15 → 7), её разница — верхняя
оценка. Направление совпадает с попарными замерами ТЗ (B: 78,1 → 40,9 с);
величина при загрузке ~18–22 — ~1,7–2× на (A) и (B).

**Число запусков git на тест AC-10.** Хук аудита Python
(`sys.addaudithook`, событие `subprocess.Popen`, счёт по `args[0]` либо
первому элементу argv) в процессе pytest (`pytest.main` в том же
интерпретаторе, `sys.argv` подставлен под сторож `conftest.py`), цель (A):
- база: всего 267 запусков `subprocess.Popen`, из них **261 — `git`**
  (литерал, разрешается по PATH в `/usr/bin/git` → обёртка xcrun → второй
  процесс), 5 — `python3` venv, 1 — `claude`;
- ветка: всего 268, из них **261 — `git`** (тот же литерал, теперь
  разрешается в `/Library/Developer/CommandLineTools/usr/bin/git` напрямую),
  5 — `python3`, 1 — `claude`, 1 — `xcode-select` (однократный вызов
  `prefer_direct_git` при `import tests`).

Число запусков git не меняется — меняется цена каждого.

Длительность полного набора — по записи «прогон: время» автогейта приёмки
этой задачи (в шаге разработчика полный набор не запускается); сравнение с
рядом 22–23.10 — сведения для Оператора.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (`tests/direct_git.py`), 2 (AC-1…AC-5) |
| 2 | 1 (`tests/__init__.py`), 2 (AC-6, AC-7(а)) |
| 3 | 1: в `tests/` дифф ветки — только `tests/__init__.py`, `tests/direct_git.py`; файл тестов задачи уже в ветке (test_author) |
| 4 | файл тестов задачи (test_author), прогон — шаг 2 |
| 5 | 3 (раздел «Замеры») |

## Влияние на систему
- Меняется PATH только процессов, импортирующих пакет `tests` (pytest
  набора и его воркеры); PATH боевого пульта, `orchestrator/`, `conftest.py`,
  `pyproject.toml`, `targets.yaml` не тронуты. Тесты, сравнивающие PATH
  (`own_run_path`, `pult_pytest_unchanged`), строят ожидания из текущего
  PATH — см. матрицу неослабления SPEC.
- На Linux (CI) функция ничего не делает (проверка платформы), поведение CI
  неизменно.
- Ни один существующий тест, гейт, лимит не ослаблен; существующие тестовые
  методы не менялись.
- Откат — revert merge-коммита (удаляет модуль и три строки
  `tests/__init__.py`).

## Риски
- PATH шага роли в тестах получает каталог разработчика вместо `/usr/bin`
  (матрица SPEC, строка 3) — расхождение в сторону строгости.
- Если `xcode-select -p` указывает на Xcode.app, где `usr/bin/git` нет, —
  вставки нет, поведение как на базе.

## Ответ Оператора (ANSWER-1) — сверка
Оба пункта касаются только долгоживущего файла
`tests/test_01m5kjne39phv9eawjchk7qdfs_direct_git.py` (его написал
test_author, он залочен перечнем сумм); код `tests/direct_git.py` и
`tests/__init__.py` ни одного из них не касается. Повторный прогон
`python3 -m pytest tests/test_01m5kjne39phv9eawjchk7qdfs_direct_git.py -rs`
23.10: 11 passed, 43 subtests, пропусков нет.

- П. 2 (подмена `which` зависит от `path`) — **выполнен**: `FakeWhich`
  (файл тестов, стр. 74–90) ищет git только по каталогам переданного
  `path=`, без `path=` возвращает `None` — поиск git без `path=` даёт
  красный AC-5 (мутация проверена test_author, записка test_author).
- П. 1, песочница — **выполнено**: `Ac8RolePathTest(TmpRootTest)` (стр. 542);
  `TmpRootTest.setUp` вызывает `isolate_keychain_and_role`
  (`tests/sandbox.py:1619`) и подменяет `stack.check_stack` на
  `_stub_check_stack` (`:1643`).
- П. 1, условие пропуска — **не выполнено в залоченном файле**: стр. 565–566
  пропускают тест на любом `OSError` из `runner.role_env()` /
  `declared_tool_path`, а не только на «объявленный инструмент не найден в
  PATH» (`orchestrator/runner.py:924–925`). Единственный другой `OSError`
  этой цепочки — «venv не готов для роли» (`runner.py:1017`) — в
  `TmpRootTest` недостижим (проверка `check_stack` заглушена), так что
  на практике пропуск сейчас возможен только по отказу «не найден», но
  формально условие шире. Вынесено эскалацией; решение — ANSWER-2 ниже.

## Ответ Оператора (ANSWER-2) — исполнение
П. 1 — вариант **(б)**: залоченный
`tests/test_01m5kjne39phv9eawjchk7qdfs_direct_git.py::Ac8RolePathTest::test_ac8_role_path_finds_git_and_declared_tools`
принят как есть — в `TmpRootTest` с заглушкой `stack.check_stack` пропуск на
любом `OSError` на деле совпадает с пропуском по отказу «объявленный
инструмент не найден в PATH». Код задачи (`tests/direct_git.py`,
`tests/__init__.py`, коммит 73fc60c4) не меняется, существующие тесты не
правятся; эскалация снята, PLAN сдаётся `ready`. Сужение условия пропуска —
строка бэклога Оператора, вне этой задачи.

## Возврат из verifying (CI 39908727505) — исполнение
Причина: зеркало пакета `tests` в
`tests/test_fsm_advance_tests_writing_test_groups.py::CollectFromTestsDirTest::test_clean_long_lived_file_collects_from_tests_dir`
(символьные ссылки только на `__init__.py` и `sandbox.py`) роняет импорт
`tests.direct_git` из `tests/__init__.py`.

Ограда по решению Оператора внесена в `tests/__init__.py` рабочей копии:

```python
import os

try:
    from .direct_git import prefer_direct_git
except ModuleNotFoundError as exc:
    # (комментарий: зеркала пакета tests без этого модуля)
    if exc.name != "tests.direct_git":
        raise
    DIRECT_GIT_DIR = None
else:
    DIRECT_GIT_DIR = prefer_direct_git(os.environ)
```

Прогон 23.10.2026, по одному файлу,
`python3 -m pytest <файл> -p no:xdist -p no:cacheprovider -q`, с оградой:

| Файл | Итог |
|---|---|
| `tests/test_fsm_advance_tests_writing_test_groups.py` | 9 passed, 2 subtests |
| `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_guard_spec_paths.py` | 2 passed |
| `tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py` | 5 passed |
| `tests/test_01m59kmpg2zmk10v556vzvqd65_plank_rule.py` | 15 passed, 94 subtests |
| `tests/test_canary_drive.py` | 20 passed, 4 subtests |
| `tests/test_checkpoint_stray_acceptance_files.py` | 5 passed, 19 subtests |
| `tests/test_dry_run.py` | 9 passed |
| `tests/test_guard_extraneous_acceptance_files.py` | 7 passed, 7 subtests |
| `tests/test_long_lived_step_end_to_end.py` | 4 passed, 4 subtests |
| `tests/test_01m5kjne39phv9eawjchk7qdfs_direct_git.py` (долгоживущий, `-rs`) | 11 passed, 43 subtests, пропусков нет |

Планка `plank-run 01M5KJNE39PHV9EAWJCHK7QDFS`: **1 failed, 1 passed** —
красный `Ac6InitOnlyWiringTest::test_ac6_init_has_no_other_change` (см.
ниже; закрыто ANSWER-3).

## Ответ Оператора (ANSWER-3) — исполнение
Вариант **(а)**: планка AC-6 поправлена Оператором командой `amend-tests`
(7a1b6853) — в `foreign_statements` допущен один узел `Try` канонической
формы ограды; ограда этой формы — допустимая часть правки
`tests/__init__.py` по толкованию AC-6. Код не менялся: `tests/__init__.py`
рабочей копии (стр. 1–12) — та же ограда, что выше.
`plank-run 01M5KJNE39PHV9EAWJCHK7QDFS` 23.10.2026: **2 passed** (код выхода
pytest 0). Эскалация снята, PLAN сдаётся `ready`.

## Вопрос к Оператору по возврату из verifying (закрыт ANSWER-3)

**Вопросы**

1. Ограда противоречит AC-6 в форме залоченной планки. AC-6 SPEC: «другой
   правки этого файла нет». Планка
   `tasks/01M5KJNE39PHV9EAWJCHK7QDFS/acceptance_tests/test_oneoff_init_and_plan.py::Ac6InitOnlyWiringTest::test_ac6_init_has_no_other_change`
   (`foreign_statements`, стр. 40–75) допускает на верхнем уровне
   `tests/__init__.py` только `import os`/импорт `prefer_direct_git`,
   одно присваивание `DIRECT_GIT_DIR = prefer_direct_git(os.environ)` и
   `del`; узел `Try` она считает посторонним оператором — тест красный с
   текстом «другая правка tests/__init__.py: try: from .direct_git import
   prefer_direct_git except ModuleNotFoundError as exc: …» (стр. 99).
   Варианты:
   - (а) `amend-tests` планки: в `foreign_statements` допустить узел `Try`
     ровно вида «тело — импорт `prefer_direct_git`; один обработчик
     `ModuleNotFoundError`, проверяющий `exc.name != "tests.direct_git"` →
     `raise`, затем `DIRECT_GIT_DIR = None`; `else` — то самое
     присваивание», и считать присваивания в нём; плюс уточнение AC-6
     SPEC (ограда — допустимая часть правки). Код в рабочей копии уже
     такой, после правки планки шаг сдаётся `ready` без изменений кода.
   - (б) ограду не ставить (вернуть три строки 73fc60c4), а CI чинить
     иначе — правкой зеркала в `tests/test_fsm_advance_tests_writing_test_groups.py`
     (стр. 212–214, добавить ссылку на `direct_git.py`) с мандатом
     Оператора: это правка существующего тестового файла, требование 3
     SPEC её запрещает.
   - (в) ограда выражением без `try` (например, `importlib.util.find_spec`
     внутри вызова) — проходит AST-фильтр планки формально, но обходит
     смысл AC-6 и решения Оператора; не рекомендую.
   **Дефолт при молчании:** (а).

**Контекст.** Ограда внесена в `tests/__init__.py` рабочей копии (не
откатывал); девять файлов с зеркалом и долгоживущий файл задачи
зелёные (таблица выше); AC-7 не затронут — на машине с обёрткой модуль
есть, вставка выполняется как прежде; долгоживущий AC-6 (подпроцесс с
поддельным `tests.direct_git`) зелёный.

**Блокирует.** Сдачу `ready`: с оградой красна планка AC-6, без неё
красен CI ветки.

## Предложения системе
- Решение по причине возврата стоит сверять с залоченной планкой задачи
  до выдачи: здесь мандат на форму кода (try/except) разошёлся с
  AST-проверкой планки той же задачи.
- ANSWER, адресованный разработчику, но требующий правки залоченного
  долгоживущего файла test_author, разработчик исполнить не может —
  такие пункты стоит направлять сразу в `amend-tests` либо в шаг
  test_author.
- Песочница Bash роли отклоняет `for`-цикл с `$t` («simple_expansion») и
  heredoc с `{'` — попеременные замеры пришлось расписывать одинаковыми
  командами вручную; команды пульта для попарного замера «база — ветка»
  нет (замеры требуют SPEC уже не первый раз).

