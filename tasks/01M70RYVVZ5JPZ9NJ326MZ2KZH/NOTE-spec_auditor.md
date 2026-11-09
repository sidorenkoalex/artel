# Записка spec_auditor (аудит 2, spec_sha 150eb7c9)

## Выяснено
- Факты SPEC о коде сходятся: orphans.py:62-83/74/76-77/115-117, hung_test_watchdog.py:68-81/172-183, __init__.py:155-158 и 175-181 (реэкспорт `_process_cwd` на :177).
- orphans.py:75 зовёт `doctor._process_cwd` (имя фасада, связано при импорте): подмена `hung_test_watchdog._process_cwd` его не достанет. Канал подмены в AC-2 не назван.
- check_hung_test_runs (hung_test_watchdog.py:221) пишет алерт в БД — AC-5 «малый» держится только при подмене alerts/БД.
- Опыт (Python 3.13.12): подмена `os.readlink` глобально, бросающая OSError, ломает `Path.resolve()` — `/var/folders` не раскрывается в `/private/var/folders`.
- В PATH роли нет lsof и ps (`which -a lsof` — не найден).
- tests/test_report_outcome_module.py:1137-1155 подменяет lsof выдуманными pid 400k–900k; на Linux новый путь через /proc читается первым — сбой только при совпадении pid с реальным процессом.
- Вердикт: concerns, В1–В5.

## Не сработало
- Составные команды bash с `cd`/`|`/`$` песочница отклоняет — только одиночные вызовы.

## Где остановился
- SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Ничего существенного.
