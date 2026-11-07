# Записка spec_auditor

## Выяснено
- SPEC c263d93b: факты gitcmd.py:539-593, targets.py:391/424/486/664/721/849-859/890, вызовы pult_message, snapshot.py:281 — верны.
- Красная фаза AC-4 честная: отказ неизвестного поля (targets.py:539-541) пишет «раздел 'policy': неизвестное поле 'commit_trailer'», подстроки `policy.commit_trailer` нет.
- target-set: _argument_value/_literal round-trip `Harness-Actor: orchestrator` проверен опытом; пустой аргумент — отказ (projects.py:819).
- Существующие тесты (pult_commit_signature:77/98, rewrite_flow:76, target_set:270 динамический, entry_checks, record_fields) не ломаются.

## Не сработало
- Нет.

## Где остановился
- SPEC-AUDIT.md: verdict pass, status ready, guard ок. Замечание без отклонения: байтовая форма AC-2 без служебной строки не задана.

## Чего не хватило
- Нет.
