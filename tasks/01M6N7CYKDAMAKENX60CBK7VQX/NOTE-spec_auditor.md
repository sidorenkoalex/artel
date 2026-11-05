# Записка аудитора SPEC

## Выяснено
- AC-7 «gh не вызван» на approve невыполним буквально: `ci.branch_status` GitHub читает check-runs через `ci.gh("api", …)` (ci.py:1206+, :257-282) до и после `trigger_rerun` (fsm_merge_gate.py:316, :372).
- ci-rerun: `ci.verifying_status` (ci_rerun.py:~150) и на красном пути `failed_check_names` зовут gh раньше `trigger_rerun`; SPEC называет только путь зависшей проверки.
- AC-13 «равенство, не содержит» — в действиях тесты утверждают `reason in out` (unsupported_project.py:200,231,259,291,314,391; epic_draft_promote:87; pair_support check_refusal :131) — невыполнимо при запрете правок (треб. 10).
- Требование 3 «<любой файл>»: одна проба имени не доказывает покрытие каталога (`**/ci.yml`, префикс `.github/workflows/c`).
- cleanup: после отправки текст «сервер проекта не тронут…» (cleanup.py:296-302), «PR не тронут» после отправки — новое; тестов на этот текст нет.

## Где остановился
SPEC-AUDIT.md сдан: verdict fail, status ready, guard ок. Шесть отклонений (AC-13 равенство, AC-7 gh, ci-rerun :156, проба файла, литерал в targets.py, текст kill после отправки).

## Чего не хватило
Где gh зовётся на пути статуса CI — искал по ci.py вручную.
