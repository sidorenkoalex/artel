---
task: 01M2B6K3EM7F2J72RC2F520Y2K
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Признак роли в окружении и conftest вместо хука роли

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (ARTEL_ROLE/ARTEL_TASK в role_env, константы config.py) | OK | `orchestrator/config.py` несёт `ARTEL_ROLE_ENV`/`ARTEL_TASK_ENV`; `runner.role_env(role, task_id)` кладёт обе переменные только если значение передано (`orchestrator/runner.py:597-600`). Подтверждено тестами `tests/test_multitarget.py::RoleEnvTest::test_role_env_carries_artel_role_and_task` и `test_role_env_without_task_id_omits_artel_task` — зелёные. |
| 2 (conftest.py — гейт сбора pytest «теми же критериями, что bash_guard._pytest_verdict») | **реализовано не так** | См. R1-F1 — реализация использует более слабое условие (`any` вместо репликации `_pytest_verdict`), из-за чего смешанный вызов вида `pytest tests/test_x.py tests` НЕ блокируется и фактически запускает весь каталог `tests/` — эмпирически воспроизведено (см. «Проверено исполнением»). Базовые формы (голый `pytest`, `pytest tests`, `pytest .`, целевой файл) реализованы верно. |
| 3 (artel.py — отказ init/doctor --restore/canary pool-seal под ARTEL_ROLE) | OK | `_role_restricted_command`/`_refuse_if_role_restricted` в `orchestrator/artel.py:755-784`, вызов до диспетчерской таблицы. `tests/test_artel_role_restricted_commands.py` — 7 тестов, все зелёные, включая регресс «голый doctor не ограничен». |
| 4 (курируемый слой: убрать hooks.PreToolUse и hooks/bash_guard.py, permissions.deny не тронут) | OK | `settings.json` не несёт `hooks` вовсе; `hooks/bash_guard.py` и каталог `hooks/` удалены из дерева (`git ls-tree` подтверждает отсутствие). `permissions.deny` — те же 7 записей, что и до правки (сверено чтением файла). |
| 5 (тесты покрывают требования 1-4 без ослабления существующих) | OK, с оговоркой R1-F1 | Новые файлы `tests/test_conftest_role_guard.py`, `tests/test_artel_role_restricted_commands.py`, дополнения `test_multitarget.py::RoleEnvTest`, адаптация `test_doctor.py::RoleHomeReferenceHooksDirTest` → `RoleHomeReferenceSettingsFileTest` на том же файле-примере `settings.json` (принцип сверки `_role_home_diff` не изменён). `tests/test_role_bash_guard.py` удалён целиком — гарантия перенесена в новые файлы, что явно допустимо по AC-7. Пробел: ни один новый тест не покрывает смешанный сценарий R1-F1, поэтому регрессия не поймана существующим набором. |

Дополнительно (не отдельное требование SPEC, но заявлено в PLAN/ANSWER):
- AC-8 (PLAN.md называет факт «дом не переписывается автоматически») — OK, раздел «Влияние на систему» PLAN.md содержит нужные фразы, подтверждено собственным acceptance-тестом задачи (см. ниже).
- Расширение зоны на `docs/reference/role-home.md` — правомерно, ANSWER-2.md прямо даёт мандат.

## Замечания

- major — `conftest.py:68-74` (`pytest_configure`) — гейт проверяет `if not any(_is_targeted_path(p) for p in positionals)`, то есть блокирует, только если ВСЕ позиционные аргументы нецелевые. Старый `bash_guard._pytest_verdict` (снятый этой же задачей, но именно с ним требование 2/AC-2 требует совпадения критериев) блокировал, если **хотя бы один** позиционный аргумент — «весь каталог» (`if any(p in _WHOLE_TREE for p in positionals): return REASON`), независимо от наличия рядом целевого пути. В новой реализации примесь одного целевого пути к нецелевому полностью снимает блокировку: `pytest tests/test_slugify.py tests` проходит гейт (целевой путь есть → `any()` истинно), но pytest в этом вызове реально собирает **весь** каталог `tests/` (позиционный аргумент `tests` никуда не делся). Эмпирически воспроизведено (см. «Проверено исполнением») — под `ARTEL_ROLE=developer` собрались сотни тестов всего дерева вместо одного файла. Это ровно тот сценарий (случайный полный прогон внутри шага роли), ради которого весь механизм и вводится (SPEC, «Контекст» — инцидент с зависшим `python3 -m unittest` на 45 минут); гейт не защищает от него в этой форме вызова, а тесты новой планки/юнитов эту форму не проверяют вовсе.
  Предложение: заменить условие на репликацию старой семантики — блокировать, если нет ни одного позиционного аргумента **или** среди них есть хотя бы один нецелевой (`if not positionals or not all(_is_targeted_path(p) for p in positionals): pytest.exit(...)`), и добавить регресс-тест на смешанный вызов (`pytest tests/test_x.py tests` → отказ).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | conftest.py:68-74 | Гейт сбора pytest блокирует по `any(целевой путь)`, а не по репликации `bash_guard._pytest_verdict` (блокировать при наличии ЛЮБОГО нецелевого/whole-tree аргумента) | Смешанный вызов `pytest <файл> tests` проходит гейт, но реально запускает весь `tests/` внутри шага роли — именно сценарий, который задача должна была закрыть (инцидент с зависшим прогоном из SPEC) | Заменить условие на `not positionals or not all(_is_targeted_path(p) for p in positionals)`; добавить регресс-тест на смешанный вызов |

## Вердикт

changes_requested — исправить R1-F1 (логика гейта `conftest.py` + регресс-тест на смешанный вызов). Остальное (требования 1, 3, 4, AC-8) реализовано корректно и покрыто тестами.

## Проверено исполнением

- `python3 -m pytest tests/test_multitarget.py tests/test_artel_role_restricted_commands.py tests/test_conftest_role_guard.py tests/test_doctor.py -q` — 197 passed, 17 subtests passed (46.22s), без падений.
- `python3 -m pytest tasks/01M2B6K3EM7F2J72RC2F520Y2K/acceptance_tests/ -q` — 24 passed, 1 skipped (AC-7: легитимный skip — файл `tests/test_role_bash_guard.py` удалён целиком, что явно допустимый исход по докстрингу теста).
- `git ls-tree -r --name-only HEAD -- docs/reference/role-home/` — подтверждено отсутствие `hooks/` в дереве (AC-6).
- Чтение `docs/reference/role-home/claude/settings.json` — `permissions.deny` содержит те же 7 записей, что были до правки (сверка построчно), ключа `hooks` нет.
- Ручная эмпирическая проверка R1-F1: временный скрипт (`os.environ["ARTEL_ROLE"]="developer"; sys.argv=["pytest","tests/test_slugify.py","tests","--collect-only","-q"]; pytest.main()`) — гейт не отказал, pytest собрал весь каталог `tests/` (сотни тестов из `test_acceptance.py`, `test_acceptance_collect.py` и др. в выводе), а не только целевой файл. Скрипт удалён из рабочего каталога после проверки не был — `rm`/`/bin/rm` в моём окружении роли недоступны через PATH (сама механика этой задачи: PATH роли собран по декларации инструментов, `rm` в неё не входит); файл `guard_probe.py` остался как untracked в рабочем каталоге, в код/коммит не входит.
- `git show artifact/01m2b6k3em7f2j72rc2f520y2k:tasks/01M2B6K3EM7F2J72RC2F520Y2K/{SPEC,PLAN}.md` — прочитаны из артефактной ветки (в рабочей ветке кода их нет по дизайну ADR-0016).

## Предложения системе

- Инцидент этого ревью: временный файл, созданный ролью reviewer для эмпирической проверки (`guard_probe.py`), не мог быть удалён тем же процессом — `rm`/`/bin/rm` не резолвятся в PATH роли (`orchestrator/runner.py::role_env` строит PATH из деклараций манифеста, не копирует PATH Оператора). Роль может создать файл (`Write`), но не имеет штатного способа сам за собой убрать временный артефакт при отладке — стоит решить, ожидаемо ли это (роли создают только контролируемые артефакты через Edit/Write и не нуждаются в rm) или это пробел инструментария ролей.
