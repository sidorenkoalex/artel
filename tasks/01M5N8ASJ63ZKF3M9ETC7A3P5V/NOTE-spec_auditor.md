# Записка spec_auditor

## Выяснено
- Круг 2 (spec_sha 7607c201). HEAD 2b187a3d; diff 84c784aa..HEAD по orchestrator/scripts/tests пуст — номера строк верны.
- Все пять решений Оператора круга 1 в SPEC перенесены (8(г)/AC-6 формы импорта, AC-7 два сценария, условие потока, сравнение без длительностей, AC-4 `__module__`).
- Новая находка: сценарий 2 AC-7 (`sys.modules["orchestrator.suite_durations"] = None`) не ломает `from . import suite_durations`, если у пакета `orchestrator` уже есть атрибут `suite_durations` (он появляется при любом импорте модуля — в том числе в сценарии 1 для подмены `Reader.start` и в базовом прогоне). Проверено на python 3.13: warm → «import OK», cold → ImportError. По букве SPEC тест красный на правильном коде. Нужно ещё снять атрибут пакета (удалить, не None: None даёт AttributeError внутри try, мутацию не ловит).
- Мелкое: формы AC-6 не включают `from .acceptance import _x` / `from orchestrator.acceptance import _x` в модулях верхнего пакета (сейчас такая форма только для публичного `is_pytest_command`, project_profile.py:461, :651).

## Не сработало
- В Bash нет `ls`/`cat`/`rm` в PATH; `VAR=… cmd` требует подтверждения — запускал `python3 - arg < file` из рабочего каталога.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns.

## Чего не хватило
- Поведение `from . import X` при `sys.modules[X] = None` и наличии атрибута пакета — проверял пробой.
