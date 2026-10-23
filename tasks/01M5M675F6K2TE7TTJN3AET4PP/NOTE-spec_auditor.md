# Записка spec_auditor — 01M5M675F6K2TE7TTJN3AET4PP

## Выяснено
- Адреса SPEC подтверждены: cleanup.py:260/279/329/356, config.py:105–110, workspace.py:153, gitcmd.py:374, merged_remote_cleanup.py:113; функции prune.py по именам на месте.
- Мерж артели идёт в клоне (`repo_context.resolve` → `.artel/projects/artel/repo`, fsm_merge_gate.py:182). `refs/remotes/origin/main` главной копии обновляют только fetch в ROOT (doctor root_pin.py:53 через fetch_ref_sha с tracking_refs=True, pin.py:127). На момент cleanup_merged_remote он устаревший → merge-base --is-ancestor для только что влитой ветки почти всегда даст «не влита».
- Инвариант 40 (docs/invariants.md:70): «git главной копии меняют только pin-update/pin --to и doctor --fix»; тест (snapshot refs/heads, refs/artifacts, HEAD, worktree list) refs/remotes не видит — останется зелёным, но формулировка инварианта расходится с требованием 1.
- docs/retention.md:112 «prune этого вида не касается» — требование 6 должно это снять, SPEC этого не говорит.
- SpyRun на rev-parse refs/remotes/… отвечает 0 с пустым выводом (sandbox.py:1268, 1384) — правило «40 hex» нужно, факт ТЗ верен.
- Существующие тесты уборки после мержа совместимы: в MergedRemoteSandbox клон == корень, пуш удаления снимает ссылку → drop вернёт None.

## Не сработало
- Составные команды Bash (cd/; ) требуют подтверждения — только одиночные команды с абсолютными путями.

## Где остановился
- Вердикт concerns; SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Откуда в главной копии вообще появляются refs/remotes/origin/task/* сейчас (вероятно ручной git fetch Оператора) — в коде создателя не нашёл.
