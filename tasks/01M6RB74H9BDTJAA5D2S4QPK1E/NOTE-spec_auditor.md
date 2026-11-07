# Записка spec_auditor

## Выяснено
- Третий визит (spec_sha 5e078eb2). Все шесть отклонений прошлого аудита закрыты решениями гейта №2 и правкой SPEC.
- Факты подтвердились: forge.py:96, project_checks.py:51 (ci_by_pipeline), unsupported_project.py:491 (test_ac9), epics.py:796 (cmd_new в обход обёртки), catalog.py:856, projects.py:986/:889-893/:900-926, cli.py:312-355 (починки до all_checks, sys.exit(1) при fail).
- Внешний триггер «сверка до записи не прошла»: GET /user с username "   " — token_user принимает любую строку (gitlab_adapter.py:583), _render пишет его в кавычках (проверено опытом), merge_local → _check_delivery (targets.py:517, :715-720) отказывает → _merge_mismatches. SPEC этот триггер не называет.
- Существующие тесты new на GitLab — только pair_support:161 и unsupported_project:401; подмены /user с адресом нет → warn → зелёные.

## Не сработало
- —

## Где остановился
- SPEC-AUDIT.md сдан: concerns, ready.

## Чего не хватило
- Цепочка merge_local → _check_delivery (targets.py:486-518) — не сразу.
