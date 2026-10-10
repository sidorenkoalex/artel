---
task: 01M4KAYMW2YRFB7G0442WFVSHA
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: ANSWER Оператора в in_dev — основание шага developer, а не переход по готовым артефактам

## Фаза A — план

- Таблица покрытия полна: все требования 1–7 привязаны к шагам; требование 7 закрыто
  явным «существующие методы не правились» — по диффу `tests/` подтверждено (новый файл
  `tests/test_answer_in_dev_gate_journal.py`, существующие файлы не тронуты).
- Шаги — единицы размера MR (константа + запись класса; две функции гейта; вызов в
  рубеже; тесты; карта).
- Подход согласован с архитектурой: гейт рядом с прецедентом `_review_rework_gate`,
  через `_run_gates`, класс отказа в `refusal_classes.REFUSAL_CLASSES`; `auto.py` и
  прочие файлы «только чтение» не тронуты.
- «Влияние на систему» = дифф: 4 файла кода/тестов + карта; гейт ставится раньше
  подтяжки main — заявлено. Откат — revert, правка аддитивна.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `review.py::_unprocessed_answer` берёт все записи `operator` с префиксом «ANSWER создан» — покрывает `answer.py:223` (указание), `:323/:330/:332` (мандаты/эскалация/ждёт approve), `:384` (`zones-extend`). Отказ `ANSWER_UNPROCESSED_REFUSAL_ACTION`, detail называет `posixpath.basename` пути — `ANSWER-n.md`. |
| 2 | OK | Действие в `REFUSAL_CLASSES` с `ROLE_FIXES`; AC-1/AC-2 долгоживущего файла показывают шаг developer с ANSWER в брифе и отсутствие «шаг developer не нужен» до шага. |
| 3 | OK | Гейт в `fsm_advance.in_dev` (стр. ~620), значит ручной `advance` и `auto._pre_advance_step` держатся одним рубежом; AC-6. |
| 4 | OK | Отработанность — по `agent run started` позже ANSWER + `agent run finished`; условий на код нет. AC-3. |
| 5 | OK | Действие не внесено в `ROLE_NOT_FINISHED_REFUSAL_ACTIONS` → общая повтор-остановка; AC-4. |
| 6 | OK | Без ANSWER `pending=None`; ANSWER, закрытый прежним шагом, сброшен при обходе журнала, вход в визит не учитывается. AC-5 (оба метода). |
| 7 | OK | Существующие методы `tests/` не изменены. |

Корректность разбора журнала проверена по живым путям записи:
- `checkpoint.commit_success_checkpoint` вызывается только из `runner._finish_ok` и
  только для `developer` (`checkpoint.py:694–712`, мандат «строго developer»), до
  `agent run finished` — засчитывать её признаком шага безопасно, test_author/reviewer
  этой записи не дают (у test_author своё действие).
- Провал шага пишет `agent run FAILED`, не `finished` → провалившийся шаг ANSWER не
  отрабатывает (верно: бриф мог не дойти до работы). Брошенный `step_open=True` после
  FAILED/обрыва сбрасывается ближайшим `agent run started` — ложного «шаг шёл в момент
  ANSWER» для следующего шага нет.
- Порядок — по `id` журнала, не по `ts`.

## Замечания

Блокеров и major нет. Наблюдения без влияния на вердикт (не заводятся в реестр —
последствий-поломок не несут):

- `orchestrator/advance_gates/review.py:390` — `_ANSWER_ACTION_PREFIX = "ANSWER создан"`
  дублирует `fsm.ANSWER_CREATED_ACTION_PREFIX` (`orchestrator/fsm.py:82`). Прямой импорт
  `fsm` из `advance_gates` — риск цикла импорта, так что дубль объясним; при переименовании
  действия в `answer.py` расходиться будут две копии, а не одна.
- `tests/test_answer_in_dev_gate_journal.py::AnswerRefusalClassTest` — утверждение
  `refusal_class(action) == ROLE_FIXES` повторяет AC-2 долгоживущего файла (ADR-0020 п. 4);
  `assertNotIn(... ROLE_NOT_FINISHED_REFUSAL_ACTIONS)` — структурный дубль поведенческого
  AC-4. Сторож не вредит и ловит заявленную мутацию (проверено), но избыточен.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт

approved — все требования SPEC реализованы, сторожа проверены временными мутациями,
карта свежа.

## Проверено исполнением

- `python3 -m pytest -q tests/test_01m4kaymw2yrfb7g0442wfvsha_answer_in_dev_gate.py
  tests/test_answer_in_dev_gate_journal.py tests/test_refusal_classes.py
  tests/test_fsm_review_rework_gate.py tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py
  tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py` — 42 passed, 62 subtests passed.
- `python3 -m pytest -q -x tests/test_canary*.py tests/test_auto*.py tests/test_fsm_advance*.py
  tests/test_answer*.py` — 410 passed, 67 subtests passed.
- `artel.py plank-run 01M4KAYMW2YRFB7G0442WFVSHA` — отказ «планки нет: в источнике нет
  файлов test_*.py»: у задачи только долгоживущий файл в `tests/`, он прогнан выше.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — расхождение
  только в строке `built_at_sha` → карта свежа; изменение откатил `git checkout`.
- Временные мутации (каждая откачена `git checkout`, дерево чистое после):
  1. `open_at_answer = step_open` → `False` в `_unprocessed_answer` — красные
     `test_step_running_when_answer_was_given_does_not_process_it` и
     `test_pult_commit_for_developer_counts_as_finished_step` (заявки подтверждены).
  2. `_answer_gate`: `path = None` (гейт выключен) — красные AC-1, AC-2, AC-4, AC-6
     долгоживущего файла; AC-3, AC-5 зелёные (как заявлено «зелёны с рождения»).
  3. Удалена запись `ANSWER_UNPROCESSED_REFUSAL_ACTION: ROLE_FIXES` из `REFUSAL_CLASSES` —
     красные `test_answer_refusal_is_role_class_with_repeat_stop`, AC-1, AC-2, AC-4.
- `python3 scripts/guard.py <этот REVIEW.md>` — «GUARD: ок (1 файлов)».

## Предложения системе

- `skills/review-checklist.md` / реестр замечаний: при `schema_version >= 3` любой minor
  в реестре блокирует `approved` до следующей итерации — вкусовые замечания либо
  раздувают итерации, либо уходят в свободный текст мимо реестра (как здесь). Стоит явно
  разрешить minor со статусом, не блокирующим гейт, или прямо сказать, что minor в реестр
  не идёт.
- `orchestrator/fsm.py:82` `ANSWER_CREATED_ACTION_PREFIX` живёт в `fsm`, недоступном
  `advance_gates` без цикла; перенос таких констант действий журнала в нейтральный модуль
  (`answer.py` или `refusal_classes`-подобный) снял бы класс дублей литералов.
