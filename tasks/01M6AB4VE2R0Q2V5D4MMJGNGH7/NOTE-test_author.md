# NOTE test_author (визит 3, после ANSWER-1)

## Выяснено
- ANSWER-1 п. 5: опрос по `policy.mr_sync_interval_min` — только надзор эпика (`auto.cmd_auto_epic`); `auto <id>` в awaiting_human не живёт.
- Надзор эпика гоняется прямо `auto.cmd_auto_epic(epic, obs, launch)`; цикл обрывается исключением из подменённого `auto.time.sleep` (cmd_auto_epic журналирует abort и пробрасывает). Часы: заместитель `auto.time` (sleep/time/monotonic) + `store.now`. Сверка в опросе = рост журнала задачи.
- Эпик: `epics.new_epic_id()` + `store.insert_epic` + `conn.commit()` + `update_task(epic_id=…)`; наблюдение — `store.register_observation` (позиция с текущего max steps).
- `watch --observation` требует сессию наблюдения (`ARTEL_SESSION_ID`); на darwin `_notify` зовёт osascript — тест подменяет `sys.platform` на linux, считает строки «уведомление: …».
- ANSWER п. 1: «MR не найден» = отказ mr_status с причиной «не найдено (404): …» (форма адаптера); AC-8/AC-9 переведены с пустого mr_iid на 404 (`Stand.not_found`).

## Написано (этот визит)
- tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync.py: AC-17 (3 метода: без поля не сверяют `auto <id>`/надзор; с полем — интервал и не закрывает при трёх итогах; отказ загрузки 0/отриц./не целое), AC-18 (одно уведомление на смену, ни одного на повтор).
- Пометки escalate AC-17/AC-18 сняты из acceptance_tests/test_ac20_invariants_appendix.py.
- Валидация стабом (опрос в `_supervise`, поле в targets, значимое действие в watch, поля MergeRequest): 11 методов зелёные; мутации «без интервала», «каждая сверка значима», «опрос по умолчанию», «0 принят» пойманы. Стаб откатан `git checkout`, в дереве только правка своего tests-файла.
- preflight — всё «пройдена»; plank-run красен по причине «нет PLAN».

## Не сработало
- shell-функции и `${…}` в Bash отклоняются; мутации — по одной python-heredoc правке на вызов.

## Где остановился
Шаг сдаётся: все AC покрыты, escalate-пометок нет.

## Чего не хватило
Как оборвать цикл надзора эпика без закрытых имён — нашлось: исключение из подменённого `auto.time.sleep`.
