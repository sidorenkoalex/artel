# NOTE spec_auditor 01M6TRKY1A41QSZMCXY9TKYXG7

## Выяснено (визит 3, spec_sha 5e75a23d)
- Все 8 отклонений визита 2 закрыты SPEC (AC-1 CI_JOB_RECORD, AC-11 по виду грязи, AC-2 local/ci, 3г только чтением, AC-14 форма, AC-8 Given, 3е как страховка, FULL_SUITE_JOB + 3ж).
- Новое: 3ж сверяет только scripts/plan_appendix_ci.py, но сценарий импортирует из ветки scripts/guard.py (plan_appendices, guard.py:37 тянет orchestrator/config, stack, yamlmini…), а до него в job python исполняется scripts/stack_ci.py (ci.yml:221). Правка guard.plan_appendices в ветке → CI накладывает подмножество, публикует «наложены из X», приёмка примет.
- 3а без исключения tasks/ строже прежнего правила (acceptance.py:3626-3632 терпит неотслеживаемые tasks/).
- Мандат «Ослабление тестов разрешено» снимает любую находку test_integrity (test_integrity.py:47-48) — раздела «Меняемое поведение» не нужно.
- Тесты сценария CI (test_plan_appendix_ci.py, 01m443) проверяют вхождение и код выхода — публикация и сверка FETCH_HEAD их не ломают.

## Не сработало
- grep/awk с `|`, `;`, `$` в bash требуют подтверждения — читать через Read с offset.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns, 3 отклонения (3ж/О-1 импорт guard, 3а tasks/, требование 4 оба основания); guard ок.

## Чего не хватило
- Нет.
