# Записка аудитора SPEC

## Выяснено
- Визит 2 (spec_sha 4b79f947…): все шесть отклонений визита 1 закрыты решением гейта №1 и перенесены в SPEC.
- Исключения AC-9 сверены: github_adapter.py:62, doctor/misc_checks.py:98, cleanup.py:304 (_forge_of :237). Других сравнений forge/merge_gate в orchestrator/ нет.
- Сравнения актора с "operator": brief.py:1069, :1354, report.py:371, auto.py:1214, advance_gates/review.py:414 — в SPEC не перечислены.
- cmd_new: _checked_target :755, ensure_clone :829, new_task_id :838. auto: cmd_auto :622 -> _cmd_auto :1028 -> _pre_advance_step :1104; дочерние задачи эпика идут через `auto <id>` (:1365).

## Не сработало
- `ls`/`shasum` в Bash недоступны или требуют подтверждения; glob `--include=*.py` нужно брать в кавычки.

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, status ready, два мелких отклонения (AC-2 через CLI против cmd_new; граница сторожа AC-9).

## Чего не хватило
- Карта не говорит, какие места сравнивают актора с "operator" — искал grep'ом.
