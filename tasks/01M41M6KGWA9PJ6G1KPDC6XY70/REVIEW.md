---
task: 01M41M6KGWA9PJ6G1KPDC6XY70
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: CI быстрее — проверка на минимальной версии Python отдельным параллельным заданием; песочница FsmTest не сорит в каталог задач

## Фаза A: план
- Таблица покрытия PLAN закрывает все 7 требований SPEC; шаг один — одно
  многофайловое приложение к защищённым путям (`.github/workflows/ci.yml`,
  `tests/test_invariants.py`). Для задачи, где весь объём — приложение,
  это правильный размер, не «сделать всё».
- Подход не конфликтует с архитектурой: кодовая ветка не меняется (diff
  ветки пуст, карта не регенерируется — `*.py` не тронуты), правка ложится
  на мерже (`fsm_merge_gate.py`), как требует SPEC п.7.
- «Влияние на систему» соответствует приложению: новое задание
  `python-min`, перенос трёх шагов + pytest, подмена `TASKS`, сторож,
  расширение инварианта 36 на `python-min`. Сверх этого в приложении ничего нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `python-min`: `needs: changes`, `if:` побуквенно как у `python`, свой checkout, `timeout-minutes: 40`; из `python` шаги `--min` убраны (хунк переносит их под новый ключ задания). |
| 2 | OK | `pytest tests/test_invariants.py -n auto -p no:cacheprovider -p timeout -p xdist -o timeout=120`. |
| 3 | OK | Шаги не удалены, `continue-on-error` нет; `pip install -r requirements.lock` в новом задании; снимок и сверка ссылок остались в `python` вокруг полного `tests/`. |
| 4 | OK | `git apply --check` проходит (проверено мной). Структуру заданий `ci.yml` читает только `CiJobsByPushClassInvariantTest`; его правка в объёме переноса — проверено мной grep'ом по `tests/`, `scripts/`, `orchestrator/`: остальные места используют путь `ci.yml` как строку или в прозе. |
| 5 | OK (с оговоркой) | Оценка «до» — по замеру `main` (314 с), «после» — расчётная (~190 с / ~90 с). Замер «после» на CI ветки невозможен в принципе: ветка идёт без приложения. Обоснование в PLAN выдерживает критику, AC-6 планки зелёный. |
| 6 | OK | `("TASKS", root / "tasks")` в общем списке подмен `FsmTest.setUp`; `self.tdir = config.TASKS / self.TASK` (стр. 291 после приложения) — теперь во временном каталоге. Лишний `addCleanup(shutil.rmtree, self.tdir)` убран, `tmp.cleanup` его покрывает. Новый комментарий (бриф читает SPEC через подменённый `gitcmd.show` → `config.TASKS`) подтверждён исполнением: все 67 тестов файла зелёные с подменой. |
| 7 | OK | `FsmSandboxKeepsRunRootTasksCleanTest.test_sandbox_task_dir_is_outside_run_root_tasks` — заявка «Ловит мутацию» конкретная и наблюдаемая; временная мутация её подтвердила (см. ниже). Отдельного файла-сторожа в `tests/` ветки нет. |

Утверждения существующих тестов (AC-9, чек-лист «сверены с base»):
`CiJobsByPushClassInvariantTest.violations` — кортеж обхода расширен,
условие `job == "python"` → `job != "guard"` (строго шире), текст находки
параметризован `job {job}`; `test_planted_fail_open_condition_is_caught`
ищет подстроку `fail-open`, она сохранилась. Сужения данных нет. Ослабления нет.

## Замечания

Блокирующих и major-замечаний нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `git apply --check` приложения из PLAN (извлечено из блока ```diff) на чистом дереве ветки — без ошибок.
- Планка: скопирована в рабочий каталог, `python3 -m pytest tasks/01M41M6KGWA9PJ6G1KPDC6XY70/acceptance_tests -p no:cacheprovider -q -s` — 9 passed (зерно AC-7: 710605013).
- Копия дерева HEAD (`git archive`) с наложенным приложением (`patch -p1`):
  `python3 -m pytest tests/test_invariants.py -p no:cacheprovider -p timeout -o timeout=120 -q` — 67 passed, 215 subtests, 117 с; набор записей `<копия>/tasks/` до и после прогона совпал.
- Временные мутации в той же копии (после каждой код возвращён, повторный прогон — 6 passed):
  - `("TASKS", root / "tasks")` → `("TASKS", config.TASKS)` — сторож `FsmSandboxKeepsRunRootTasksCleanTest` красный (1 failed); при этом в `tasks/` копии остался каталог `01M41P001PQW67Z5HT18FX2Y9F` — ровно тот класс мусора, от которого задача.
  - `if:` задания `python-min` → `needs.changes.outputs.code == 'true'` — `CiJobsByPushClassInvariantTest` красный (1 failed).
  - в `if:` задания `python-min` добавлено `!startsWith(github.ref, 'refs/heads/task/')` — `CiJobsByPushClassInvariantTest` красный (1 failed).
- `grep` по `tests/`, `scripts/`, `orchestrator/` на `ci.yml`/`workflows`/`stack-python-min`/имя задания — других читателей структуры заданий нет.
- `python -n auto` локально не гонял: ролевой `conftest.py` отклоняет xdist в шаге (PLAN, «Риски»). Полный `tests/` уже идёт на CI с `-n auto`, включая этот файл на версии манифеста.

## Предложения системе
- `docs/invariants.md`, строка инварианта 36, называет только «job `python`»; после мержа тест держит и `python-min`. Строку реестра стоит обновить отдельно: `docs/` вне зон этой задачи.
- Аналитику: требование «оценка по замерам CI ветки задачи» несовместимо с задачами, у которых вся правка — приложение (CI ветки его не видит). Заказывать замер «до» по ветке/main, а «после» — первым CI `main` после мержа.
