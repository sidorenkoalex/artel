# Записка analyst — 01M57PMBHWK5EGQ8HPA5TQX72H

## Выяснено
- Итерация 3 (возврат из spec_gate, аудит визит 2, 4 решения). Внесено: треб. 3 — NULL target = артель (report.py:554-555, catalog.py:973), число проектов после замены; AC-4 — база с NULL-задачей рядом с DEFAULT_TARGET; треб. 2 + AC-2 — алерт target = id задачи (attention, alerts.py:116-120) без метки в панели report; AC-3 — у каждого проекта записей больше GATE_RATIO_WINDOW, окно проекта ≠ доля в глобальном окне; AC-8 + треб. 7 — эталон литералом/файлом до правки, нормализация времени: фиксированный now модуля report и аргумент now _render, литеральные ts журнала (окна operator-by-day report.py:366-380, test_author 834-842, explore 975-979).
- HTML report сам метки времени не печатает; от времени зависят только окна от datetime.now.
- _alerts_html (report.py:642-653) сейчас target не выводит вовсе.

## Не сработало
- Ничего.

## Где остановился
SPEC.md обновлён, status ready, guard ок.

## Чего не хватило
Какие части HTML report зависят от времени — искал grep по now/datetime в report.py.
