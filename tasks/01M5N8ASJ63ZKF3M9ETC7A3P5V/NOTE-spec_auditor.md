# Записка spec_auditor

## Выяснено
- HEAD ветки 2b187a3d; diff 84c784aa..HEAD по orchestrator/scripts/tests пуст — номера строк ТЗ/SPEC верны.
- Перечень 13 закрытых имён подтверждён (grep `acceptance\._`); прочие совпадения (`_pytest_command` two_sided:279, `_own_target` plank_run:110, `_acceptance_run_body` plank_run:41, fsm_autogate:48, models:1019, plank_helper:34, project_profile:424, outcome_integrity:12) — комментарии/докстринги.
- Подмен тестами имён из списка нет (разбор ast вызовов patch.object/setattr + строки "orchestrator.acceptance.").
- Главная находка: advance_gates/{two_sided,outcome_integrity,tests_writing}.py импортируют `from .. import acceptance` — формы нет в перечне AC-6/8(г).
- AC-7: reader только при profile None и log=; `try` вокруг Reader уже есть (acceptance.py:2865-2868) — мутация «импорт вне try» тестом AC-7 не ловится; «тот же лог» побайтно недостижим (время в итоге pytest).

## Не сработало
- sed/awk в цепочках Bash требуют подтверждения — по одной команде.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns (5 отклонений), guard ок.

## Чего не хватило
- Формы импорта acceptance подпакетами — искал grep'ом `from .. import`.
