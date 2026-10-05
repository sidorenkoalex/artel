---
task: 01M446WEVJXARR5CDED8RE9CCR
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: auto — единые правила «отказ, который чинит роль → повтор шага роли»; run продвигает состояние

## Фаза A — план

- Покрытие: в таблице PLAN есть все требования 1–7 и неослабление тестов (шаг 2, мандат ANSWER-1). Пропусков нет.
- Шаги крупные: шаг 1 — «вся механика». Задача — монолит, его утвердил Оператор (SPEC «Оценка объёма»), так что для этой задачи это допустимо.
- С архитектурой подход не конфликтует. Новый модуль `advance_gates/refusal_classes.py` без импортов пакета снимает цикл `auto → fsm → review → brief`: три копии перечня РНЗ (`auto.py`, `brief.py`, `watch.py`) сведены к одной.
- «Влияние на систему» совпадает с diff. Изменены 13 файлов кода и документации и 3 файла тестов; два из них затронуты по мандату ANSWER-1, третий новый. Защищённые пути (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/`) не тронуты. Откат — revert merge-коммита, схема БД не менялась.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Единственный перечень — `REFUSAL_CLASSES` в `orchestrator/advance_gates/refusal_classes.py`. `refusal_class()` по умолчанию возвращает «чинит Оператор». `auto` читает класс только оттуда (`auto.py` `_pre_advance_step`). Сверил перечень со всеми литералами `"переход отклонён…"` в `orchestrator/` (grep): каждое действие четырёх агентских состояний есть в перечне с классом из таблицы SPEC. |
| 2 | OK | Отказ «чинит роль» даёт `None`, дальше идёт шаг роли. Повтор после шага той же роли даёт `Stop` с действием в причине (`_role_step_between_repeated_refusals`, теперь в любом состоянии). Подкласс РНЗ из брифа по-прежнему вычитается (`brief._ROLE_NOT_FINISHED_REFUSAL_ACTIONS` берётся из единого перечня). РНЗ исключён из повтор-остановки по ANSWER-1, вопрос 2, вариант A; причина описана в докстринге модуля и в PLAN. |
| 3 | OK | Класс «чинит Оператор» даёт `Stop` с первого отказа, причина `f"{refusal} — {hint}"`. Исход `Refused` удалён. |
| 4 | OK | Возврат `True` от `cmd_advance` больше не останавливает цикл: отказ guard'а `fsm.guard_refuses` журналирует актором `fsm`, и он идёт по классу Р. Немедленный стоп оставлен только когда guard отказал без записи в журнал. |
| 5.1 | OK | Все три ветки сбоя git в `review._mutation_claim_gate` (merge-base, diff, show) журналируются действием `MUTATION_CLAIM_GIT_REFUSAL_ACTION`. Отсутствие заявки остаётся за прежним действием. |
| 5.2 | OK | Обе ветки в `acceptance._acceptance_run_body` («не заведена», «не выписана на ветку») переведены на `ACCEPTANCE_CODE_COPY_REFUSAL_ACTION`. Красная планка остаётся за «приёмочные тесты». |
| 5.3 | OK | `_long_lived_git_refusal` покрывает все пять сбоев git: дифф, show на голове, ls_tree main, сумма, запись перечня. Нарушение правила «только добавляет» остаётся за `LONG_LIVED_ACTION`. |
| 5.4 | OK | Переведены на «ветка документов не прочитана»: перечисление QUESTIONS.md (`fsm_advance.py`), подсчёт ANSWER (`fsm.py`), `_tests_writing_ac_state`, SPEC.md в подтяжке (`fsm._pull_main_or_escalate`) и при поиске планки (`acceptance.py`). Оставшиеся вызовы `_read_branch_text_or_refuse` читают только свой артефакт: QUESTIONS/SPEC в `spec_writing`, REVIEW в `review`, PLAN в `in_dev`. Исключения — `fsm._approve_spec_gate` (fsm.py:881) и `canary.py:1286`, но это `spec_gate` и канарейка, они вне четырёх состояний. |
| 6 | OK | `runner.cmd_run_and_advance` вызывается только из `artel._cmd_run_or_detach --attach`; отвязанный `run` тоже исполняется этой формой. Успех шага — запись `agent run finished` этим вызовом. `step_role(t) is None` означает «вне агентского состояния» — тогда `advance` не делается. Исход печатается одной из трёх строк `run: advance …`. `auto.py:901` и `canary.py:1714` зовут `cmd_run` напрямую, поэтому лишнего `advance` нет. `lease.run_locked` возвращает результат `body`. |
| 7 | OK | `idle_steps` растёт и на шагах роли по отказам Р. `AUTO_MAX_STEPS` и стоп-кран конфликта подтяжки не тронуты (AC-13 зелёный). |

## Замечания

Blocker и major нет. Ниже minor-заметки на вкус. В реестр они не заводятся: аппрув от них не зависит, правка по желанию.

- minor — `orchestrator/auto.py:635-641, 830, 841` — поле `_CycleState.prev_refusal` мёртвое: его только обнуляют, никто не читает. Оставлено ради существующего `tests/test_auto_cycle.py:1734-1741`. Можно удалить вместе с этими двумя утверждениями, но для этого нужен мандат на правку теста. Пока поле — безвредный шум.
- minor — `orchestrator/auto.py:275` — имя `_IN_DEV_ROLE_FIXABLE_REFUSAL_ACTIONS` больше не про `in_dev`: туда попадают все действия класса Р, включая review/tests_writing. Имя сохранено ради `tests/test_plan_appendix.py:569-583`; комментарий это оговаривает.
- minor — `tests/test_refusal_classes.py` сверяет с перечнем только действия, объявленные константами в модулях гейтов. Инлайн-литералы `GateRefusal("переход отклонён: защищённый путь" …)`, «гейт заявки мутации», «приёмочные тесты», «реестр замечаний» и др. сторожа не имеют. Если такой текст переименуют в гейте, отказ молча уедет в класс «чинит Оператор», и `auto` остановится там, где раньше чинила роль. Разработчик сам вынес это в «Предложения системе»; задача условия гейтов не меняет, так что в её рамках это не дефект.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: замечаний уровня blocker/major итерация 1 не завела.

## Вердикт

approved

## Проверено исполнением

- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M446WEVJXARR5CDED8RE9CCR`: 10 passed, код выхода pytest 0.
- Тесты затронутых модулей (передний план): `python3 -m pytest -q -p no:cacheprovider` на файлах `tests/test_01m446wevjxarr5cded8re9ccr_auto_refusal_class.py`, `tests/test_01m446wevjxarr5cded8re9ccr_run_advances.py`, `tests/test_refusal_classes.py`, `tests/test_auto_cycle.py`, `tests/test_external_code_copy_refusal.py`, `tests/test_mutation_claim_gate.py`, `tests/test_plan_appendix.py`, `tests/test_watch.py`, `tests/test_brief.py`, `tests/test_advance_refusal_history.py`, `tests/test_canary.py`, `tests/test_invariants.py`, `tests/test_pull.py`, `tests/test_fsm_branch_correct_status_reads.py`: 359 passed и 305 subtests passed за 159 с.
- Временная мутация сторожа: в `refusal_classes.py` литерал «долгоживущие файлы tests/» заменён на «…test/». `tests/test_refusal_classes.py` покраснел (1 failed, subtest с этим действием). Файл возвращён `git checkout`, `git status` чистый.
- Свежесть карты: `python3 scripts/codebase_map.py`, затем `git diff -- docs/codebase-map.md`. Изменилась только строка `built_at_sha`, расхождений по содержимому 0. Файл возвращён.
- Сверка утверждений тестов с base по diff `tests/`: все изменённые утверждения — ровно шесть методов из мандата ANSWER-1. Новых сужений `setUp` или фикстур нет. Удалённое `assertIsInstance(second, auto.Stop)` в `test_other_in_dev_refusal_still_stops_on_the_second_repeat` тоже в мандате. Заявки «Ловит мутацию» в двух изменённых докстрингах (`test_ac1_…`, `test_ac3_…`) называют наблюдаемое расхождение (число вызовов `advance` и остановка до лимита).
- Полноту перечня проверил `grep -rnoh '"переход отклонён[^"]*"' orchestrator`: каждое действие четырёх агентских состояний есть в `REFUSAL_CLASSES`.
- CI коммита 6900910c зелёный (16 проверок, по данным пакета).

## Предложения системе

- `orchestrator/advance_gates/*`: стоит поддержать предложение разработчика — все действия гейтов вынести константами в `refusal_classes` и импортировать их в гейты. Тогда вопрос «литерал перечня разошёлся с текстом гейта» закроется для инлайн-литералов тоже, а сейчас он закрыт только для констант.
