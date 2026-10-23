# Записка spec_auditor — 01M5M675F6K2TE7TTJN3AET4PP (круг 2, SPEC b9fb2d38)

## Выяснено
- Адреса SPEC подтверждены: pin.py:123–156 (cmd_pin_update), gitcmd.py:162–188 (git без timeout), workspace.py:153–163 (registered_paths → [] при сбое), prune.py:240–282 (_print_report, _remove_dirs), retention.md:68–86, :108–113, :112.
- `_remove_dirs` (prune.py:279) печатает «  <метка> не удалён: <exc>»; требуемая SPEC строка «  каталог .artel/worktrees/<имя>: не удалён — <причина>» меткой не получается — нужна правка `_remove_dirs` (параметр формата) либо своя петля; SPEC запрещает дублирование и правку чего-либо кроме нового вида → противоречие (concerns).
- AC-3 ловит только уборку до проверки канарейки; уборка между канарейкой и CI / CI и merge проходит все AC.
- AC-4 не требует удаления каталога с именем ЗАКРЫТОЙ задачи (ТЗ: T001 — done) — мутация «защищать имя любой задачи» проходит.
- Существующие тесты pin-update (test_pin, wait_ci, stale_cycles, start_precision, main_ci) — assertIn/реальный git; новая строка вывода их не ломает.
- Песочница подменяет config.WORKTREES (sandbox.py:1754); docs/codebase-map.md — в COMMON_ZONES (config.py:814).

## Не сработало
- Составные Bash-команды и ls вне рабочих каталогов запрещены.

## Где остановился
- SPEC-AUDIT.md записан (status ready, verdict concerns: О-1 _remove_dirs/формат, О-2 AC-3 место уборки, О-3 имя закрытой задачи, О-4 два варианта сбоя, П-3 локаль [pruned], П-4 живой gitdir); guard ок.

## Чего не хватило
- Не проверил, переводится ли « * [pruned] %s» в локализованном git (каталоги локалей вне доступа).
