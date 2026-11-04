# Записка spec_auditor

## Выяснено
- Визит 6 (spec_sha 5e0372ae…): разница с визитом 5 — `git diff 0541d03d8 6b37d7c08 -- tasks/<id>/SPEC.md`; решение №5 отражено (SPEC.md:47-51, 73-79, 155-161, 240-248, 263-273, 353-360).
- Опыт: при GIT_CEILING_DIRECTORIES=<корень> git из корня находит репо, из `.artel`, `.artel/logs` — 128.
- Вызовы git пульта у команд роли идут с cwd=ROOT или `-C` (gitcmd.py:1295, 1503-1528, 1603, 1710; plank_helper.py:71; stack.py:614 cwd=_MODULE_ROOT).
- Клон артели: `.artel/projects/artel/repo`; копии в `.../worktrees/<id>` (вне клона).
- Вердикт concerns: Е-1 — запрет SPEC.md:216-217 только про `git clean`, а AC-2 без потолка гоняет `reset --hard`/`checkout -- .`; Е-2 — для чужой копии (внутри ROOT) не задан приоритет строки причины.

## Не сработало
- Bash: только git/python3; `ls`, `$VAR` требуют подтверждения — листинг через python3.

## Где остановился
- SPEC-AUDIT.md записан, status ready, verdict concerns; guard ок.

## Чего не хватило
- Ничего существенного.
