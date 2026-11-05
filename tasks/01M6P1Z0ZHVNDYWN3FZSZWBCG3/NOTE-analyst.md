# Записка analyst

## Выяснено
- Шаг 4 (третий возврат со spec_gate, решения 1–6 по аудиту): все внесены.
  - Р1 → AC-7: пароли не в `GIT_CONFIG_VALUE_*` и не в выводе `GIT_TRACE=1` `credential fill`.
  - Р2 → общий абзац безопасности: `GIT_TERMINAL_PROMPT=0`, NOSYSTEM, GLOBAL пустой, ≤60 с для всех git-вызовов, включая прямой `credential fill` (AC-3/5/8).
  - Р3 → требование 2 (правило хоста `url_host` с портом, регистр имени не важен, другой порт — другой хост; общее для треб. 2/4/5), требование 4, требование 5 (не из поля — прежний `_remote_kind`), AC-3 (другой порт — пусто), AC-5 (другой порт — `fail`).
  - Р4 → требование 5 и AC-5: нет `.gitmodules` при поле — `warn` на каждый путь; `http://` на хосте записи — `warn` «адрес `http://`, токеном слота не проверяется».
  - Р5 → AC-2: эталон = `GIT_CONFIG_COUNT/KEY_n/VALUE_n` + `ARTEL_HOSTING_*`, без GLOBAL/NOSYSTEM.
  - Р6 → AC-9 и «Не входит»: + `tests/test_push_hook_units.py`, `tests/test_push_hook_stand.py`.
- Сверено: gitcmd.py:59-72 `url_host`; project_checks.py:1331-1342, :1372-1373, :1386-1389 — совпадает с решениями.

## Не сработало
- Bash с `$?` отклоняется (simple_expansion) — команды без переменных.

## Где остановился
- Шаг завершён: SPEC.md status ready, guard ок, budget 35 без изменений.

## Чего не хватило
- Ничего существенного.
