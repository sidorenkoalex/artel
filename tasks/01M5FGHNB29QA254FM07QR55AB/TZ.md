---
task: 01M5FGHNB29QA254FM07QR55AB
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Очередь зон: запись «ждёт зоны» закрывается при любом выходе; подсказка merge_after на гейте SPEC

# Очередь зон: запись «ждёт зоны» закрывается при выходе задачи из ожидания; подсказка merge_after на гейте SPEC согласована с отказом

## Факты

Две строки бэклога `docs/backlog.md`, раздел «Бэклог»: «Запись «ждёт зоны» остаётся открытой после выхода из ожидания по stop или потолку» (источник — REVIEW задачи 01M3KHQS7EQTHDT1RGCNH4KGTW) и «Подсказка merge_after на гейте SPEC противоречит отказу answer» (условие «после мержа 01M4R4JQZEX2MBDB195SBJ8A7S» наступило: мерж 775538c9). Оба дефекта воспроизводятся на пине f1f805b6 (сверено по коду).

**Граница задачи одной фразой:** меняются только записи журнала о выходе из цикла ожидания зоны, расчёт минут ожидания для `status` и текст одного отказа `approve` на `spec_gate`; кто держит зону, кто и когда стартует код в зоне, исходы цикла `auto` и все остальные отказы — прежние побайтно.

Дефект 1 — открытая запись ожидания зоны:

- Цикл ожидания — `orchestrator/auto.py:155` (`_wait_for_zone`). Запись входа журналируется на `orchestrator/auto.py:183` (`journal`); её текст — `orchestrator/zone_lock.py:149` (`wait_enter_action`), начало — `orchestrator/zone_lock.py:145` (`_WAIT_ENTER_PREFIX`, «ждёт зоны »). Парная запись выхода — `orchestrator/zone_lock.py:154` (`wait_exit_action`, начало «зона свободна через») — пишется только на `orchestrator/auto.py:218` (`journal`), то есть только когда зона освободилась.
- Остальные выходы цикла возвращают остановку без записи выхода:
  - команда `stop` до сна — `orchestrator/auto.py:189` (`_stop_command_stop`) и во время сна — `orchestrator/auto.py:196` (`_stop_command_stop`); сон прерывает `orchestrator/auto.py:126` (`_sleep_until_next_poll`) по сигналу из `orchestrator/auto.py:36` (`_on_sigterm`);
  - потолок ожидания — `orchestrator/auto.py:190` (`ZONE_WAIT_MAX_SEC`), причина на `orchestrator/auto.py:194` (`_ZONE_WAIT_CEILING_REASON`);
  - потеря lease во время ожидания — `orchestrator/auto.py:198` (`lease_refusal`), причина на `orchestrator/auto.py:202` (`_ZONE_WAIT_LEASE_LOST_REASON`);
  - исключение внутри цикла уходит в `orchestrator/auto.py:639` (`journal`, запись «цикл оборван» в `cmd_auto`) — записи выхода из ожидания тоже нет.
- Каждая остановка цикла затем журналирует «auto остановлен» — `orchestrator/auto.py:561` (`auto_stop`); каждый вызов начинается записью «auto старт» — `orchestrator/auto.py:998` (`journal`).
- Минуты для `status` считает `orchestrator/zone_lock.py:159` (`wait_minutes`): запись входа открыта, пока после неё нет записи с началом «зона свободна через». Вызывающий — `orchestrator/catalog.py:893` (`wait_minutes`, внутри `_zone_wait_suffix`); добавка «ждёт N мин» печатается, пока у задачи есть конфликт зоны. Итог: после `stop` или потолка задача, всё ещё заблокированная зоной (например, одиночный `run` с немедленным отказом), показывает в `status` «ждёт N мин» от давно оконченного ожидания, хотя цикла уже нет. С включённым ожиданием по умолчанию — `orchestrator/config.py:954` (`AUTO_WAIT_ZONE_DEFAULT`) — в ожидание уходит каждый вызов `auto`, поэтому случай частый.
- Попутная находка того же класса: текст операторского снятия ожидания — `orchestrator/zone_lock.py:137` (`RELEASE_ACTION`, «ждёт зоны — снято Оператором (осознанный риск)»), пишет его `orchestrator/zone_lock.py:663` (`cmd_zone_release`) — начинается с того же префикса, и `wait_minutes` принимает его за вход в ожидание.
- Существующие тесты считают записи выхода по началу «зона свободна через» и ждут ровно одну при освобождении зоны: `tests/test_auto_cycle.py:1320` (`exits`), `tests/test_auto_cycle.py:1596` (`startswith`); без записи входа `status` минут не печатает — `tests/test_catalog_status_log.py:252` (`CmdStatusZoneWaitMinutesTest`).

Дефект 2 — подсказка отказа на гейте SPEC:

- Отказ `approve` на `spec_gate` при потере зависимости, заявленной строкой ТЗ «Порядок: после», — `orchestrator/merge_after.py:242` (`spec_gate_declared_refusal`), текст на `orchestrator/merge_after.py:255` (`FIELD`): «снять заявленную может только Оператор: мандат «Зависимости мержа: …» в ANSWER (artel.py answer <id> <файл>) либо эскалация аналитика с вопросом». Вызов — `orchestrator/fsm.py:1191` (`spec_gate_declared_refusal`) в `_approve_spec_gate`.
- Задача 01M4R4JQZEX2MBDB195SBJ8A7S сделала такой `answer` на `spec_gate` именованным отказом: `orchestrator/answer.py:239` (`_spec_gate_answer_text`); текст отказа на `orchestrator/answer.py:253` (`task_id`) уже называет верный путь: reject → эскалация аналитика → answer в escalated. Подсказка гейта ведёт Оператора в отказ.
- Путь существует: `reject` на `spec_gate` возвращает задачу в `spec_writing` — `orchestrator/fsm.py:1656` (`set_state`) в `_cmd_reject`; `answer` в `escalated` со строкой «Зависимости мержа: …» меняет колонку `merge_after` — `orchestrator/answer.py:400` (`state`); до первого прохода гейта SPEC колонка остаётся заявленным значением, и повторная сверка идёт уже с ним.
- Подсказка отказа на `merge_gate` — `orchestrator/merge_after.py:408` (`merge_gate_refuses`) — ведёт к `answer` на `merge_gate`, который там принимается; она верна и не меняется.
- Долгоживущий приёмочный тест `tests/test_01m45d29bqje8fjyja4jqwsyfz_spec_gate_declared.py` требует, чтобы текст отказа содержал и канал ответа Оператора (регулярное выражение «мандат|ANSWER|answer»), и эскалацию («эскалац»).

## Требуется

1. **Парная запись выхода при каждом выходе из ожидания.** `_wait_for_zone` на каждом выходе, кроме освобождения зоны, до возврата `Stop` журналирует (актор `operator`, как запись входа) запись выхода с честной причиной: команда `stop` (обе точки), потолок ожидания, потеря lease. Текст строится функцией `zone_lock` рядом с `wait_exit_action`, несёт причину, накопленные минуты ожидания (тот же счётчик `elapsed_sec`, что у записи «зона свободна через») и последнего известного держателя; текст не начинается ни с «зона свободна через», ни с «ждёт зоны» (например, «ожидание зоны прервано: <причина>; <N> мин, держал <id>»). Новая запись не печатается: вывод цикла прежний побайтно. Возвращаемый `Stop` (состояние, причина, подсказка, признак алерта), печать и последующая запись «auto остановлен» — прежние побайтно. Запись при освобождении зоны — прежняя побайтно, ровно одна.
2. **Открытость ожидания для `status`.** `wait_minutes` считает запись входа закрытой, если после неё (по id) есть любая из записей: прежняя «зона свободна через…», новая запись выхода требования 1, «auto старт», «auto остановлен», «цикл оборван» (последние три закрывают ожидание, прерванное исключением или убийством процесса, как только `auto` той же задачи остановится или стартует снова). Записи «auto старт», «auto остановлен», «цикл оборван» распознаются по точному совпадению действия, записи выхода — по началу строки. Три литерала — константы в `orchestrator/zone_lock.py`; `orchestrator/auto.py` пишет эти записи через константы. Копии литералов в `orchestrator/watch.py` и `orchestrator/canary.py` не трогаются (вне зон). Запись `RELEASE_ACTION` входом в ожидание не считается. Без записи входа — `None`, как сегодня; в незакрытом ожидании — минуты от последней записи входа, как сегодня.
3. **Неослабление механики зон.** Не меняются: `blocking_conflict`, `_start_conflict`, `_occupies`, `claim`, `refusal`, `queue_wait`, `queue_order`, `cmd_zone_release` и тексты `REFUSAL_ACTION`, `RELEASE_ACTION`, `CLAIM_ACTION`; условия выхода из цикла ожидания, интервал опроса, потолок и повтор `run` после освобождения зоны — прежние. Задача по-прежнему не стартует код в занятой зоне: правки касаются только записей журнала и подсчёта минут для показа. В `orchestrator/zone_lock.py` меняются только маркеры ожидания (`_WAIT_*`, `wait_enter_action`, `wait_exit_action`, новая функция записи выхода, `wait_minutes`) и добавляются три константы записей цикла из требования 2.
4. **Подсказка отказа на гейте SPEC.** В отказе `spec_gate_declared_refusal` о потере заявленной зависимости часть после списка потерянных id ведёт по пути, который пульт исполняет: `artel.py reject <id> "<причина: аналитик, эскалируй вопрос о зависимости …>"` → аналитик эскалирует → `artel.py answer <id> <файл>` со строкой «Зависимости мержа: …» в `escalated` → `artel.py approve <id>`. Текст не предлагает `answer` на `spec_gate`; начало отказа (поле, «теряет зависимости, заявленные Оператором строкой ТЗ «Порядок: после»», список полных id) — прежнее; текст по-прежнему содержит «answer» и «эскалац» (условие долгоживущего теста). Отказ о добавке без обоснования, отказ и подсказка на `merge_gate`, отказ `answer` на `spec_gate` — прежние побайтно.
5. Тесты детерминированы, без сети, сон подменён (приёмом `TimeWithSleep` из `tests/sandbox.py`, как в `tests/test_auto_cycle.py`):
   - на каждый выход из ожидания — `stop` до сна, `stop` во время сна (через `_on_sigterm`), потолок (`ZONE_WAIT_MAX_SEC = 0` и ненулевой с несколькими опросами), потеря lease — ровно одна запись входа и ровно одна запись выхода с названной причиной, держателем и минутами; записи «зона свободна через» нет; `Stop` прежний;
   - освобождение зоны — ровно одна запись «зона свободна через», новой записи выхода нет;
   - `wait_minutes`: `None` после каждой из записей закрытия требования 2; число после записи входа без закрытия; `None` при одной записи `RELEASE_ACTION`; новый вход после закрытого — снова число;
   - `status` (`cmd_status` в `orchestrator/catalog.py`): после прерванного `stop` ожидания задача, всё ещё заблокированная зоной, не показывает «ждёт N мин», а держатель и очередь показываются как прежде;
   - неослабление: после каждого выхода из ожидания на занятой зоне отказ старта по зоне (`refusal` в `orchestrator/zone_lock.py`) отказывает, как до выхода, роль не стартует; `zone-release` по-прежнему пускает задачу;
   - подсказка гейта SPEC: текст отказа называет `reject`, эскалацию аналитика и `answer` в `escalated`, не называет `answer` на `spec_gate`; путь исполним — `answer` со строкой «Зависимости мержа: …» в `escalated` меняет колонку, после чего тот же SPEC проходит `spec_gate_declared_refusal` без отказа; отказ о добавке без обоснования и подсказка `merge_gate_refuses` — прежние побайтно.

   Существующие тесты без правок и зелёные.

Зоны: orchestrator/auto.py, orchestrator/zone_lock.py, orchestrator/merge_after.py, tests/

Ограничение зон по смыслу: в `orchestrator/zone_lock.py` — только маркеры ожидания (требование 3); в `orchestrator/merge_after.py` — только текст отказа о потере заявленной зависимости в `spec_gate_declared_refusal`.

Только чтение: docs/backlog.md, orchestrator/catalog.py (`_zone_wait_suffix` — вызывающий `wait_minutes`; подпись не меняется), orchestrator/config.py, orchestrator/lease.py, orchestrator/cycle_hint.py, orchestrator/store.py, orchestrator/runner.py, orchestrator/fsm.py (вызывающий `spec_gate_declared_refusal`, `reject` на `spec_gate`), orchestrator/answer.py (отказ `answer` на `spec_gate`, мандат в `escalated`), orchestrator/advance_gates/mandate.py, orchestrator/doctor/hung_test_watchdog.py (показ ожидания зоны в `doctor`), tests/test_auto_cycle.py, tests/test_catalog_status_log.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_spec_gate_declared.py, tests/test_zone_lock.py, tests/sandbox.py (существующие тесты и песочница не правятся). Вызывающие названных, но не меняемых функций и констант (`cmd_auto`, `auto_stop`, `cmd_status`, `cmd_zone_release`, `_approve_spec_gate`, `_cmd_reject`, `ZONE_WAIT_MAX_SEC`, `wait_minutes`, `_zone_wait_suffix`, `refusal`) — orchestrator/artel.py, orchestrator/merge_queue.py, orchestrator/report.py, orchestrator/canary.py, orchestrator/alerts.py, orchestrator/watch.py, orchestrator/acceptance.py, orchestrator/advance_gates/test_integrity.py, orchestrator/fsm_advance.py, scripts/guard.py — только чтение: подписи не меняются.

Не входит: порядок старта разработки после мержа зависимости (строка бэклога «Порядок старта разработки, а не только мержа», зоны merge_after.py, zone_lock.py, auto.py — отдельная задача); отпускание зоны до `done` (строка бэклога 06.09 о хвосте после разработки); закрытие ожидания процесса, убитого без последующего `auto` той же задачи, по живости lease (`liveness.py` — зона другой задачи); показ ожидания в `doctor`; тексты отказа `answer` на `spec_gate` и подсказки на `merge_gate`; копии литералов записей цикла в orchestrator/watch.py и orchestrator/canary.py. Не заводить одновременно с задачей «Порядок старта разработки, а не только мержа»: те же файлы (merge_after.py, zone_lock.py, auto.py).

Бюджет: $20–25.
