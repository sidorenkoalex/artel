---
task: 01M1THKPNZ11DBZAQDMJ33EMJR
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: стоп-кран волны, часть 1 — счётчик класса отказа по волне и алерт

## Подход

Счётчик и алерт живут в `orchestrator/alerts.py` (владелец таблицы
`alerts`), не в `failure_classification.py` (вне зон этой задачи) и не в
`store.py` (SQL живёт только там, ADR-0003 3ж, а `store.py` тоже вне
зон — трогать её потребовало бы «## Расширение зон» PLAN.md и мандата
Оператора, чего эта задача не заслуживает ради одной агрегирующей
функции). Подсчёт числа РАЗНЫХ задач за окно читает уже существующие
`store.all_tasks`/`store.task_steps` (обычный Python-цикл, не новый SQL)
— вместо задачи с БД сравнимого размера это заведомо достаточно быстро.

Два новых вызова в `orchestrator/runner.py`, ровно в точках, названных
SPEC требованием 3:
1. Сразу после `failure_classification._record_failure_classification`
   — `alerts.check_wave_breaker_failure(conn, failure_class)`. Функция
   сама фильтрует по `failure_classification.TRANSIENT_SYSTEM_CLASSES`
   (1а/1б/системный кандидат) — `None`/«обрыв потока»/session_limit не
   считаются.
2. Сразу после `store.journal(..., "agent run TIMEOUT", ...)` —
   `alerts.check_wave_breaker_timeout(conn)`, отдельный класс «таймаут
   шага» (у него нет записи в `failure_classification.CLASS_LABELS`,
   т.к. это обрыв шага по времени, а не классификация текста попытки).

`alerts.py` импортирует `failure_classification` ОТЛОЖЕННО (внутри
`check_wave_breaker_failure`), тем же приёмом, что уже несёт
`store._close_attention_alert` (комментарий там же объясняет причину):
`failure_classification` сама читает `alerts` на уровне модуля — прямой
импорт с двух сторон дал бы цикл.

Дедуп открытого алерта — по префиксу сообщения (target=self, kind=
incident, source=`wave_breaker`, класс), не по буквальному тексту (число
задач/минуты меняются от срабатывания к срабатыванию) — тот же приём,
что `alerts.raise_token_rate_divergence_alert` (докстринг там же).

Новые константы `config.WAVE_BREAKER_WINDOW_SEC=900`/
`config.WAVE_BREAKER_TASKS=3` — единственный источник порога/окна,
читаются на каждом вызове (не копируются в отдельные переменные).

## Шаги

1. `orchestrator/config.py` — константы `WAVE_BREAKER_WINDOW_SEC`,
   `WAVE_BREAKER_TASKS`.
2. `orchestrator/alerts.py` — счётчик `_wave_breaker_task_count`
   (Python-фильтр по `store.all_tasks`/`store.task_steps`, окно, target
   self), дедуп-обёртка `_raise_wave_breaker_alert` (по префиксу
   сообщения), публичные точки `check_wave_breaker_failure`/
   `check_wave_breaker_timeout`.
3. `orchestrator/runner.py` — два вызова в названных SPEC точках.
4. Юнит-тесты новых функций `alerts.py` (`tests/test_failure_
   classification.py` не трогаем — он вне зон и не про этот счётчик;
   новый файл `tests/test_alerts_wave_breaker.py`), прогон приёмочной
   планки задачи.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (константы) | 1 |
| 2 (подсчёт по классам + таймаут) | 2 |
| 3 (алерт на пороге, дедуп, две точки вызова) | 2, 3 |
| 4 (hung_test_runs не считается) | 2 (читает только journal двух action, не открытые алерты) |
| 5 (только target self) | 2 |

## Влияние на систему

Новый код не меняет поведение `run`/`auto`/бэкоффа/ретраев (SPEC, «Не
входит») — только читает уже журналируемые события и заводит алерт,
который сегодня никто не блокирует (блокировка старта шага — часть 2).
Существующие тесты T082 (`tests/test_failure_classification.py`,
`tests/test_agent_failure.py`) не тронуты — `_record_failure_
classification` и её сигнатура не менялись, новый вызов добавлен СНАРУЖИ
неё, в `runner.py`. `orchestrator/alerts.py` — уже несущий похожий
паттерн (`raise_token_rate_divergence_alert`) модуль, новый код в его
стиле, не меняет существующие функции. `_wave_breaker_task_count`
проходит по ВСЕМ задачам через `store.all_tasks`/`task_steps` на каждый
классифицированный отказ/таймаут — O(число задач × число их шагов) на
срабатывание событий отказа, не на каждый обычный шаг; для размера БД
пульта на сегодня (сотни задач) это доли секунды, тот же порядок, что и
`catalog.cmd_status`, уже делающий `all_tasks` на каждый запрос статуса.
Откат — вернуть оба файла (`config.py`, `alerts.py`) и убрать два вызова
из `runner.py`; ничего постороннего они не трогают.

## Риски

Дедуп по префиксу сообщения хрупок к будущей правке текста алерта —
как и у `raise_token_rate_divergence_alert`, любой, кто перепишет
шаблон сообщения, обязан сохранить совпадение префикса со старыми
открытыми алертами либо явно закрыть их. Не блокирует эту задачу —
свойство, унаследованное от уже принятого в кодовой базе приёма.
