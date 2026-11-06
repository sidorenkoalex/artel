# Записка spec_auditor — 01M6QZ4RR80B2BYM9AXG5ZMAS4

## Выяснено
- Визит 5: SPEC 58c2ff5b (после решений возврата 4), вердикт concerns, HEAD 88ebf957.
- Все ссылки на строки projects.py/targets.py/artel.py верны; ссылку 4.6
  (:830-831) SPEC исправил на :827-828 — верно.
- Опыт: `_comment_line` ловит `runner: compose  # x`; mapping('') и ('\n\n') → {}.
- Отклонение: шов AC-10 «вызов _render(…, 0, '')» совпадает с пробным
  идиомом `_render({key: None}, 0, "")` (projects.py:550).
- Мелочь: мутация только M в AC-1 не ловится (compose-блок плоский).

## Не сработало
- `ls` в шелле недоступен (zsh eval) — пользоваться Read/grep.

## Где остановился
- SPEC-AUDIT.md сдан (ready, concerns), guard прогнан.

## Чего не хватило
- Ничего существенного.
