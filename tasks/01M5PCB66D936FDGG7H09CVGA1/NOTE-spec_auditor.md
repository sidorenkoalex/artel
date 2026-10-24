# Записка spec_auditor

## Выяснено
- Счёт строк/«Ловит мутацию»/импортов SPEC сходится с кодом (2271 строка, 71 строка, test_green/test_seed_always_red — строки засева).
- mutation-run: весь прогон команды (контроль + все патчи) в пределе full_suite_limit = 900 с (config.FULL_SUITE_TIMEOUT_SEC) — «после» почти наверняка тоже частями, а SPEC разрешает части только для «до».
- classify: KILLED при любом FAILED; ошибка фикстуры pytest = ERROR → «ошибка сбора…», но подготовка в теле функции/помощнике = FAILED.
- tests/ и codebase-map — COMMON_ZONES, замок зон с волной 1а не конфликтует.

## Не сработало
- `ls` в шелле шага недоступен; `$VAR` в командах Bash отклоняется — писать пути буквально.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns, 6 отклонений (главные: части --patches для «после»; убийство подготовкой «после»; патч не обязан реализовать мутацию строки). guard — ок.

## Чего не хватило
- Предел mutation-run на всю команду (900 с) искал по коду: mutation_run.py:512 → project_profile.full_suite_limit → config.py:223.
