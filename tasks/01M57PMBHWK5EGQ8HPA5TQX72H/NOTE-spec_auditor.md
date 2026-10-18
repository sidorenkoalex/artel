# Записка spec_auditor

## Выяснено
- Визит 3, SPEC sha 6c2a62d3…: четыре отклонения визита 2 закрыты (NULL→DEFAULT_TARGET в треб. 3, AC-2 строка attention, AC-3 окно по проекту, AC-8 эталон до правки).
- Факты по коду подтвердились: report.py:553-558/58/355-363/366-380/834-842/975-983, watch.py:295-308/468-473, catalog.py:973-990, artel.py:1132-1133, alerts.py:116-120/238.
- Алерты target NULL реально заводятся (budget.py:359, amend.py:881, doctor/canary_pool.py:240, live_smoke.py:41, hung_test_watchdog.py:209, alerts.py:177).
- observations.target NOT NULL (schema.py:47) — NULL-алерт сейчас не доставляется никому, факт SPEC верен.
- safe_text(None) не падает (str(None)="None") — моя записка визита 2 ошибалась.
- zone_lock фильтрует по проекту (zone_lock.py:322); merge-очередь общая — в «Не входит».
- Новые отклонения: AC-1 без NULL-задачи (мутация `[None]` в 5 местах кроме плитки не ловится); треб. 2 не задаёт источник «имени внешнего проекта» для алерта.
- Тесты test_report.py:87-111,185-203 зовут `_gate_ratio(steps)`/`_metrics_html([], [], 3.0, 7.0)` — сигнатуры надо сохранить.

## Не сработало
- Составные команды bash и `cd …; git` требуют подтверждения — по одной команде, git grep.

## Где остановился
- SPEC-AUDIT.md готов (status: ready, verdict: concerns), guard ок.

## Чего не хватило
- Нет.
