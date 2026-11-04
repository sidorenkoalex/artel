# Записка spec_auditor

## Выяснено
- Визит 5 (spec_sha a0b091d2…): разница с e34863a1 — `git -C <wt> diff e7c8d161b 0541d03d8 -- tasks/<id>/SPEC.md`; решение №4 отражено (SPEC.md:62-67, 224-241).
- Факты верны (config.py:57, artel.py:2562, role_prompt.py:197/503, runner.py:1017/1093/1195, gitcmd.py:25/259/263/1123, mutation_run.py:467, plank_helper.py:67); тесты PATH закрепляют только PATH[0].
- Наблюдение: `<клон>/.git/worktrees/<чужая>` попадает в исключение клона — на ревью.

## Не сработало
- Bash с `$VAR` и `cd …;` в составной команде требует подтверждения — писать абсолютные пути/`git -C`.

## Где остановился
- SPEC-AUDIT.md записан: status ready, verdict pass. Шаг завершён (guard — см. ниже).

## Чего не хватило
- Ничего существенного.
