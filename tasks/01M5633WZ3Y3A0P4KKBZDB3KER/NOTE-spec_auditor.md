# Записка spec_auditor

## Выяснено
- Вердикт concerns (SPEC sha 4272211…). Ссылки SPEC на код верны.
- Признак «артель» на выходе из tests_writing считается в orchestrator/fsm_advance.py:587 (вне зон) и доходит до гейтов только как network_addresses.
- Точный текст пояснения «импорт вне перечня» (guard.py:2597) ни одним тестом не прибит.
- tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py:410 подменяет long_lived_errors_from_files обёрткой (files, task_id, **kwargs) — новый аргумент только именованный, иначе обёртка сломается.

## Не сработало
- sed после cd в Bash требует подтверждения — читать через Read.

## Где остановился
- SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Нет определения «строка-имя» для элемента long_lived_imports (вид list/list0 в targets.py:36-41).
