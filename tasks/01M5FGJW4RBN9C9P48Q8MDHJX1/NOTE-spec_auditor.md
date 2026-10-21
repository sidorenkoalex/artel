# Записка spec_auditor — 01M5FGJW4RBN9C9P48Q8MDHJX1

## Выяснено
- Ссылки SPEC на код сверены: fsm_merge_gate.py:1284/1322/1352/1424/1522–1535, cleanup.py:153/229/253/266 — совпадают.
- `gitcmd.remote_ref_state` (gitcmd.py:673–687) не принимает `-c http.lowSpeed*`: «читать remote_ref_state» и «ls-remote с пределом» при gitcmd.py «только чтение» несовместимы буквально.
- Нет AC на предел lowSpeed для ls-remote/push пути мержа и на исход «origin не ответил на чтение» вместе с подсказкой ls-remote.
- Подсказка для `None` на push и для исключения не названа (требование 3).
- `_cleanup_merged_task` подменяется `lambda *a, **k` (test_merge_gate_ci_wait.py:415) — новый параметр подмену не ломает; docs/codebase-map.md входит в COMMON_ZONES (config.py:814).
- Вердикт: concerns.

## Не сработало
- Составные bash-команды с `cd`/`xargs` требуют подтверждения — нужны одиночные команды.

## Где остановился
- SPEC-AUDIT.md записан (status: ready, verdict: concerns, О-1…О-4), guard: ок. Шаг завершён.
- В поле `signals` — строка сигналов без точки в конце: так её пишет `spec_audit.entry` (spec_audit.py:162); точка в миссии — конец предложения.

## Чего не хватило
- Нет помощника gitcmd для ls-remote с пределом lowSpeed — искал, где взять чтение головы с пределом.
