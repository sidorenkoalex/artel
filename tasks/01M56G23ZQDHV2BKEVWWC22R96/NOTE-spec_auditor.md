# Записка spec_auditor

## Выяснено
- Аудит 2 (spec_sha 6ff22eff…): решения гейта (1)–(6) в SPEC отражены, ссылки на код подтверждены.
- Главная находка: требование 8 и AC-7 пишут `<long_lived_dir>/<long_lived_prefix(id)>`, а prefix уже содержит каталог (scripts/guard.py:2959-2967; tests/test_01m551w0…_profile_mission.py:180). Так каталог удваивается.
- plan_appendix_errors в самостоятельном guard сверяет с PROTECTED_PATHS артели (guard.py:380-388), а не с перечнем проекта.
- run_plank с pytest-own сам переводит пути от корня к workdir (acceptance.py:1114, _own_target :193-202).
- Вердикт: concerns (AC-7 серьёзно; путь-метка и отсутствующий долгоживущий файл — мелко).

## Не сработало
- `ls` в Bash недоступен; пайпы с `cd` требуют подтверждения.

## Где остановился
- SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Нигде не сказано явно, что `long_lived_prefix` включает каталог: это видно только из тела guard.long_lived_path_prefix.
