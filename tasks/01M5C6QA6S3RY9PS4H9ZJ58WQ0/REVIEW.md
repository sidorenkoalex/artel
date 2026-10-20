---
task: 01M5C6QA6S3RY9PS4H9ZJ58WQ0
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Механика канарейки, часть А — реестр живого прогона, окно тишины, мерж и обходы окна во время канарейки

## Фаза A — план
- Таблица покрытия полна: требования 1–11 разложены по шагам 1–4; шаги — единицы
  размера MR (реестр в `canary.py`; окно и обходы в `notes.py`/`pool_seal.py`;
  флаг и проверка мержа в `artel.py`/`fsm.py`/`fsm_merge_gate.py`; юнит-тесты).
- Подход не выходит из зон SPEC: нового модуля нет, `liveness.owner_alive`,
  `CANARY_OWNER_MARKER`, `doctor/stale_cycles.py`, `tests/sandbox.py` не тронуты
  (сверено по diff --stat). «Влияние на систему» совпадает с фактическим diff:
  8 файлов, сигнатуры расширены только необязательными параметрами.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `canary._live_run_record` (менеджер): запись `<run_stamp>-<pid>.json` в `config.ROOT/.artel/canary-live` (под `.gitignore` `.artel/`, ROOT в `ALL_CONFIG_ATTRS`), поля pid/process_start/run_stamp/sha/set_name/started_at/tasks; atomically через tmp+replace; снятие в `finally`, `_interrupt_on_signal` снаружи — сигнал тоже снимает. `cmd_canary` возвращает `run_stamp`, `on_run_stamp` зовётся до print и до первого клона. |
| 2 | OK | `live_runs`/`_live_verdict`: pid (`liveness._pid_alive`, `owner_alive` не тронута), потолок `CANARY_DRIVE_TIMEOUT_SEC × tasks + 3600`, старт с допуском `_LSTART_SPAN` того же модуля; `None` при сверке — живая; `None` при записи — только pid+возраст. Не живые убираются с меткой (метку чужого pid не трогают) и строкой журнала без задачи. |
| 3 | OK | Метка `<run_stamp>.lock` через `O_CREAT|O_EXCL` до записи; `FileExistsError` → «canary: прогон <run_stamp> уже идёт», чужие файлы не трогаются (исключение до входа в `try/finally`). |
| 4 | OK | `notes._silence_window_reason` — первая проверка `canary.live_run_note()` (любой набор). |
| 5 | OK | `fsm_merge_gate._refuse_during_canary` вызывается в `_cmd_approve_merge_gate` непосредственно перед `_push_merged_main` (после `_publish_merge_artifacts`, где уже есть `sys.exit`-отказы — путь уборки и снятия мьютекса прежний); текст отказа совпадает с требованием. |
| 6 | OK | `--during-canary` в `_approve_reason_indices`; пустое основание — отказ у `approve`/`pool-seal` (`artel._during_canary_arg`) и `note`/`doc-commit` (`notes._during_canary_or_refuse`); вне `merge_gate` — отказ в `fsm._cmd_approve` по образцу `--no-answer`; основание — строка журнала задачи. |
| 7 | OK | `repo_context.is_artel(ctx)` и `live_run_note(default_set_only=True)`. |
| 8 | OK | `canary.refuse_main_move_during_canary` в `note --now/--flush`, `doc-commit --flush`, `cmd_pool_seal`; с флагом — строка журнала пульта. |
| 9 | OK | `artel._cmd_canary`: отбор `row["run_stamp"] in stamps`, приёмник — `stamps.append`; на обрыве приёмник уже получил stamp. |
| 10 | OK | Без живого прогона `live_run_note()` → `None`, все проверки — ноль действий; первая строка вывода канарейки побайтно прежняя (сверил склейку f-строк); `pool-seal` без флага зовётся прежним вызовом без аргументов. |
| 11 | OK | Тесты детерминированы: готовность ребёнка — по каналу, часы подменены. |

## Замечания
Замечаний уровня blocker/major/minor нет.

Наблюдения без замечания (сценария с последствием не нашёл):
- `orchestrator/canary.py` `_live_run_record`: между `os.open(... O_EXCL)` и
  входом в `try` сигнал теоретически оставит метку без записи; `live_runs` такие
  метки не убирает. Последствие — лишь файл-сирота: `run_stamp` посекундный и не
  повторяется, окно метка не держит (читается только запись).
- `canary_drive` ведёт задачу с `config.ROOT` = клон (`orchestrator/canary_drive.py:15`),
  поэтому собственный мерж учебной задачи в клоне реестр пульта не видит и
  канарейка сама себя не держит — проверил, потому что `_refuse_during_canary`
  стоит на общем пути мержа.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: итерация 1 замечаний не завела.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py tests/test_canary_live_registry_units.py` — 24 passed, 54 subtests passed за 134 с.
- `artel.py plank-run 01M5C6QA6S3RY9PS4H9ZJ58WQ0` — отказ «планки нет: нет файлов test_*.py» (в `acceptance_tests/` только `long_lived.sha256.txt`; критерии держат долгоживущие файлы `tests/`, прогнанные выше).
- Временная мутация (код возвращён `git checkout`, `git status` чист): `_drop_live_record` снимает метку безусловно и `DURING_CANARY_FLAG` убран из `_approve_reason_indices` → `tests/test_canary_live_registry_units.py` — 2 failed (`test_mark_of_other_pid_kept_on_sweep`, `test_reason_is_not_taken_for_sha`): обе заявки «Ловит мутацию» исполнимы.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без строки `built_at_sha` — расхождений нет, карта свежая (изменение откатил).
- CI коммита 44132df9 — зелёный (из пакета).
- diff `tests/`: существующие тесты не тронуты, только новый `tests/test_canary_live_registry_units.py`; ассертов не удалено.

## Предложения системе
- `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py` идёт 125 с (порог 60 с): каждый подслучай AC-5/AC-13 поднимает дочернюю канарейку и полную песочницу мержа — класс «долгоживущий тест с реальными дочерними процессами на каждый subTest» стоит учесть в skills/test-authoring.md (одна живая канарейка на несколько проверок).
