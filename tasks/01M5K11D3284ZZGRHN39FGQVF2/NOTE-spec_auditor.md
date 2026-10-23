# Записка spec_auditor — 01M5K11D3284ZZGRHN39FGQVF2

## Выяснено
- Все ссылки SPEC на код сверены и верны: artifact_branch.py:24–27 (докстринг), :315/:425/:444 (вызовы `_send`), :320, :336, :353, :378, :404, :418, :694; store.py:960, :1185; doctor/artifact_branches.py:180–182 (докстринг `_fix_unsent_closed_refs` с `send_pending`); config.py:654 (пол бюджета $25).
- SPEC верно уточнил ТЗ по паузе: подмена `artifact_branch.time.sleep` строкой/парой запрещена сторожем tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py — допустима только подмена атрибута `artifact_branch.time` объектом-заместителем.
- Существующие тесты: `reject_ref_pushes` (tests/test_artifact_ref_sync.py:77) даёт «pre-receive hook declined» → non-ff без повтора; `break_origin` (:69) → «сеть». Строк 5xx в тестах push документов нет. PushSuccessTest (tests/test_artifact_branch_push.py:106, len==1) остаётся зелёным при требовании 4.
- Вердикт: concerns — пробелы AC (нет проверки: «сеть» не повторяется; повтор без --force; деталь успеха с числом попыток; число пауз = попыток−1; негатив «(failed to …)»).

## Не сработало
- `cd … && grep` в Bash требует подтверждения — пользоваться `git -C <wt> grep`.

## Где остановился
- SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Ничего существенного.
