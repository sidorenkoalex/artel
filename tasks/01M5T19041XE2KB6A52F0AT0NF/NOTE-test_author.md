# Записка test_author

## Выяснено
- Планка: разовый acceptance_tests/test_base_values.py (AC-1,2,4,5,24; эталон «как на main» —
  `git show DIFF_BASE:orchestrator/config.py` + ast). До кода: 3 red (AC-1,2,24), 2 green (AC-4,5).
- Долгоживущие tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_*.py:
  entry (AC-3,6,7,8,9,14), gates (AC-10..13), worktree (AC-15..22), doctor (AC-23), flow (AC-25).
  До кода: 35 red / 15 green (зелёные — AC-9, AC-22, загрузка допустимых knowledge, отказ
  agent_wrapper в локальном слое и т.п.).
- Стаб реализации (config/stack/preflight/cli/repo_context/github_adapter/guard/targets/projects/
  workspace) — все 50 долгоживущих и 5 планки зелёные; стаб откатан `git checkout`, scratch удалён.
- git 2.50: в sparse-копии `git add -A` с неотслеживаемым файлом под исключением выходит кодом 1
  (повод AC-20). Стаб лечил это `core.excludesFile` в `config.worktree` рабочей копии.
- Игнор путей обвязки в копии значит: сценарий, коммитящий правку обвязки, должен делать
  `git add --sparse -f -- <пути>` (так и сделано в gates).
- AC-21 «шаг не стартует» — через `runner.role_cwd` (OSError); `runner.cmd_run` в RealGitSandbox
  не идёт (скилы роли читаются из main клона артели).
- Локальный слой требует test_profile/components в description — фикстура это несёт.
- preflight: все проверки пройдены.

## Не сработало
- `runner.cmd_run` в RealGitSandbox: «скил роли developer не прочитан: skills/conventions-core.md».

## Где остановился
- Готово к сдаче.

## Чего не хватило
- Как проверить «шаг роли не стартует» без полного cmd_run — искал дольше всего; ответ —
  `runner.role_cwd` и его обработка OSError в `runner.py` (~1574).
