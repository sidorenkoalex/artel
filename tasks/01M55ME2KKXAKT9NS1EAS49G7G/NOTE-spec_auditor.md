# Записка spec_auditor

## Выяснено
- Диф ТЗ применяется к main 6fbeaa8d (`git apply --check` через stdin — «Checking patch skills/test-authoring.md...», без ошибок); абзац skills/test-authoring.md:114-126 совпадает с «Было»; «Стало» в SPEC «Материалы» совпадает со SPEC 01M551W0 (refs/artifacts/01M551W0TFCT2XRQ71XFXJDKB9, SPEC.md:242-259).
- Диф ТЗ без строки `diff --git a/skills/test-authoring.md b/skills/test-authoring.md`: guard `plan_appendices` (scripts/guard.py:380-450, ошибка APPENDIX_NO_HEADER_ERROR guard.py:283) такой блок НЕ считает приложением. Нужен и заголовок раздела `## Приложение…` (guard.py:265). templates/PLAN.md про приложения молчит. Прецедент 01M41VH0Z3CQ0WY039SV1ERGMB PLAN.md:102-105 — с `diff --git`.
- Код уже ведёт каталог по профилю: project_profile.py:70-114, role_prompt.py:183, checkpoint.py:393.

## Не сработало
- `cd … && git` в одной команде — отказ по правилу Read deny; запускать git без cd.

## Где остановился
- SPEC-AUDIT.md написан, verdict concerns (два отклонения: заголовок diff --git; AC-1 не привязан к разбору пульта).

## Чего не хватило
- Правило «блок приложения обязан нести `diff --git`» живёт только в scripts/guard.py, ни в skills/conventions-core.md, ни в templates/PLAN.md.
