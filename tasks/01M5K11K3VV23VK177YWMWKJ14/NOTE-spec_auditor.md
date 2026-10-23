# Записка spec_auditor — 01M5K11K3VV23VK177YWMWKJ14

## Выяснено
- Все ссылки SPEC на код сходятся (artel.py:172/:1801/:2181, cleanup.py:434/:447/:558/:583–591/:587, retro.py:619/:666/:671, snapshot.py:62).
- lease.run_locked (lease.py ~370) возвращает body(sid) — значение _cmd_kill дойдёт до cmd_kill; artel.main вызывает fn() без использования результата — True не меняет код выхода.
- Ловушка: tests/test_kill_live_cycle_refusal.py:156 и :167 — `kill.assert_called_once_with(self.TASK, confirmed=True/False)`. Диспетчер, всегда передающий `reason=None`, красит оба теста; правка запрещена требованием 8. Значит `reason=` передаётся только при наличии флага (как `_approve_during_canary_kwargs`, artel.py:1882). SPEC об этом молчит.
- Подсказка `artel.py kill <id> --reason "<текст>"`: не определено, подставляется ли id (и полный ли — диспетчер знает только префикс rest[0]).
- AC-10 проверяет только `\n`; `\r\n` -> один пробел, `\r` и обрезка краёв требованием 2 не покрыты AC.
- docs/codebase-map.md — в config.COMMON_ZONES (config.py:814), регенерация карты зон не требует.

## Не сработало
- `cd ...; grep` в Bash отклоняется правилом Read deny — использовать `git grep`/`git show HEAD:`.

## Где остановился
- Вердикт concerns, SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Поиск тестов, мокающих cmd_kill с точной сигнатурой (git grep "cmd_kill" tests) — ТЗ перечисляет только тесты детали «kill switch».
