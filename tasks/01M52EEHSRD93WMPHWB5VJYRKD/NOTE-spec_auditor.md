# Записка spec_auditor — 01M52EEHSRD93WMPHWB5VJYRKD

## Выяснено
- Адреса требования 1 SPEC совпадают с кодом (fsm_merge_gate.py:962-967, suite_run.py:511/:533, plank_run.py:187, amend.py:545-549/:715-718, pull.py:664-666, fsm_advance.py:594-596, tests_writing.py:558-563, test_integrity.py:1429/:1527, notes.py:1040).
- Пропущено: advance_gates/acceptance.py:387-405 (прогон планки in_dev->verifying, `command = list(decision.profile.command)`) и :169 (`run_repeat` в `_seed_repeats_escalate`) — файл в зонах, в требованиях и AC его нет; часть 2 его не меняла.
- amend.py:715-718 зовёт collect/run без cwd -> config.ROOT (acceptance.py:593): одного профиля мало, workdir отсчитается от корня пульта.
- run_plank и two_sided.run принимают профиль параметром `profile`, не `command` (acceptance.py:97, :1097; two_sided.py:320).
- AC-1/AC-2 уже выполнены на main частью 2 (acceptance_suite :2098-2101; вызовы fsm_autogate.py:326, fsm.py:1294).
- Внешние проекты с pult-pytest: pull/amend/plank-run/two_sided сегодня идут командой пульта; после передачи профиля — его командой. SPEC об этом молчит.

## Не сработало
- `cd ... ; cmd` и `ls` в Bash отклоняются — нужны абсолютные пути и одна команда.

## Где остановился
- SPEC-AUDIT.md заполнен, вердикт concerns.

## Чего не хватило
- Перечня всех вызывающих мест запуска с каналом профиля — искал grep'ом по orchestrator/.
