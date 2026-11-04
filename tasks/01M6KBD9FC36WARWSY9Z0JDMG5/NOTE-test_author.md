# Записка test_author — 01M6KBD9FC36WARWSY9Z0JDMG5

## Выяснено
- Раскладка: долгоживущие tests/test_01m6kbd9fc36warwsy9z0jdmg5_target_set.py (AC-1, 3–7, 9–11) и tests/test_01m6kbd9fc36warwsy9z0jdmg5_doctor_failure_errors.py (AC-8); AC-2 — планка acceptance_tests/test_ac2_backup_same_second.py (разовый): SPEC требует подмены закрытого шва projects._backup_stamp, долгоживущему файлу patch закрытых имён запрещён.
- Команда в тестах зовётся через artel.main() с подменённым sys.argv (образец — tests/test_01m5scgsqn0at0b07h7m9803ra_targets_migrate.py); journal — строки steps с action='target-set'; копии — config.LOGS/targets-*.yaml.
- AC-8: строка ищется по имени в doctor.all_checks; место «сразу после строк проектов» проверено так: у двух записей одной формы блоки одной длины, строка — через длину блока после project-support-<последний>.
- Записи с единственным компонентом нужен long_lived (иначе merge_local отказывает) — в фикстурах учтено.
- Тесты провалидированы временным стабом (projects.cmd_target_set + _backup_stamp, строка в doctor/cli.all_checks): все 43 зелёные; стаб снят git checkout, рабочая копия — только два новых файла tests/.
- До реализации 16 отказных параметризаций зелены (неизвестная команда тоже отказ) — оговорено в докстринге модуля.
- preflight: все проверки пройдены.

## Не сработало
- ls/cat и heredoc в Bash отклоняются — Read/Write и временный файл, убранный task-rm.

## Где остановился
- Готово к сдаче. docs/codebase-map.md не регенерировал: правка вне tests/ test_author откатывается — карту обновит разработчик.

## Чего не хватило
- Имени функции doctor-строки и функции команды SPEC не называет — тесты держатся только публичных входов (artel.main, doctor.all_checks).
