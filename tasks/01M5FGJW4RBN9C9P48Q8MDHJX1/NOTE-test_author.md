# Записка test_author — 01M5FGJW4RBN9C9P48Q8MDHJX1

## Выяснено
- Прошлый шаг не оставил ни одного файла (отказ трассируемости по всем AC).
- Тело гейта мержа на настоящем git гоняют `tests/test_fsm_merge_gate_done_snapshot.py` (внешний проект) и `tests/test_plan_appendix.py::MergeAppendixTest` (артель): `_cmd_approve_merge_gate(..., confirmed_ci_note=...)`, подмена `ci.branch_status`, `acceptance.run_full_suite`.
- Тело гейта закрытое (`_cmd_approve_merge_gate`) — долгоживущему файлу его звать нельзя; поэтому проводка в гейте — разовый файл планки, свойства самой уборки — долгоживущий `tests/test_01m5fgjw4rbn9c9p48q8mdhjx1_merged_remote_cleanup.py` через `cleanup.cleanup_merged_remote(conn, task_id, branch, merged_sha)` (имя — из SPEC «например»).
- AC-8 «пульт не вызывает gh после мержа»: `_await_main_ci` у артели зовёт gh (ci.main_line_status) — проверяю на внешнем проекте через гейт и на самой новой функции у обоих проектов.

## Не сработало
- Составные bash-команды (`;`, `&&`, `$VAR`) требуют подтверждения — по одной команде.

## Где остановился
- Пишу файлы.

## Чего не хватило
- Нет сводки, какие тесты гоняют тело гейта мержа до конца (нашёл grep'ом `_cmd_approve_merge_gate` по tests/).
