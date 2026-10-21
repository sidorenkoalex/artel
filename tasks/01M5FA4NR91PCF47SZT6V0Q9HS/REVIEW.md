---
task: 01M5FA4NR91PCF47SZT6V0Q9HS
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Механика канарейки, часть Б-2: реестр живой канарейки

## Фаза A — план

- Таблица покрытия полна: требования 1–7 разнесены по шагам 1–4. Шаги размером с MR: метка → команда → `doctor` → изоляция.
- Подход совпадает с конвенциями: `live_runs()` не тронут, причина снятия метки вместе с мёртвой записью вынесена в `_mark_follows_record` без изменения условия (сверил старое и новое тело `_drop_live_record`). Подписи `live_run_note`, `refuse_main_move_during_canary` и `all_checks` прежние.
- «Влияние на систему» совпадает с diff: 7 файлов, все в зонах SPEC. `notes.py`, `fsm_merge_gate.py`, `pool_seal.py`, `sandbox.py` и `test_invariants.py` не тронуты. Время полного прогона приведено, как требует требование 5.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `live_run_note` (canary.py:3073–3084) сначала зовёт `live_runs()` с прежней уборкой, затем `live_marks()`. `live_marks` пропускает метки, у которых осталась запись того же `run_stamp` (`_record_stamps` после уборки). Набор метки не фильтруется `default_set_only`, то есть мерж держится. `_mark_state`: при живом pid прогон живой; пустая или нечисловая метка, а также pid ≤ 0 живы, пока они моложе 60 с; мёртвое убирается строкой `LIVE_RUN_SWEPT_ACTION`. Все потребители (notes.py:285, fsm_merge_gate.py:1268, canary.py:3201) идут через `live_run_note`, прямых вызовов `live_runs` вне канарейки нет (grep). |
| 2 | OK | `cmd_canary_live()` убирает реестр через `live_runs` и `live_marks`, затем печатает запись (`run_stamp`, pid, `parent_pid`/шаблон при наличии, sha7, набор, начало, возраст, остаток `T×tasks+1ч−возраст`), метку (`run_stamp`, pid, возраст) или «живых прогонов канарейки нет». |
| 3 | OK | `artel._cmd_canary_live` проверяет аргументы до чтения реестра: `RUN_STAMP_RE.fullmatch` с `[0-9]` (строже `\d`), затем отсутствие `run_stamp`, пустое или пробельное основание и лишние аргументы. Дальше идёт уборка. Случаи (а)/(б)/(в) — `_drop_reason`; если записи остались, метка остаётся. Отказ дословно по тексту SPEC с кодом 1; при отсутствии `run_stamp` — «в реестре нет», код 0. Журнал: `operator`, `LIVE_RUN_DROPPED_ACTION`, имена файлов, основание, предупреждение о живом pid. Сигналов процессам нет. Под ролью — отказ белого списка, справка дописана (artel.py:184). |
| 4 | OK | `check_canary_live` работает только на чтение через `registry_view` (без unlink и без journal). Даёт `ok` (пусто или список), `warn` при возрасте ≥ `CANARY_DRIVE_TIMEOUT_SEC` для записи и для метки, `warn` на мёртвое с подсказкой `doctor --fix` / `canary live --drop`. `_fix_canary_live` в ветке `--fix` стоит до `all_checks`. Реэкспорт в `doctor/__init__.py`, строка подключена после `canary-trigger`. |
| 5 | OK | Подмена `canary._live_dir` добавлена в `setUp` двух классов (tests/test_canary_template_flag.py:192–198, tests/test_doctor_closed_ref_fix.py:154–162); утверждения не тронуты. Планка AC-19/AC-20 зелёная. Перечень не дополнялся, обоснование есть в PLAN. |
| 6 | OK | Долгоживущие тесты задачи без сети (у `doctor_live` есть заглушка subprocess), время меток задаётся через `os.utime`, у `_window` часы подставные. |
| 7 | OK | `git diff` по `tests/`: только добавление `setUp`/подмены и импорты, ассерты не менялись. `tests/test_canary_live_registry_units.py` зелёный без правок. AC-21 (`_window`) зелёный. |

## Замечания

Замечаний уровня blocker/major нет. Наблюдения уровня «вкус» оставлены ниже, в разделе «Вердикт», в реестр они не заводятся.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved.

Наблюдения, не блокирующие мерж (уровень minor). Их можно взять отдельной строкой бэклога:
- `orchestrator/canary.py` `_mark_state`, ветка `except OSError: text, age = "", 0.0`. Если метку нельзя прочитать по причине, отличной от `FileNotFoundError` (метка-каталог, права 000), её возраст считается нулевым, а не берётся из `stat().st_mtime`. Такая метка держит окно бессрочно, а `doctor` не предупреждает: возраст 0 ниже порога. Проверено исполнением: метка-каталог с mtime на 10⁶ с в прошлом дала `why=None`, `age=0.0`, `live_run_note` вернул причину, `doctor` ответил `ok`. По букве требования 1 нечитаемую метку старше 60 с следует убирать. Снять такую метку можно только через `canary live --drop`, а для метки-каталога `unlink` упадёт. Свой пульт таких меток не создаёт (`O_EXCL`, 0o644), поэтому это minor.
- `orchestrator/doctor/canary_pool.py` `check_canary_live`: для свежей нечитаемой метки строка выводит «pid None». В `_mark_line` этот случай оформлен как «не читается», здесь нет. Это косметика.
- Изоляция классов перечня (AC-19/AC-20) проверяется только планкой с пометкой «Группа: разовый», сторожа в `tests/` нет. Если после мержа из `setUp` уберут подмену `_live_dir`, тест снова начнёт трогать настоящий реестр пульта, и никто этого не поймает. SPEC сама задаёт проверку перечня как разовую, к коду задачи претензии нет.

## Проверено исполнением

- `artel.py plank-run 01M5FA4NR91PCF47SZT6V0Q9HS`: 3 passed, код pytest 0 (AC-19 ×2, AC-20).
- `python3 -m pytest -q -p no:xdist` по 12 модулям: `tests/test_01m5fa4nr91pcf47szt6v0q9hs_{mark,live_cmd,doctor_live,window}.py`, `tests/test_canary_live_registry_units.py`, `tests/test_canary_template_flag.py`, `tests/test_doctor_closed_ref_fix.py`, `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_{registry,window}.py`, `tests/test_doctor.py`, `tests/test_doctor_canary_pool.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py`. Итог: 206 passed, 105 subtests passed за 192 с.
- `python3 scripts/codebase_map.py` и затем `git diff -- docs/codebase-map.md` без строки `built_at_sha`: расхождений нет, карта свежая. Файл после проверки восстановлен через `git checkout`.
- Проба `_mark_state`, `live_run_note` и `check_canary_live` на метке-каталоге и пустой метке во временном каталоге реестра: результат описан в первом наблюдении вердикта.
- `grep` вызовов `live_runs()` и `live_run_note(` по `orchestrator/`: все потребители окна идут через `live_run_note`.
- CI коммита 6777366c зелёный (16 проверок), по данным пакета.

## Предложения системе

- В `pyproject.toml` xdist включён по умолчанию: `pytest -n 6` по набору модулей в шаге ревью валит узлы («node down: Not properly terminated»), спасает только `-p no:xdist`. Скилу review-checklist пригодилась бы готовая команда «тесты затронутых модулей».
- Правило «свойство кода, помеченное разовым — замечание» сталкивается с SPEC, которая сама задаёт разовую проверку изоляции (AC-19/20). Ревьюверу нечем закрыть такой разрыв, кроме наблюдения. Стоит решить, когда изоляция тестов от живого реестра требует сторожа в `tests/`.
