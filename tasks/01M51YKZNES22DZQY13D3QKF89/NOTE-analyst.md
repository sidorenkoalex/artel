# Записка analyst — 01M51YKZNES22DZQY13D3QKF89 (визит 6, возврат из spec_gate)

## Выяснено
- Возврат 16.10.2026 по семи замечаниям четвёртого аудита — все внесены в SPEC, деление и рамки частей не менялись:
  1) PYTHONUNBUFFERED=1 для _run_full_suite_to_log — треб. 3, AC-11, D1а-2 п.1;
  2) журнал suite-run пишет хост, -v на config.LOGS запрещён — треб. 3, AC-10, D1а-2 п.1;
  3) required → только runner: pytest-own, targets.check отказывает pult-pytest (и по умолчанию) — треб. 2, AC-3, D1а-1а;
  4) новое треб. 15 + AC-23: отказ run_repeat отличим от результата; orchestrator/advance_gates/acceptance.py
     добавлен в zones родителя и D1а-1б (вызывающий — _seed_repeats_escalate, advance_gates/acceptance.py:148-187, :169);
     из «Не входит» убран из списка неправимых, добавлена оговорка «только обработка отказа»;
  5) отметка установки — в .artel/projects/<проект>/ вне дерева прогона — треб. 8, AC-15, D1а-2 п.2;
  6) новое AC-24: ключ base-итога (suite_run.py:511,533; acceptance.py:1790-1792) — треб. 9, D1а-2 п.3;
  7) _kill_group: acceptance.py:1332, 1337, 1385, 1388 (сверено grep).
- AC теперь 1..24, zones 13, бюджет 60 без изменений.

## Где остановился
- SPEC.md сдан, status: ready, guard ок.

## Не сработало
- Длинный heredoc python в Bash — «Parser aborted»; правки шли Edit по одной.

## Чего не хватило
- Ничего существенного.
