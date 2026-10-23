---
task: 01M5KJNE39PHV9EAWJCHK7QDFS
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Полный набор tests/: git в процессах тестов — напрямую, без системной обёртки xcrun

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–5 сопоставлены шагам 1–3; требование 4 — файл test_author.
- Шаги проверяемые (модуль + проводка; прогон с мутациями; замеры).
- Подход не конфликтует с конвенциями: правка только `tests/`, `conftest.py`/`orchestrator/` не тронуты; ограда `try/except ModuleNotFoundError` в `tests/__init__.py` — решение Оператора ANSWER-3 (планка AC-6 поправлена `amend-tests` 7a1b6853).
- «Влияние на систему» = diff: `tests/__init__.py`, `tests/direct_git.py`, `docs/codebase-map.md` (+ залоченный файл тестов задачи); путь отката — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `tests/direct_git.py:42-76`: платформа → `PATH` → `shutil.which("git", path=path)` + `normpath` == `/usr/bin/git` → первый `/usr/bin` (normpath, пустые пропущены) → `developer_dir()` / `DEVELOPER_DIR` / `xcode-select -p` (timeout 5, код выхода, `OSError`/`SubprocessError` глотаются, пустой вывод → None) → `isfile` + `X_OK` → уже стоит раньше → вставка через `list.insert`, прочие элементы (и пустые) не трогаются. |
| 2 | OK | `tests/__init__.py:1-12`: `DIRECT_GIT_DIR = prefer_direct_git(os.environ)`; ограда зеркала — допустимая форма по ANSWER-3. |
| 3 | OK | `git diff --stat 9b498178...HEAD` в `tests/` — ровно `tests/__init__.py`, `tests/direct_git.py`, `tests/test_01m5kjne39phv9eawjchk7qdfs_direct_git.py`; вне `tests/` — только регенерированная карта. |
| 4 | OK | Долгоживущий файл задачи: AC-1…AC-8; модульные случаи без пропусков по машине; `FakeWhich` зависит от `path=` (ANSWER-1 п. 2); `Ac8RolePathTest(TmpRootTest)`, пропуск сужен до отказа «объявленный инструмент не найден в PATH» (коммит 13eca1d2 — сужение, не ослабление; ANSWER-1 п. 1 / ANSWER-2). |
| 5 | OK | PLAN «Замеры (AC-9)»: 6 прогонов база/ветка попеременно с `uptime`, цели (A)/(B)/(C) из SPEC, подсчёт git хуком аудита (`sys.addaudithook`, `subprocess.Popen`): 261 git и в базе, и в ветке. |

## Замечания
Блокирующих и major-замечаний нет.

Наблюдение без записи в реестр (не дефект): проверка «каталог уже стоит раньше первого `/usr/bin`» (`tests/direct_git.py:72-74`) при реальном `shutil.which` фактически не достижима — если исполняемый `<dev>/usr/bin/git` стоит раньше `/usr/bin`, функция выходит раньше на проверке «первый git не `/usr/bin/git`». Временная мутация «проверка снята» тестами не ловится (см. ниже), но наблюдаемого расхождения поведения у неё нет; это защитная проверка в формулировке SPEC, не код сверх требований.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest tests/test_01m5kjne39phv9eawjchk7qdfs_direct_git.py -p no:cacheprovider -q -rs` — 11 passed, 43 subtests, пропусков нет (AC-7, AC-8 исполнились на машине с обёрткой).
- `artel.py plank-run 01M5KJNE39PHV9EAWJCHK7QDFS` — 2 passed, код выхода pytest 0.
- Временные мутации `tests/direct_git.py` (скрипт применял замену, гонял `-k "Ac1 or Ac2 or Ac3 or Ac4 or Ac5"`, возвращал исходник; `git status` после — чисто):
  - снята проверка платформы → 4 failed;
  - `isfile+X_OK` → `exists` → 1 failed;
  - сравнение с `/usr/bin` без `normpath` → 13 failed;
  - `shutil.which("git")` без `path=` → 14 failed;
  - код выхода `xcode-select` не проверяется → 1 failed;
  - `DEVELOPER_DIR` раньше `developer_dir()` → 1 failed;
  - снята проверка «уже стоит раньше» → 0 failed (недостижима при реальном `which`, см. «Замечания»).
- `python3 -m pytest tests/test_fsm_advance_tests_writing_test_groups.py tests/test_01m56kcvctw5bv9twth54tw9q9_own_run_path.py tests/test_01m56kcvctw5bv9twth54tw9q9_pult_pytest_unchanged.py -q` — 14 passed, 66 subtests (зеркало пакета с оградой и тесты, строящие ожидания из PATH).
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — расхождение только в `built_at_sha`, карта свежая (регенерированный файл возвращён `git checkout`).
- CI коммита 7acf5d8d — зелёный (по пакету).

## Предложения системе
- Песочница Bash роли отклоняет heredoc с `{'`/`'}` — скрипт временных мутаций пришлось писать файлом в каталог документов; штатная команда пульта «временная мутация» (замена → прогон → возврат) сняла бы это трение у ревьюверов.
