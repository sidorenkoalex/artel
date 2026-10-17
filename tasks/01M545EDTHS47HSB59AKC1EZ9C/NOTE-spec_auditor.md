# Записка spec_auditor (визит 2, SPEC sha ebf23d4a)

## Выяснено
- sha SPEC = ebf23d4a (git hash-object) — совпадает с миссией.
- config.PROJECTS = ROOT/.artel/projects (config.py:50): «пути под config.ROOT исключены» буквально накрывает и клоны внешних проектов → противоречие с треб.1/8, AC-11/13.
- doctor/artifact_branches.py:171-174: главная копия как source — только для артели (is_artel); для внешнего source всегда клон (тест test_doctor_closed_ref_fix::test_external_project_does_not_search_main_copy). Второй признак (URL) реального вызывающего у внешнего проекта не имеет.
- ci.verifying_status (ci.py:586-657) и trigger_rerun (ci.py:1221-1257) НЕ зовут gh с repo= ни разу (check_runs, run_list, _commit_workflow_runs, find_run_id, rerun, watch — без repo) → AC-15 пуст.
- Фикстура tests/sandbox.py:1057-1065 _PROJECT_TARGET_ENTRY несёт token_slot {name}-token; десятки тестов внешних проектов с реальным git/gh-заглушкой; SPEC не говорит, что отдаёт общая подмена keychain.token для этих слотов.
- BaseBranchCheckTest (tests/test_doctor.py:629) — plain TestCase, EXTERNAL_ENTRY без token_slot.

## Не сработало
- awk/цепочки `;` с переменными в Bash требуют подтверждения — по одной команде.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready.

## Чего не хватило
- Нет быстрого способа увидеть, какие ci.gh-вызовы идут с repo= — grep "repo=" по ci.py.
