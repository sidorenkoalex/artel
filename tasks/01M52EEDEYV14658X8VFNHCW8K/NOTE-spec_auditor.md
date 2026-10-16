# Записка spec_auditor — 01M52EEDEYV14658X8VFNHCW8K

## Выяснено
- `acceptance.run_plank` (acceptance.py:923) и `two_sided._run_side` (two_sided.py:222) параметра `command` не имеют — всегда команда пульта; `_run_full_suite_now`/`_run_full_suite_to_log` (acceptance.py:1313/1361) получают готовый argv, `command` входит через `run_full_suite` (:1115, :1175). «Оба пути команды» буквально есть только у run/collect/run_repeat.
- yamlmini типизирует значения `env`: `PYTHONHASHSEED: 0` → int 0, `true` → bool, пустое `env:` → None (проверено разбором).
- `secret_env_names()`: claude — CLAUDE_CODE_OAUTH_TOKEN, ANTHROPIC_API_KEY (claude.py:50); codex — пусто (codex.py:500-514), FORBIDDEN_KEY_ENV_NAMES (codex.py:114) в перечень не входят.
- tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py:103 берёт `runner` как «неизвестное подполе» со значением "x"; останется зелёным, если отказ нового правила называет `test_profile` и `runner` (:151-152).
- Цикл импорта targets → providers → roles → models → store → targets: импорт реестра в targets.py только ленивый.
- Profile строят kwargs-ами tests/test_project_profile_gates.py:210, tests/test_network_address_gate.py:178 — новым полям нужны умолчания.

## Не сработало
- grep с `cd … &&` и составные команды режет разрешение — абсолютные пути, по одной команде.

## Где остановился
- Вердикт concerns, SPEC-AUDIT.md записан.

## Чего не хватило
- Нигде не сказано, где у мест запуска параметр `command` — пришлось читать сигнатуры в acceptance.py/two_sided.py.
