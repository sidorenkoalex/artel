# Записка spec_auditor — 01M6EXF3TMNRKCZH8CS9BXXG1Z

## Выяснено
- Второй аудит: SPEC sha 638ccd96…, вердикт concerns (SPEC-AUDIT.md). Двенадцать пунктов первого аудита (fail на 2ce503df…) в SPEC закрыты.
- Тестировать сбой на гейте мержа трудно: при постоянном TargetsError гейт отказывает ещё в repo_context.resolve (fsm_merge_gate.py:1508-1514, repo_context.py:93-96), до people_entry. При постоянном sqlite3.Error отправка падает исключением в gitcmd._project_tasks (:215-220), это происходит внутри _push_plan. Тест AC-9 должен подменять сбой в названном чтении, иначе он зелёный и без правки.
- В результатах forge у ошибки есть только текст reason, кода ответа нет (forge.py:42-49, :112-118). Отличить 403 от временного отказа можно только разбором текста «(403)» (gitlab_adapter.py:202-203).
- Хук pre-push: по соглашению в нём только POSIX sh и git (pre-push:10-11). Откуда хук берёт запись проекта, SPEC не говорит.
- Тесты, которые подменяют SUPPORTED_MERGE_GATES и работают с github+target-human (awaiting_human_units:137, awaiting_holds:143), вызывают узлы напрямую, мимо unsupported_reason. Множество пар их не ломает.

## Не сработало
- `$?` и `$VAR` в Bash отклоняет песочница: «simple_expansion». Работает `&& echo`.

## Где остановился
- SPEC-AUDIT.md записан (status: ready, verdict: concerns), guard прошёл. Шаг завершён.

## Чего не хватило
- Как отправка через in_repo проходит повторно через _push_plan внутри git(). Это видно только при чтении gitcmd.py:981-1020.
