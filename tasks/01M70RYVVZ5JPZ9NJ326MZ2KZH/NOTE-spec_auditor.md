# Записка spec_auditor

## Выяснено
- orphans.py:74 берёт `/usr/sbin/lsof` по абсолютному пути, если он есть (на этой машине Darwin есть) — подмена `lsof` в PATH песочницы до `_live_suite_run_in` на macOS не доходит; AC-1/AC-2 в форме ТЗ на macOS не собираются.
- hung_test_watchdog.py:179 зовёт `_temp_owner_alive` → orphans.py:117 `_live_suite_run_in`: новое «защищено при неизвестном cwd» меняет и сторожа (зависший pytest в базе без маркера перестаёт быть находкой) — в SPEC не названо.
- Существующие тесты: tests/test_canary_doctor_owner.py:26 (run.json с os.getpid()), test_ac6/ac7/ac10 канарейки — по коду не ломаются при наличии /proc или lsof.
- docs/codebase-map.md в COMMON_ZONES (config.py:938).

## Не сработало
- ls /usr/sbin/lsof запрещён песочницей; `test -x` сработал.

## Где остановился
- Вердикт fail, SPEC-AUDIT.md записан.

## Чего не хватило
- Ничего существенного.
