---
task: 01M6JJ4J4NBV2Y1Q4XHE3C3FVT
type: review
author_role: reviewer
status: approved
iteration: 3
schema_version: 5
---

# REVIEW: Граница git для ролей — отказ git clean и git в репозитории пульта, команда удаления файла задачи

## Фаза A — план
- Таблица покрытия полна (требования 1–10). Шаг 10 закрывает возврат с гейта мержа по ANSWER-1. Пункт 1: `real_git` обходит обёртки любой копии пульта. Пункт 2: в PATH роли попадает каталог настоящего git, а не чужого `role_bin`. Пункт 4: тест двух обёрток со счётчиком запусков git. Переменной вложенного вызова нет, как требует ANSWER-1 (отмена п. 3).
- «Влияние на систему» сходится с diff: `orchestrator/role_git.py`, `orchestrator/role_bin/git` (комментарий-маркер), `orchestrator/runner.py`, `tests/test_role_git.py`. Все файлы в зонах SPEC, существующие тесты не тронуты. В инкремент вошли и правки итерации 2 (`option_config`, `_alias_refusal`, дедупликация в `task_files.py`) — они уже приняты в R1-F1/R1-F3.
- В «Рисках» честно записано расхождение с долгоживущим `test_ac16_…` (см. «Замечания»).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений. AC-1 зелёный в планке |
| 2 | OK | Без изменений в классификации путей |
| 3 | OK | Без изменений с итерации 2 |
| 4 | OK | Без изменений |
| 5 | OK | Переменной-выключателя по-прежнему нет. `is_role_wrapper` влияет только на выбор настоящего git, разбор вызова не пропускается (ANSWER-1) |
| 6 | OK | `runner.py:1015-1019`: если `which("git")` — обёртка, git берётся через `role_git.real_git`. Второй элемент PATH роли — своя обёртка, и других обёрток в PATH нет (`RoleEnvForeignWrapperTest`). При двух обёртках на PATH вызов завершается, настоящий git запускается 1–3 раза (`TwoWrappersTest`, ANSWER-1) |
| 7 | OK | `DoctorBoundaryTest.env` теперь собирает PATH без обёрток любой копии — тест не зависит от окружения процесса |
| 8 | OK | Без изменений |
| 9 | OK | Без изменений |
| 10 | OK | Каталог обёртки в PATH по-прежнему `ROLE_GIT_BIN` от `__file__` модуля runner |

## Замечания
Новых замечаний к коду нет.

Наблюдение для Оператора (не дефект кода, в реестр не идёт; разработчику исправить нечем — файл под локом). Долгоживущий `tests/test_01m6jj4j4nbv2y1q4xhe3c3fvt_role_git_boundary.py::test_ac16_wrapper_dir_second_in_role_path_before_git` красный, если на PATH процесса pytest первой стоит обёртка другой копии пульта. Я это воспроизвёл: claude и codex — 2 failed. Причина в помощнике `_real_git`: он пропускает только каталог обёртки рабочей копии и отдаёт каталог чужого `role_bin`. А `role_env`, как и требует ANSWER-1 п. 2, этот каталог в PATH роли не кладёт. После мержа так будет при каждом прямом `pytest` этого файла ролью из рабочей копии: на PATH роли стоит обёртка главной копии. В CI, `suite-run` и `plank-run` тест зелёный. Класс тот же, что у принятого пропуска `Ac7WrapperMachineTest` (матрица неослабления). Чтобы роли не принимали красный тест за регрессию, нужна правка через `amend-tests`: `_real_git` должен пропускать любой `git`, для которого `role_git.is_role_wrapper` истинно. Предложение разработчика в «Рисках» PLAN верное.

## Реестр замечаний
Все записи прошлых итераций (R1-F1..R1-F3) — `accepted` в итерации 2. Новых записей нет.

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M6JJ4J4NBV2Y1Q4XHE3C3FVT`: 119 passed, код выхода pytest 0.
- `python3 -m pytest -p no:cacheprovider -q tests/test_role_git.py tests/test_01m6jj4j4nbv2y1q4xhe3c3fvt_role_git_boundary.py tests/test_multitarget.py tests/test_providers.py tests/test_codex_login_shell_path.py tests/test_runner_role_environment.py`: 117 passed, 25 subtests passed.
- Временные мутации. Скрипт лежал в каталоге документов и удалён; правки возвращены в `finally`, `git status --short` после прогона пуст:
  - `real_git` в старом виде (пропускает только свою обёртку) — `TwoWrappersTest`: 1 failed за 10.2 с, то есть снят таймаутом;
  - фильтр обёртки в `runner._resolve_declared_tools` выключен — `RoleEnvForeignWrapperTest`: 1 failed;
  - проверка маркера в `is_role_wrapper` выключена — `tests/test_role_git.py`: 23 passed. Это ожидаемо: копии в тестах несут `role_git.py`, и признак держит первая ветка. Ветку «только маркер» отдельный тест не держит; заявки на неё нет, поэтому это не замечание.
- Сценарий возврата: копия пакета обёртки во временном каталоге стоит первой на PATH процесса pytest:
  - `tests/test_multitarget.py`: 51 passed, 14 subtests, без зависания;
  - `tests/test_role_git.py`: 23 passed;
  - долгоживущий файл задачи: 2 failed (`test_ac16_…[claude|codex]`), см. «Замечания».
- `grep` по `orchestrator`/`scripts`: другие вызовы `real_git`/`is_role_wrapper` — только `role_git.py:342` (старая сигнатура совместима, `path_value` по умолчанию берётся из окружения).
- `python3 scripts/codebase_map.py`: карта отличается только строкой `built_at_sha`. Моя регенерация отменена (`git checkout -- docs/codebase-map.md`).

## Предложения системе
- Долгоживущий тест задачи с помощником «найти настоящий git по PATH процесса» зависит от того, из какой копии пульта собрано окружение. Когда механизм ставит на PATH обёртку с копией в каждой рабочей копии, test_author стоит писать такие помощники через функцию самого механизма (`role_git.is_role_wrapper`), а не через сравнение с одним каталогом. Кандидат в `skills/test-authoring.md` (класс «тест окружения роли, зависящий от копии пульта»).
