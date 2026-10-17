# Записка spec_auditor — 01M52EEHSRD93WMPHWB5VJYRKD

## Выяснено
- Визит 2 (spec_sha c1f99210…): все 6 пунктов решения Оператора от 17.10 внесены в SPEC (AC-12, cwd=wt_path в amend :715-718, по две точки в AC-3/6/7/8, ключ в AC-4, канал profile, pult-pytest).
- Требование 4, AC-10 и «Не входит» пишут «команда пульта» для внешнего pult-pytest. Но гейт мержа (fsm_merge_gate.py:819-820), suite-run (suite_run.py:277-283), планка in_dev (advance_gates/acceptance.py:393) и tests_writing (fsm_advance.py:594) сегодня идут командой профиля. Это закреплено тестом tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py:456.
- AC-10: безусловную передачу Profile в pull/amend/plank-run/two_sided видно только на профиле, у которого команда не `python3 -m pytest`. На артели не видно.
- advance_gates/tests_writing.py:557 делает `list(command)` и на Profile упадёт.

## Не сработало
- Составные Bash-команды (`;`, `|`, `xargs`, `ls`) требуют подтверждения. Работает одна команда с `cd X && …`.

## Где остановился
- SPEC-AUDIT.md: вердикт concerns, guard ок.

## Чего не хватило
- Было неясно, какой командой сегодня идёт внешний pult-pytest в каждом месте. Ответ дала сверка `_head` (acceptance.py:126-131) с каждым вызывающим.
