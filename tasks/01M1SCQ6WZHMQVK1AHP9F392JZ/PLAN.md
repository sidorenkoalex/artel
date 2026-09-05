---
task: 01M1SCQ6WZHMQVK1AHP9F392JZ
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: регрессия №15 — рубеж «замечания ревью не отработаны» сверяется с коммитом ревьювера, а не с последним коммитом REVIEW.md

## Подход

`_review_rework_gate_refuses` (orchestrator/fsm_advance.py) сегодня берёт
опорное время как дату ПОСЛЕДНЕГО коммита `REVIEW.md`
(`_commit_iso_date`) — из-за этого автокоммит артефактов шага developer,
тронувший `REVIEW.md` (правка леджера замечаний, T100), ошибочно сдвигает
опорное время вперёд и маскирует штатный шаг developer между вердиктом
ревьювера и этой правкой (инцидент 05.09).

Правки:

1. Новая функция `_reviewer_verdict_baseline(conn, task_id, branch)` —
   опорное время как (`datetime`, источник):
   - сначала git: САМЫЙ СВЕЖИЙ коммит `REVIEW.md`, чьё сообщение — автокоммит
     артефактов шага РОЛИ `reviewer` (тот же признак сообщения, что уже
     несёт `_STEP_ARTIFACTS_COMMIT_PREFIX`, сужен до `reviewer`); коммит
     developer'а (другая роль в сообщении) под этот фильтр не подходит,
     даже будучи самым свежим коммитом `REVIEW.md` — этим и закрывается
     AC-2.
   - нет такого коммита (REVIEW.md правился в обход checkpoint.py) —
     fallback на последнюю по времени запись журнала `agent run finished`
     роли `reviewer` (вторая часть требования 1).
   - ни то ни другое — `(None, None)`, гейту сверять не с чем (та же
     деградация, что у существующего `_commit_iso_date`).
2. `_review_rework_gate_refuses` использует `_reviewer_verdict_baseline`
   вместо `_commit_iso_date(branch, "tasks/<id>/REVIEW.md")` для опорного
   времени; остальная сверка с `code_ts` (существующий
   `_latest_developer_commit_iso_date`) не меняется.
3. Второе условие OR требования 2 — журнальный сигнал: гейт зовёт ОБЩУЮ
   функцию `orchestrator/auto.py::_role_step_since_state_entry(conn,
   task_id, "in_dev", "developer")` (уже существует, регрессия №13) —
   не пишет вторую независимую копию критерия «был ли шаг developer после
   входа в состояние» (AC-4). Есть цикл импорта module-level между
   `fsm_advance` и `auto`? Нет: `auto.py` импортирует `fsm` (не
   `fsm_advance`), `fsm.py` импортирует `fsm_advance` только ЛЕНИВО
   (`from . import fsm_advance` внутри функции) — `fsm_advance` может
   импортировать `auto` на уровне модуля без цикла.
4. Отказ (AC-5) называет опорное время, источник и время последнего
   коммита developer в одной строке `detail`.
5. Юнит-тесты (`tests/test_fsm_review_rework_gate.py`) на функцию
   `_reviewer_verdict_baseline` отдельно от уже залоченных приёмочных
   (`tasks/<id>/acceptance_tests/test_review_rework_gate.py`, которые
   гоняют то же поведение через настоящий git и уже покрывают AC-1..AC-7
   целиком) — дополнительно проверяют вырожденные случаи (git не ответил,
   REVIEW.md не найден) без поднятия настоящего git-репозитория.

6. (ANSWER-3, повторный отказ приёмки итерации 2 — прогон планки
   регрессии №13, `tasks/01M1RHFRQ2C0P4A57XJJ1WZV8N/acceptance_tests`,
   красен на 3 тестах.) `_reviewer_verdict_baseline` возвращает `(None,
   None)`, когда REVIEW.md закоммичен в обход `checkpoint.py` и без
   журнальной записи роли reviewer — этой планкой такой сценарий и
   строится. `_review_rework_gate_refuses` на `review_ts is None`
   возвращала `False` безусловно — гейт открывался fail-open ровно там,
   где ДО этой задачи он отказывал (`_commit_iso_date` последнего
   коммита REVIEW.md). Фикс: `review_ts is None` — fallback на
   `_commit_iso_date(branch, "tasks/<id>/REVIEW.md")` (источник
   `"последний коммит REVIEW.md"`), опора `_reviewer_verdict_baseline`
   остаётся приоритетной. Заодно вскрылось второе следствие того же
   класса: планка регрессии №13 заводит задачу прямо в `in_dev` без
   единой записи журнала `state -> in_dev` — вырожденный ответ
   `auto._role_step_since_state_entry` на этот случай, `(True, None)`
   (легитимный для auto.py, у которого другого сигнала вовсе нет),
   безусловно принимался бы гейтом за «шаг developer состоялся» и
   перекрывал бы уже посчитанный git-вердикт «код не менялся». Правка:
   гейт засчитывает журнальный OR только когда `_detail is not None`
   (реальная запись, не вырожденное отсутствие сигнала) — сама функция
   `auto._role_step_since_state_entry` не менялась (AC-4 по-прежнему
   держится, `tests/test_auto_cycle.py` не тронут). Юнит-тесты:
   `ReviewReworkGateFallbackTest` в `tests/test_fsm_review_rework_gate.py`
   (2 теста, мокают `gitcmd.git`/`gitcmd.show`, без настоящего git).
   Проверка: `tasks/01M1RHFRQ2C0P4A57XJJ1WZV8N/acceptance_tests` — 10/10;
   своя планка (`tasks/<id>/acceptance_tests`) — 9/9; юниты
   `tests.test_fsm_review_rework_gate`/`tests.test_auto_cycle`/
   `tests.test_advance_guard` — 56/56.

## Шаги

1. `orchestrator/fsm_advance.py`: `_reviewer_verdict_baseline`,
   `_REVIEWER_STEP_AUTOCOMMIT_PREFIX`, правка
   `_review_rework_gate_refuses` (опорное время + OR-условие через
   `auto._role_step_since_state_entry` + текст отказа), импорт `auto` и
   `timezone`.
2. Юнит-тесты новой функции и обновлённого гейта
   (`tests/test_fsm_review_rework_gate.py`).
3. Прогон приёмочных тестов задачи (уже залочены) и юнитов затронутых
   модулей (`tests.test_fsm_review_rework_gate`, `tests.test_auto_cycle`,
   `tests.test_advance_guard`).
4. (ANSWER-3) Fallback `review_ts` на `_commit_iso_date` и правка
   условия OR-журнала (`_detail is not None`) в `_review_rework_gate_
   refuses`; юнит-тесты `ReviewReworkGateFallbackTest`; повторный прогон
   планки регрессии №13 и своей планки.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |

## Влияние на систему

Меняется только опорное время и OR-условие ОДНОГО существующего гейта
`in_dev -> review` (`_review_rework_gate_refuses`) — сам гейт, его место
в FSM и остальные гейты перехода (`_capacity_gate_refuses`,
`_zones_gate_refuses`) не трогаются. Новая зависимость модуля:
`fsm_advance.py` импортирует `auto.py` — цикла импорта нет (проверено
`python3 -c "import orchestrator.fsm_advance"`, см. «Подход» п.3).
Существующий журнальный гейт `auto.py` (регрессия №13,
`_role_step_since_state_entry`) не меняется — только переиспользуется,
поведение `auto`-цикла не затронуто (AC-8, `tests/test_auto_cycle.py`
остаётся зелёным). Откат — вернуть `_commit_iso_date` на место
`_reviewer_verdict_baseline` и убрать OR-условие с `auto`.

## Риски

- Git-фильтр по префиксу сообщения `_REVIEWER_STEP_AUTOCOMMIT_PREFIX`
  ищет САМЫЙ СВЕЖИЙ коммит REVIEW.md с этим префиксом, не привязываясь к
  номеру итерации явно (сообщение автокоммита checkpoint.py не несёт
  номер итерации) — при линейной истории это всегда вердикт ТЕКУЩЕЙ
  итерации (следующая итерация reviewer перезаписала бы более старый
  коммит новым автокоммитом с тем же префиксом, который и станет новым
  «самым свежим»); нелинейная история (ручная правка между итерациями,
  переписывающая порядок коммитов) вне зоны этой задачи.
- Задача параллельно зоне регрессии №14 (01M1RNZ6V7TTTTYAHBMF8JBQQS) в
  том же файле `orchestrator/fsm_advance.py` — порядок мержа на
  усмотрение Оператора (SPEC «Не входит»).

## Предложения системе
