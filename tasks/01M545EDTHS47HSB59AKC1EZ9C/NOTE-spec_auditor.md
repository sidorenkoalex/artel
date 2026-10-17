# Записка spec_auditor (визит 4, SPEC sha ca8e0a7f)

## Выяснено
- sha SPEC = ca8e0a7f (git hash-object) — совпадает с миссией. ANSWER-n нет; решения гейта №1–№3 внесены в SPEC все (П-1 треб.9, А-1 треб.9, В-1 AC-7/AC-8, Ф-1 5.6/AC-8, В-2 AC-2, роль без token_slot — треб.7/AC-10).
- Ссылки подтверждены: github_adapter.py:168,193,306; misc_checks.py:91-94; artifact_branches.py:126-146/137/171-174; ci.py:1148,1207,1240,586,1221; runner.py:1116-1141; suite_run.py:781-782; sandbox.py:1057-1065; test_doctor.py:629-692; config.py:799 COMMON_ZONES (config.py общая зона).
- TmpRootTest уже подменяет config.ROLE_HOME (sandbox.py:1693) — HOME-признак в песочнице и так нейтрален; ARTEL_ROLE песочница не снимает.
- BaseBranchCheckTest — plain TestCase вне песочницы: под процессом роли (HOME = настоящий ROLE_HOME) треб.7 отказал бы check_base_branch → тест красный, если нейтрализация не процессная.

## Не сработало
- Bash: составные команды с `;`/переменными требуют подтверждения — по одной команде.

## Где остановился
- SPEC-AUDIT.md: verdict concerns (мелкие), status ready. Отклонения: П-2 (охват нейтрализации роли), Ф-2 (источник token_slot для gitcmd/ci.gh), Р-1 (исход check_base_branch в процессе роли).

## Чего не хватило
- Справки, какие тесты test_doctor идут вне песочницы (plain TestCase) — искал по grep классов.
