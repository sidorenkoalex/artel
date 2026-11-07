# Записка analyst

## Выяснено
- Шаг 3 (возврат со spec_gate, 6 решений + ANSWER-2): переписываю SPEC. Решения сверены с кодом: ci.py:1352-1360 (_last_job, max id), :1384 (сверка), outcome_integrity.py:1045-1048, :1073-1087; forge.py:238-240 (Job без id); hosting_registry test :32-33, :114 (skipif по WITHOUT_REPORT).
- forge импортирует ci (forge.py:20), targets берёт реестр импортом forge при вызове (targets.py:1341-1348) — тест-замена AC-9 подменяет реестр в процессе теста; механизм подмены — дело test_author.
- config.py — общая зона (config.py:883), но по решению 3 добавлена в zones явно.
- Пути gh api для подмены: commits/<sha>/check-runs (ci.py:293), actions/jobs/<id> (ci.py:1805, run_id), actions/runs/<run_id>/artifacts, actions/artifacts/<id>/zip, actions/runs?branch=<base>&status=success.

## Не сработало
- `ls` в Bash недоступен — читаю файлы Read.

## Где остановился
- Готово: SPEC.md переписан (11 требований, AC-1..AC-9, budget 50, ready), guard — ок. Решения гейта: 1 → треб. 11 + AC-9; 2 → треб. 1–2 + AC-1, AC-4; 3 → треб. 3, 5 + AC-3 (константы CI_REPORT_ARCHIVE_MAX_BYTES, CI_REPORT_UNPACKED_MAX_BYTES, CI_REPORT_DOWNLOAD_TIMEOUT_SEC); 4 → треб. 8 + AC-6; 5 → AC-7 + перечень путей gh api перед AC; 6 → треб. 4, 5.
- Оставлено разработчику (Материалы): согласование max Job.id (включая skipped) в ci._last_job с попыткой «наибольший среди исполненных».

## Чего не хватило
- —
