---
task: 01M44ENW1B73Z80PR73HP1C9CG
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: answer отказывает на ключ, approve эскалации «нужен шаг роли» без ответа — только с флагом

## Фаза A — план

- Таблица покрытия полна: требования 1–9 сопоставлены шагам 1–5.
- Шаги размера MR: разбор `artel.py`, проверка в `fsm.py`, подсказки, документ, тесты.
- Подход вписан в существующую архитектуру: новое состояние FSM не вводится. Отказ стоит внутри `escalated -> <возврат>` тем же приёмом, что прежний отказ по `answer_baseline`. Флаг доходит до обработчика через `partial`, как `accept_red`/`fixes_main`. Перечень меток теперь один (`fsm.ROLE_STEP_REQUIRED_MARKERS`), и `auto._ROLE_STEP_REQUIRED_MARKERS` ссылается на него, поэтому определение термина SPEC и проверка `approve` не разойдутся.
- «Влияние на систему» сверено с диффом. Затронуты ровно `artel.py`, `fsm.py`, `auto.py`, `config.py`, `docs/operator-session.md`, новый `tests/test_approve_no_answer_units.py` и карта. `pull.py`, `runner.py`, `canary.py` и `tests/test_invariants.py` не тронуты. Откат — revert merge-коммита.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `artel.py::_answer_args` вызывается в лямбде диспетчера до `answer.cmd_answer`, то есть до lease, журнала и коммита. Отказ (`sys.exit`) в пяти случаях: пусто, нет файла, ключ «--…», лишние аргументы, не `is_file()`. Каждый текст несёт синтаксис `artel.py answer <id> <файл-с-ответом>` и полученный аргумент. Состояние не читается, поэтому отказ одинаков в любом состоянии. |
| 2 | OK | `fsm._approve_escalated`: при `unanswered_role_step_escalation != None` и без флага пишется запись журнала `fsm` «approve отклонён: нет ANSWER после эскалации», печатается текст с ANSWER, командой answer и флагом, перехода нет. Учитывается только хвост журнала после последней «state -> escalated», поэтому старый ANSWER не засчитывается. |
| 3 | OK | Флаг пишет запись `operator` «эскалация снята без ответа» с detail последней эскалации, затем идёт прежний переход с прежним текстом. Шаг developer после возврата подтверждён AC-4 долгоживущего теста (первое событие — `step:developer`). |
| 4 | OK | Сверка `answer_baseline` стоит первой и возвращает до новой проверки; флаг её не обходит (AC-5). |
| 5 | OK | `_approve_sha_arg` пропускает `--no-answer`. `_cmd_approve` отказывает по флагу вне `escalated` до `confirm_fixation`; текст называет флаг и `escalated`. |
| 6 | OK | Без метки в хвосте функция возвращает `None`, путь прежний. С меткой и записью «ANSWER создан…» в хвосте — тоже `None` (покрыты оба вида: `answer` и `zones-extend`). |
| 7 | OK | `auto_stop_advice` подменяет подсказку на `config.AUTO_STOP_ESCALATED_ROLE_STEP`. Подсказка серии конфликтов подтяжки идёт через `ESCALATED_ROLE_STEP_HINT`. Голого `approve <id>` в обеих нет. `runner.py` и `answer.py` не тронуты. |
| 8 | OK | Справка `artel.py`: строка команд `[--no-answer]`, абзацы про указание в `in_dev`/`review`, про отказ на ключ и про флаг. В `docs/operator-session.md` добавлен пункт о флаге и журнале. |
| 9 | OK | Свойства AC-1…AC-8 держит долгоживущий `tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`. Свой файл разработчика его не повторяет и покрывает соседние углы: sha с флагом в обоих порядках, основание `--accept-red`, равное «--no-answer», каталог вместо файла, флаг на эскалации без метки, detail из последней эскалации. У каждого теста есть заявка «Ловит мутацию» с наблюдаемым расхождением. |

## Замечания

Замечаний уровня blocker/major нет. Наблюдения уровня minor (вкус, сценарий поломки слабый) вынесены в раздел «Вердикт» как ненавязываемые — в реестр не заносятся, чтобы не держать вердикт открытым из-за вкуса.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved.

Наблюдения minor (необязательны к правке, на усмотрение разработчика и Оператора):

- `orchestrator/config.py:806-811` вместе с `orchestrator/auto.py:534-536`. Подсказка `AUTO_STOP_ESCALATED_ROLE_STEP` не несёт `{sha}`, а прежняя `AUTO_STOP["escalated"]` давала `approve {id}{sha}` (SPEC «approve: полный sha в подсказках»). Команда `approve <id> --no-answer` без sha работает: `confirm_fixation` при `sha is None` сверяется с `fixed_sha`. Но готового к копированию sha в этой подсказке больше нет. Можно добавить `{sha}` перед `--no-answer`.
- `orchestrator/fsm.py:1127-1130`. Запасной путь «файлов ANSWER больше, чем записей "ANSWER создан" до эскалации» навсегда засчитывает ответ, если у задачи когда-то был ANSWER-файл без записи журнала (ручной коммит до 01M287TP). Тогда все последующие эскалации с меткой снимаются голым `approve`. План это признаёт («Риски»), путь редкий, а без запасного пути краснели бы существующие `test_pull_conflict_marker_states`/`test_answer_gate`. Принимаю как осознанный компромисс.
- `orchestrator/artel.py` (справка, абзац `--no-answer`). Идентификатор разорван переносом: «`answer_` / `baseline`» в моноширинной разметке. Косметика.

## Проверено исполнением

- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M44ENW1B73Z80PR73HP1C9CG` — `test_ac7_approve_sha_arg.py`: 1 passed, код выхода pytest 0.
- `python3 -m pytest -q tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py tests/test_approve_no_answer_units.py tests/test_pull_conflict_marker_states.py tests/test_answer_gate.py tests/test_cmd_approve_dispatch.py tests/test_auto_escalated_return_rework_gate.py tests/test_artifact_escalation_marker.py` — 54 passed, 19 subtests passed.
- `python3 scripts/codebase_map.py` и `git diff --stat -- docs/codebase-map.md` — расхождение только в строке `built_at_sha` (32d494db → e944329c; проверено через `git diff -U0`). Это метка, не дефект: содержимое карты свежее. Регенерацию откатил через `git checkout -- docs/codebase-map.md`.
- Код прочитан адресно сверх пакета: `fsm._answer_file_count` (откуда считается запасной путь), `canary._pass_escalated_with_synthetic_answer` (идёт через `answer.cmd_answer`, поэтому пишет запись «ANSWER создан» и не даёт ложного «файлов больше записей»), `answer.py:323-385` (все действия создания ANSWER начинаются с «ANSWER создан»), `auto.auto_stop_advice` (форматирование `{id}`/`{sha}` новой подсказки), `lease.run_locked` (`finally` освобождает lease при `sys.exit` отказа флага).
- Дифф `tests/`: изменённых и удалённых утверждений нет, добавлен только новый файл. Ослабления набора нет.
- CI коммита e944329c зелёный (16 проверок, из пакета).

## Предложения системе

- Скил review-checklist: при `schema_version >= 3` любое замечание из «Замечаний» обязано попасть в реестр, а `approved` требует всех записей `accepted`. Поэтому minor «на вкус» в аппрув занести нечем, кроме как вне реестра. Стоит явно разрешить в форме REVIEW.md неблокирующие наблюдения minor вне реестра либо ввести для них отдельный статус.
