# Записка spec_auditor

## Выяснено
- Визит 5: SPEC b73339b1… отличается от b6b16c9f… только переносом решений 3.1 (окружение требования 6 у каждого вызова docker) и 3.2 (workdir обязателен у compose). Дифф снят командой `git diff 4b5f9e5f1 e7284bcac -- tasks/<id>/SPEC.md` в worktree (ссылка refs/artifacts/<id> видна).
- Якоря targets.py:76-77 и plank_layout.py:44-45 верны. Следствие `workdir: .`: _inside("tests", ".") ложно, поэтому layout_mode = outside, а планка ложится в tasks/<id>/… под левой частью "." — противоречия нет.

## Не сработало
- `$VAR` в Bash — отказ «Contains expansion». `ls` нет в PATH, вместо него — python3.

## Где остановился
- SPEC-AUDIT.md сдан: verdict pass, status ready, guard ок; два пункта к сведению.

## Чего не хватило
- Нет.
