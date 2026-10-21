# Записка spec_auditor — 01M5FGJW4RBN9C9P48Q8MDHJX1 (круг 2)

## Выяснено
- О-1…О-4 и фраза о PR круга 1 перенесены в SPEC (треб. 2, 3, 6; AC-1, AC-6, AC-9).
- `ls-remote` в клоне внешнего проекта получает токен слота: `gitcmd.HOSTING_SUBCOMMANDS` (gitcmd.py:35) несёт `ls-remote`, `_hosting_project` пропускает `-C`/`-c`.
- Мерж `--no-ff` локальной ветки (fsm_merge_gate.py:803), `final_sha` — потомок коммита мержа: голова ветки в origin — предок `final_sha`.
- `_await_main_ci` зовёт `gh` (ci.main_line_status) после мержа — AC-8 «пульт не вызывает команд gh после мержа» буквально ложен.
- Подсказка удаления при несчитанной голове: форма `<sha>` (заглушка?) не названа.
- Существующие тесты, считающие push на гейте мержа, подменяют `_cleanup_merged_task` (test_merge_gate_ci_wait.py:415) — новых поломок не нашёл.
- Вердикт: concerns.

## Не сработало
- Составные bash-команды с `xargs` требуют подтверждения.

## Где остановился
- SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Нет сводки, какие тесты гоняют `_cmd_approve_merge_gate` до конца с живым bare-origin.
