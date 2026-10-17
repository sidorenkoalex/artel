# Записка spec_auditor — 01M545EB0A9F191WTDSPCH36GA (визит 2, spec_sha aed7b40f)

## Выяснено
- Все 6 пунктов решения Оператора на гейте SPEC внесены (треб. 2, 9; AC-1, AC-3..AC-8).
- Факты SPEC о коде подтвердились (brief.py:519/543, claude.py:45/165, runner.py:476/964/1457/1550, base/codex command, role_prompt.py:238, knowledge_cards.py:953).
- store.task_target (store.py:701-707) — fail-open на артель; используется runner.py:1184, :1469. store.py вне зон.
- runner.py:208 и :1376 зовут store.get_task → sys.exit при отсутствии задачи раньше брифа/env/argv: пример AC-8 «задачи нет в БД» недостижим на публичном пути, тест не ловит fail-open.
- artel.py:1877 _ROLE_ALLOWED_COMMANDS — рубеж подкоманд для правила artel.py:*.
- Вердикт: concerns (В-1 AC-8; мелкое — не назван task_target).

## Не сработало
- Bash с awk/пайпами просит подтверждения — только grep/sed.

## Где остановился
- SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Как на пути шага определяется проект (task_target vs get_task) — искал по runner.py.
