# Записка analyst

## Выяснено
- Шаг 5 (второй возврат с spec_gate, 6 решений, в SPEC — «решение гейта 2.N»): все шесть внесены. Якоря сверены по worktree: doctor/cli.py:305-331 (починки безусловно), test_doctor_closed_ref_fix.py:152-195 (store.db→None, без песочницы), plank_helper.py:35-71 (git по путям машины), plank_layout.py:41-47, acceptance.py:1277-1301 и :2068, test_01m5n8…_plank_layout_names.py:331-373 (закрытые имена acceptance).
- 2.1 → треб. 14, AC-20 (conn=None — ничего); 2.2 → «Не входит» (_pult.py); 2.3 → треб. 2, AC-2 (отказ с именем `long_lived_dir`/`plank_layout`); 2.4 → треб. 17, AC-5 (канал — ответ `config` подменённого docker, сокет-файл песочницы); 2.5 → треб. 14, 15, AC-20, AC-21 (warn «Docker не отвечает» / fail с текстом вызова); 2.6 → треб. 3 (публичные помощники acceptance), 12, 17, AC-17/20/21.
- Константу предела назвал `runner.DOCKER_CALL_TIMEOUT_SEC` (10 с) — имя выбрано аналитиком, место — runner (зона части 2), config.py не трогается.

## Не сработало
- `cd … && …` в Bash отказывает (simple_expansion) — guard звать абсолютным путём без cd.

## Где остановился
- SPEC.md четвёртого варианта сдан (status: ready, 17 требований, AC-1…AC-22, деление 2 части $60+$30), guard ок.

## Чего не хватило
- Docker CLI в шаге — `config --format json`, `down -p` без файла опытом не проверены (аудитор проверил в своём шаге).
