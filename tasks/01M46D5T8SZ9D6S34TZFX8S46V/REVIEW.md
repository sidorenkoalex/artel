---
task: 01M46D5T8SZ9D6S34TZFX8S46V
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Один полный прогон tests/ на машину; таймаут на гейте мержа — свой класс отказа

## Фаза A: план

- Таблица покрытия PLAN полна: требования 1–6 → шаги 1–5. Шаги размера MR,
  не микрооперации.
- Подход не противоречит архитектуре. Замок вынесен из `suite_run` в
  `orchestrator/suite_lock.py` с той же механикой (O_EXCL, мёртвый pid,
  пустой свежий файл), путь файла прежний. Образец — `merge_lock`.
  Замок берётся в `full_suite` (журнал задачи гейта) и в `run_full_suite`
  (`notes`); повторного взятия нет благодаря `held_by_me`. Решение
  обосновано: так сохраняется сигнатура фейков `run_full_suite`.
- Раздел «Влияние на систему» сверен с diff: затронуты `acceptance.py`,
  `config.py`, `fsm.py`, `fsm_merge_gate.py`, `models.py`, `suite_lock.py`
  (новый), `suite_run.py`, `tests/test_suite_lock.py` (новый) и карта.
  Сверх заявленного ничего нет. Откат — revert, файл замка совместим.
  Арифметика «1800 + 900 < LEASE_STALE_AFTER_SEC 7200» верна.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Один файл замка `suite_lock.path()` для всех полных прогонов: `acceptance.full_suite` (автогейт `fsm_autogate.py:306`, approve в acceptance, гейт мержа), `acceptance.run_full_suite` (`notes.py:1010`). `suite_run._acquire_lock/_hand_lock/_adopt_lock/_release_lock` — тонкие обёртки над `suite_lock`. Правило живёт в одном месте. |
| 2 | OK | `_machine_lock` → `suite_lock.wait_acquire` с пределом `config.FULL_SUITE_LOCK_WAIT_SEC = 1800` (`config.py`). Ожидание идёт до `_run_full_suite_now`, поэтому `timeout=` отсчитывается от старта pytest. Держатель пишется в журнал задачи (`FULL_SUITE_LOCK_WAIT_ACTION`) один раз на держателя; без задачи — print. Истёк предел — `_not_started_note` («прогон не начат: машина занята прогоном …»), pytest не зовётся, исход `FULL_SUITE_NOT_STARTED`, лог и итог по sha не заводятся. |
| 3 | OK | `cmd_suite_run` и `background` вызывают `suite_lock.acquire`/`adopt` без ожидания; отказ называет держателя через `describe`, в том числе гейт. |
| 4 | OK | Мёртвый pid: `acquire` снимает замок и берёт заново. Снятие: `try/finally` в `_machine_lock`, а у `suite-run` — прежний `finally` в `background`. Если замок не взят, снимать нечего. |
| 5 | OK | `fsm_merge_gate._full_suite_or_refuse`: таймаут — «прогон не уложился в {FULL_SUITE_TIMEOUT_SEC} с … {run.detail}» (detail несёт итоговую строку и путь к логу); не начат — свой текст с держателем; красный — прежний текст. Во всех трёх случаях `sys.exit` до мержа. |
| 6 | OK | Долгоживущий файл задачи (17 тестов) и `tests/test_suite_lock.py` (6). У каждого метода есть «Ловит мутацию» с наблюдаемым расхождением. Существующие тесты не тронуты (в diff `tests/` только новый файл). |

Смежные правки обоснованы: `fsm._acceptance_full_suite_ok` не даёт
`--accept-red` провести непроверенный набор; `models._PULT_BLAME_STARTS`
относит отказ «прогон не начат» к вине пульта. Литерал совпадает с началом
`_not_started_note` → `_full_suite_detail`, это проверено тестом.

## Замечания

Замечаний уровня blocker/major/minor нет. Два наблюдения, не требующих
правки в этой задаче:

- `orchestrator/suite_lock.py::acquire` — при мёртвом держателе возможна
  гонка: два ожидающих прочли мёртвую запись, первый снял её и создал свою,
  второй затем снимает уже живой замок первого. Окно — микросекунды между
  `_read` и `unlink`, механика унаследована от прежнего `suite_run._acquire_lock`
  без изменений и требует SIGKILL держателя. Пометка на будущее: снимать
  замок через переименование либо сверять inode перед `unlink`.
- В докстринге модуля `orchestrator/suite_lock.py:8` написано: «гейты и
  `notes` берут замок в `acceptance.run_full_suite`». На деле гейты берут
  его в `acceptance.full_suite` (`acceptance.py`, `full_suite`), что
  правильно описано в докстринге `run_full_suite` и в PLAN. Неточность
  только в комментарии, поведение верное.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет — замечаний не заведено.

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest -q tests/test_suite_lock.py tests/test_suite_run.py tests/test_model_sets.py tests/test_approve_acceptance_full_suite.py tests/test_fsm_autogate.py` — 66 passed, 2 subtests passed.
- `python3 -m pytest -q tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py` (долгоживущий файл задачи, AC-1..AC-11) — 17 passed за 102 с.
- `artel.py plank-run 01M46D5T8SZ9D6S34TZFX8S46V` — отказ «планки нет: … нет файлов test_*.py». Планка задачи — только долгоживущий файл в `tests/`, прогнан строкой выше.
- Временные мутации без правки файлов (подмена в процессе, `unittest`):
  `suite_lock.held_by_me = lambda: False` → тест
  `ReentrantRunTest.test_run_inside_own_lock_neither_waits_nor_releases`
  красный; литерал «прогон не начат» убран из `models._PULT_BLAME_STARTS` →
  `test_not_started_refusal_of_autogate_blames_pult` красный. Обе заявки
  «Ловит мутацию» подтверждены.
- Свежесть карты: `scripts/codebase_map.render` в памяти против
  `docs/codebase-map.md` без строки `built_at_sha` — совпадает (fresh).
- CI коммита 24e62f3b по пакету зелёный (16 проверок).

## Предложения системе

- Шаг ревью не может внести временную мутацию через `sed -i` (команда ждёт
  подтверждения, которого в шаге нет), хотя скил review-checklist требует
  именно приём «временная мутация». Работает подмена в процессе через
  `python3 -c` + `unittest`. Стоит описать этот приём в
  `skills/review-checklist.md` либо разрешить правку с откатом.
- `plank-run` отказывает, если планка задачи состоит только из
  долгоживущего файла в `tests/`. Ревьюверу стоит подсказать в отказе
  прогнать долгоживущий файл напрямую.
