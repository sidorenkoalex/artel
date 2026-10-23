---
task: 01M5K11D3284ZZGRHN39FGQVF2
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Отправка документов задачи: ответ сервера 5xx — отдельная причина с повтором, запись успеха после отказа, снятие send_pending

## Фаза A: план
- Таблица покрытия полна (требования 1–6 → шаги 1–2), шаги размера MR.
- Подход не конфликтует с архитектурой: повтор идёт тем же модульным `_git`
  (инвариант 33 не затронут), чтение журнала — существующий
  `store.last_task_step_of`, нового SQL нет.
- «Влияние на систему» совпадает с diff: `orchestrator/artifact_branch.py`,
  докстринг `_fix_unsent_closed_refs`, новый тест в `tests/`, карта.
  Откат — revert. Замечание к плану одно и совпадает с R1-F1: шаг 2 не
  ставит долгоживущих тестов на требования 3–4, хотя вся планка разовая.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_classify_push_failure` (`orchestrator/artifact_branch.py:347`): порядок (а)→(б)→(в)→(г), регистр снят через `lower()`, `(failed)` — regex с `re.MULTILINE` и `$`; `(failed to update ref)`/`(failure)` уходят в (в). После мержа сторожа у признаков `HTTP 5xx`/`returned error: 5xx`/`fatal error in commit_refs` и у старшинства (а) над (б) нет — R1-F1 |
| 2 | OK | Цикл `_attempt_push`: не больше `PUSH_SERVER_RETRY_ATTEMPTS` попыток, `time.sleep(PUSH_SERVER_RETRY_PAUSE_SEC)` только между попытками (`:393`), без силы; возврат — четвёрка, `push`/`_send` переведены. Аргумент паузы в `tests/` не проверен — R1-F1 |
| 3 | OK | `сервер (попыток N): <stderr[:300]>` без пары sha и совета; ветка non-fast-forward побайтно прежняя. Долгоживущего теста нет — R1-F1 |
| 4 | OK | `_send` пишет успех при `attempts > 1` или если последняя запись исхода — FAILED (`store.last_task_step_of`); суффикс `(попыток N)`. Долгоживущего теста нет — R1-F1 |
| 5 | OK | `send_pending` удалена, в `orchestrator/` 0 вхождений; оба докстринга называют коммит паспорта на переходе; в `doctor/artifact_branches.py` изменён только докстринг |
| 6 | OK | Тесты без сети: `_git` и `artifact_branch.time` (`TimeWithSleep`) подменены по модулю; существующие тесты не правились |

## Замечания

- major — `tests/test_artifact_branch_server_retry.py` (весь файл) /
  `orchestrator/artifact_branch.py:74,393,396–419,462` — у требований 3 и 4
  (ради них задача и заводилась: «по журналу не отличить "дослано" от
  "не дослано"») и у части требований 1–2 нет сторожа в `tests/`. Вся планка
  помечена `Группа: разовый` (заголовок `test_push_server_retry.py`: guard не
  пускает git-модули в долгоживущие файлы планки), поэтому после мержа эти
  свойства держит только `tests/test_artifact_branch_server_retry.py`, а он
  проверяет только классификацию `(failed)`/регистр/4xx и счёт попыток.
  Проверено временной мутацией: пять поломок одновременно — (1) убран
  `_last_send_failed(task_id)` из условия `_send` (`:462`; успех после отказа
  больше не журналируется, треб. 4); (2) деталь отказа «сервер» без
  `(попыток N)` и с советом «свести merge-коммитом» (треб. 3); (3) из
  `_SERVER_PATTERNS` убраны `http 5\d\d` и `returned error: 5\d\d` (треб. 1,
  AC-4); (4) из `_SERVER_MARKERS` убран `fatal error in commit_refs` (треб. 1,
  AC-2); (5) `time.sleep(1)` вместо `PUSH_SERVER_RETRY_PAUSE_SEC` (треб. 2) —
  `tests/test_artifact_branch_server_retry.py`, `tests/test_artifact_branch_push.py`,
  `tests/test_artifact_ref_sync.py`: 29 passed, ни одного красного.
  Последствие: любая из этих регрессий после мержа пройдёт CI молча (планку
  смерженной задачи никто не гоняет), а регрессия треб. 4 вернёт ровно тот
  дефект, который задача закрывает. Решение: добавить в `tests/` (можно в тот
  же файл) тесты с заявками `Ловит мутацию: …` на: (а) `HTTP 502` и
  `returned error: 503` → «сервер», `fatal error in commit_refs` → «сервер»,
  `[rejected] … (fetch first)` + `Internal Server Error` → non-fast-forward;
  (б) пауза вызвана с `PUSH_SERVER_RETRY_PAUSE_SEC`; (в) запись отказа
  «сервер» — деталь начинается с `сервер (попыток N): `, без
  «свести merge-коммитом» и без sha; (г) `_send`: успех после записанного
  FAILED журналируется, успех после повтора несёт `попыток N`, два успеха
  подряд без отказа — записей нет (песочница БД из `tests/sandbox.py`, как
  в `tests/test_artifact_ref_sync.py`).

- minor — `orchestrator/artifact_branch.py:472` — `last =store.last_task_step_of(`
  — пропущен пробел после `=` (и выравнивание продолжения строки съехало на
  символ). Поправить попутно.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed — в `tests/test_artifact_branch_server_retry.py` добавлены `ClassifyServerSignsTest` (HTTP 502/returned error: 503, commit_refs, (а) старше (б)), `AttemptPushRetryTest::test_pause_uses_module_constant`, `SendJournalTest` (деталь «сервер (попыток 3): » без совета/sha; успех после повтора с «попыток 2»; успех после FAILED пишется; два успеха без отказа — тихо); 8 мутаций по одной (5 из замечания + порядок (а)/(б) + суффикс попыток + ветка «сервер» в журнале) — каждая красит 1 тест | tests/test_artifact_branch_server_retry.py; orchestrator/artifact_branch.py:74,393,396–419,462 | Требования 3, 4 и признаки 5xx/commit_refs/старшинство (а)>(б), аргумент паузы треб. 2 не держит ни один тест `tests/`; планка целиком разовая | Регрессия (в т.ч. возврат «успех после отказа не журналируется») пройдёт CI после мержа молча; подтверждено временной мутацией — 29 passed | Долгоживущие тесты в `tests/` на пункты (а)–(г) замечания, с заявками «Ловит мутацию» |
| R1-F2 | fixed — `last = store.last_task_step_of(…)`, выравнивание продолжения восстановлено | orchestrator/artifact_branch.py:472 | `last =store.…` — пропущен пробел, съехало выравнивание | Вкус/читаемость | `last = store.last_task_step_of(…)` с выравниванием продолжения |

## Вердикт
changes_requested: закрыть R1-F1 (долгоживущие тесты требований 1–4 в
`tests/`) и попутно R1-F2. Код по требованиям 1–5 реализован верно, правок
логики не требуется.

## Проверено исполнением
- `python3 …/artel.py plank-run 01M5K11D3284ZZGRHN39FGQVF2` — 15 passed, код
  выхода pytest 0.
- `python3 -m pytest -q tests/test_artifact_branch_server_retry.py
  tests/test_artifact_branch_push.py tests/test_artifact_ref_sync.py
  tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py` — 33 passed,
  45 subtests passed.
- Временная мутация (5 поломок, перечислены в R1-F1) + прогон трёх модулей
  `tests/` — 29 passed (сторожа нет); код возвращён `git checkout --
  orchestrator/artifact_branch.py`, `git status` чистый.
- `grep -rn send_pending orchestrator/` — 0 вхождений.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` —
  расхождение только в `built_at_sha`, карта свежая; регенерация отменена
  `git checkout`.
- `grep -n Группа acceptance_tests/*.py` — оба файла планки `разовый`.

## Предложения системе
- Класс «планка целиком разовая из-за guard `_GIT_MODULES`»: test_author
  явно пишет, что долгоживущим файл быть не может, но этот сигнал не доходит
  до разработчика как обязанность покрыть свойства в `tests/` —
  `skills/test-authoring.md`/бриф developer мог бы требовать при разовой
  планке на свойства кода список свойств, которые разработчик обязан
  перенести в `tests/`.
