# Записка spec_auditor (визит 2, SPEC f6631082)

## Выяснено
- Отклонения визита 1 (1–9) в SPEC закрыты, кроме деталей ниже.
- Перечень 35 файлов фикстур (треб. 9) совпадает с `grep -l "test_profile:" tests/*.py`, но неполон: файлы со своей записью + `ARTEL_TEST_PROFILE` (merge_gate_applied:112, main_ci:168, project_docs_ref:43, project_area:202, merge_gate_merge_after:117, merge_gate_in_base:91, postmerge_map_interpreter:107, preflight:311) и dict-записи test_profile.py:120,123-124 (base_entry + профиль без image -> отказ check) в перечень не вошли.
- ANSWER-1 матрица, строка 3 («тот же тест без правки», test_profile.py:107-121) — неверна: :120 зовёт check(base_entry + test_profile) и ждёт успеха.
- amend.py:715,718 зовут collect(tdir)/run(tdir) без cwd -> по правилу SPEC «cwd не задан — путь артели» внешний required-проект гоняет планку на хосте.
- Восьмое место запуска: advance_gates/two_sided.py:227-235 (subprocess.run pytest, _pytest_env) для внешних проектов с профилем (test_integrity.py:1495-1528).
- Рантайм `required` без test_profile (нет image) не определён; внешние без профиля сегодня гоняют планку (advance_gates/acceptance.py:387-405).
- _run_full_suite_now/_to_log и run_full_suite без task_id; suite_run.py:564 зовёт без задачи; источник — suite_lock.my_task_id (suite_lock.py:155).
- tests/test_invariants.py (защищён) в перечне, но test_profile там только в комментарии :187.

## Где остановился
- SPEC-AUDIT.md сдан: verdict fail, status ready, 7 отклонений; guard ок.

## Чего не хватило
- Полного перечня мест запуска: two_sided.py нашёл grep'ом `_pytest_command|_pytest_env`.
