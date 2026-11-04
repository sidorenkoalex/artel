# Записка spec_auditor — 01M6KBD9FC36WARWSY9Z0JDMG5 (аудит 4, sha ba970925)

## Выяснено
- Решения №1–№3 перенесены в SPEC; ссылки yamlmini.py:35/:50/:66–87/:126, targets.py:98/191/250/349/394/395/444/539–549, projects.py:104/107/252/275–304/329–350/353, project_checks.py:37, cli.py:150–157, project_profile.py:434/446/472, acceptance.py:213, artel.py:2566/2580/2614, notes.py:414, store.journal(target=) — верны.
- docs/stack.md не содержит раздела о локальном слое проектов (grep «targets»/«слой проектов» пусто) — треб. 11 называет несуществующее место.
- yamlmini `_value`: `[a # b]` → [a]; `[a, b] # c` → [a, b] — потеря текста в списке, AC-4 проверяет только скаляр `x # y`.
- `title` из примера AC-9 — не поле схемы LOCAL_FIELDS; запись с ним не пройдёт merge_local; годится `description.base: "a # b"`.

## Где остановился
- SPEC-AUDIT.md записан: status ready, verdict concerns, О-1…О-4 (docs/stack.md без раздела; `title` в AC-9 не поле схемы; потеря текста в списке не ловится AC-4; прежний несводимый слой в шаге (б) не задан). guard ок.

## Чего не хватило
- Ничего существенного.
