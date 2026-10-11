---
task: 01M4M68557TT4KYN814H8AZ01A
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Этап 4 ADR-0021, часть B — исторические снимки для каталогов tasks/ без refs/artifacts

## Фаза A: план
- Таблица покрытия полна: требования 1–8 сведены к шагу 1. Шаг один, но
  размером с MR: команда, сверка `doctor`, юнит-тесты и карта. SPEC сам
  обосновывает монолит.
- Подход согласован с архитектурой. Команда стоит рядом с коммитом
  закрытия (`snapshot.py`) и разбирает деталь записи тем же
  `_recorded_sha`. Журнал читается через `store.steps_of_action`, без SQL
  вне `store.py`. Read-only пути из SPEC не тронуты: diff задевает
  только `artel.py`, `snapshot.py`, `doctor/artifact_branches.py`,
  `tests/test_snapshot_history.py` и карту.
- «Влияние на систему» соответствует diff. Читателей журнала я сверил
  grep'ом `task_steps`/`all_steps`/`steps_of_action` по `orchestrator/`.
  Почти все читают по id задачи. `report._all_steps` фильтрует по строкам
  `tasks` (`report.py:114`). По действию `HISTORY_ACTION` читают только
  `snapshot.history_snapshots` и `doctor`. Откат описан: revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Список каталогов берётся через `ls-tree -d origin/main tasks/`. Ссылки origin подтягиваются в приватное пространство, локальные — через `_refs_with_prefix`. Дерево — тот же объект `tasks/<id>` через `mktree`, сообщение несёт «исторический снимок» и sha `origin/main`. Затем push. На настоящем `origin/main` все 367 имён каталогов — валидные id (T-серия и ULID), посторонних каталогов нет. |
| 2 | OK | `--dry-run` печатает перечень до любой записи. `refs/remotes/origin/main` двигается обычным fetch, приватные ссылки подтягивания убираются в `finally`. `refs/artifacts/*` и журнал не меняются: это проверяет AC-2. |
| 3 | OK | Существующая ссылка (локальная или в origin) отсекает кандидата. Push идёт без force: parentless-коммит поверх появившейся ссылки origin отклонит. Локальный `update-ref` сверяется с нулевым прежним значением. Fetch без ответа — отказ до записи. |
| 4 | OK | `_newer_in_main` выводит строку `путь  main <блоб>  снимок <блоб|нет>`. Критерий «новее» (блоб отличается и `%ct` main позже) описан в PLAN как риск. |
| 5 | OK | Следует из п.3, подтверждено AC-3 и AC-8. |
| 6 | OK | `store.journal(..., target=config.DEFAULT_TARGET)` пишет запись без строки `tasks`. Деталь `refs/artifacts/<id> <- <sha> (origin/main …)` разбирается `_recorded_sha`. `doctor` сверяет локальную голову и голову в origin с коммитом из журнала. |
| 7 | OK | У записи о закрытии и у живого состояния приоритет выше (`_historical_snapshots`). Случай «только в origin и равна» даёт `ok`. AC-5 гоняет `doctor.all_checks` целиком. |
| 8 | OK | Ссылка несёт дерево `tasks/<id>/...`, `docs_fetch` читает его без правки (AC-7). |

## Замечания
Замечаний нет.

Наблюдения, которые я не считаю дефектами:
- `_create_history_ref` пишет журнал и тогда, когда push прошёл, а
  локальный `update-ref` не удался. Строка вывода подсказывает
  `docs --fetch-all`, а `doctor` считает такой случай «только в origin
  и равна», то есть `ok`. Это согласовано.
- Если в `origin/main` окажется каталог живой задачи без ссылки, команда
  создаст ему parentless-ссылку. `doctor` будет сверять её по правилу
  живой задачи, не по историческому. На текущем main такого каталога
  нет. SPEC требует покрыть каждый каталог без ссылки, так что
  поведение по спеке.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: в итерации 1 замечаний не заведено.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py tests/test_snapshot_history.py tests/test_doctor_artifact_branch_sync.py tests/test_artifact_ref_sync.py tests/test_doctor_closed_ref_fix.py tests/test_snapshot_closing_outcome.py tests/test_multitarget.py`:
  96 passed, 18 subtests passed (74.7 с).
- `artel.py plank-run 01M4M68557TT4KYN814H8AZ01A`: «планки нет»
  (`test_*.py` в `acceptance_tests` ссылки нет). Планка задачи — только
  долгоживущий файл в `tests/`, он прогнан в команде выше: 8 тестов
  зелёные.
- Первая временная мутация, `snapshot.py::_create_history_ref`: проверка
  отказа push заменена на `if False` (журнал и ссылка пишутся несмотря на
  отказ). `tests/test_snapshot_history.py` красный:
  `test_rejected_push_leaves_no_ref_and_no_record` FAILED. Код возвращён
  через `git checkout`.
- Вторая временная мутация, `doctor/artifact_branches.py::_historical_ref_problem`:
  сверка с origin выключена. AC-6 долгоживущего файла красный
  (SUBFAILED на подмене «в origin»). Код возвращён.
- `python3 scripts/codebase_map.py`, затем `git diff -- docs/codebase-map.md`
  без строки `built_at_sha`: расхождений нет, карта свежая. Файл
  возвращён через `git checkout`.
- `git ls-tree -d --name-only origin/main tasks/`: все имена — id задач
  (T-серия и ULID), без посторонних каталогов.
- Сверка «набор не ослаблен» — по diff `tests/`: добавлен только новый
  `tests/test_snapshot_history.py`, существующие тесты не менялись.
- CI коммита 9b934cbc зелёный (из пакета).

## Предложения системе
- `artel.py plank-run` для задачи, вся планка которой лежит в
  долгоживущем файле `tests/`, отвечает «планки нет». Ревьювер должен
  сам догадаться прогнать долгоживущий файл. Стоит либо прогонять в
  этом случае файлы из перечня лока, либо прямо подсказывать это в
  отказе.
