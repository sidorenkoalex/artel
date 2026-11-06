---
task: 01M6PAJ61DP2R2CMM71PJ8W0KF
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Окружение роли и doctor для compose

## Фаза A — план
- Таблица покрытия полна: 12 (без кода), 13 (снято), 14, 15, 16, 17 — у каждого шаг или основание; шаг 4 итерации 2 закрывает R1-F1 и R1-F2, строка 17 теперь называет сторожа в `tests/`.
- «Подход» и код совпадают: `SIGKILL` группе → `proc.wait()` → пробы (`orchestrator/doctor/project_checks.py:481-503`).
- «Влияние на систему» соответствует diff итерации: `project_checks.py` (19 строк) и новый `tests/test_doctor_compose_stands.py`; вне зоны ничего.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 12 | OK | `runner.py`/`stack.py` не тронуты; AC-1 — планка и долгоживущий `test_…_role_env_compose.py` зелёные |
| 13 | — | снято решением №4.1 |
| 14 | OK | Ожидание исчезновения группы теперь действительное: опыт — проба видит `ProcessLookupError` с первой попытки (`{'gone': 1}`); прочее проверено в итерации 1 |
| 15 | OK | тот же общий `_docker_call` — исправление R1-F1 действует и здесь; тест исчерпания проб AC-3 зелёный |
| 16 | OK | `python3 scripts/codebase_map.py` меняет только `built_at_sha` |
| 17 | OK | долгоживущий сторож строки «забытые стенды» — `tests/test_doctor_compose_stands.py`; не повторяет долгоживущие файлы задачи (те — строка записи и `role_env`) |

## Замечания

Новых замечаний нет. Наблюдение (не дефект): `proc.wait()` в `_drop_group` без предела — конечен, потому что лидер группы только что получил `SIGKILL`; единственный теоретический случай бесконечного ожидания (`killpg` отказал по `EPERM` своему же ребёнку) нереален.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/doctor/project_checks.py:481-503 | пробы исчезновения группы шли до `proc.wait()` | ожидание вырождалось в прокрутку до исчерпания | принято: `_drop_group(proc)` — `SIGKILL` → `proc.wait()` → пробы, обе ветки `_docker_call` зовут её; опыт ревьювера на той же команде, что в итерации 1 (`sh -c 'sleep & exec sleep'`, timeout=1): исходы проб `{'gone': 1}` вместо `{'ok': 1, 'perm': 99999}`; тест исчерпания AC-3 (подменённый `killpg`) зелёный |
| R1-F2 | accepted | tests/test_doctor_compose_stands.py | у строки «забытые стенды» не было долгоживущего сторожа | регрессия после мержа не ловилась | принято: 4 теста через фасад `doctor` с заявками «Ловит мутацию»; временная мутация ревьювера (`"-v"` в argv `down`, `orphans.py:397`) красит `test_fix_takes_down_only_dead_stand_keeping_volumes`, код возвращён |

## Вердикт
approved

## Проверено исполнением
- `python3 …/artel.py plank-run 01M6PAJ61DP2R2CMM71PJ8W0KF` — 30 passed, код выхода 0.
- `python3 -m pytest -q -p no:cacheprovider tests/test_doctor_compose_stands.py tests/test_01m6paj61dp2r2cmm71pj8w0kf_compose_record_line.py tests/test_01m6paj61dp2r2cmm71pj8w0kf_role_env_compose.py tests/test_doctor.py tests/test_doctor_closed_ref_fix.py` — 149 passed, 3 subtests passed.
- Опыт к R1-F1: `doctor.project_checks._docker_call(["/bin/sh","-c","/bin/sleep 300 & exec /bin/sleep 300"], …, timeout=1)` с подсчётом исходов `os.killpg(g, 0)` — `(None, '', '')`, `{'gone': 1}`.
- Временная мутация к R1-F2: `"-v"` добавлен в argv `down` (`orchestrator/doctor/orphans.py:397`) — `tests/test_doctor_compose_stands.py`: 1 failed, 3 passed; правка возвращена, `git status` чистый.
- `python3 scripts/codebase_map.py` — разница только в `built_at_sha` (возвращена `git checkout`).

## Предложения системе
