---
task: 01M1THKRK8HPXA7Y2SRB0RFTN2
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: стоп-кран волны, часть 2 — пауза run/auto по открытому алерту и видимость

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (`run`/`auto` отказывают начать новый шаг при открытом алерте self, уже идущий шаг не трогают, `approve`/`reject`/`budget`/`status` не блокируются, причина в stdout вызова и в журнале) | OK | `runner._cmd_run` (runner.py:207-230) проверяет `wave_breaker_alerts_open` СТРОГО после паузы и до workspace/pre-flight/spawn — уже идущий шаг не задет (та же проверка не в цикле опроса). `approve`/`reject`/`budget`/`status` не зовут `_cmd_run` вовсе. Причина журналируется (`WAVE_BREAKER_REFUSAL_ACTION`) и уходит в `sys.exit` тем же приёмом, что и `pause.REFUSAL_ACTION` (уже принятый паттерн T070). AC-1 (оба теста, включая «алерт посреди шага не прерывает его») зелёные. |
| 2 (`alert-ack` снимает блокировку немедленно; повторное срабатывание после ack — новый алерт) | OK | Первая половина — `wave_breaker_alerts_open` читает `alerts.open_alerts` (живой, не кэшированный, запрос на каждый вызов `_cmd_run`) — `ack` меняет `ack_ts`, следующий `run` увидит пустой список. Вторая половина не тронута этой задачей (уже обеспечена дедупом `alerts.raise_alert` по неподтверждённым строкам) — верно не переписана заново, AC-3 подтверждает обе половины. |
| 3 (`doctor` — алерт стоп-крана первым пунктом, до остальных проверок) | OK | `doctor/cli.py::cmd_doctor` печатает блок стоп-крана первой инструкцией функции, до `restore`/`_orphan_artifact_branches`/`all_checks`. AC-4 (порядок) зелёный, включая тест «без алерта — без строки». |
| 4 (`status` — пометка у КАЖДОЙ задачи target self, пока алерт открыт) | OK | `catalog._wave_breaker_suffix` + один запрос `wave_breaker_alerts_open` до цикла по строкам (не по задаче) — пометка не зависит от того, какая именно задача вызвала срабатывание. AC-5 (в т.ч. «вторая, невиновная задача тоже помечена») зелёный. |
| 5 (блокирует/помечает только target self, внешний target не задет) | OK | И `runner._cmd_run` (сверка `target` задачи), и `wave_breaker_alerts_open` (фильтр по `target=config.DEFAULT_TARGET` со стороны алерта), и `catalog._wave_breaker_suffix` (та же сверка `target` задачи) — двойная сверка с обеих сторон. AC-7 (оба направления: чужой target не помечен в `status`, алерт чужого target не блокирует self) зелёный. |

## Замечания

Нет.

## Реестр замечаний

Пусто — итерация 1, замечаний не заведено.

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tests/test_runner_wave_breaker.py tests/test_catalog_wave_breaker_status.py tests/test_doctor_wave_breaker.py tests/test_auto_cycle.py tests/test_pause.py tests/test_pause_now.py tests/test_catalog_status_log.py tests/test_doctor.py tests/test_multitarget.py -q` — 269 passed, 45 subtests passed (модули из зоны/затронутые модули, включая планки пауз T070/T074, которые PLAN заявляет неослабленными).
- `python3 -m pytest tasks/01M1THKRK8HPXA7Y2SRB0RFTN2/acceptance_tests -q` — 14 passed (AC-1..AC-5, AC-7; AC-6 — легальный `skip`, обоснование в `test_manual_criteria.py` разбирает класс «ci-covered»: файлы вне зоны задачи, неослабление гарантирует принцип целостности, а не новый код).
- Диф `tests/` вручную сверен построчно (файл целиком в пакете ревью) — только новые тестовые файлы и добавление одного класса/импорта в `test_auto_cycle.py`; ни один существующий ассерт не удалён и не ослаблен.
- `python3 scripts/codebase_map.py` — сверка карты: diff от коммита ветки отличался только строкой `built_at_sha` (регенерация не нашла содержательных расхождений); откатил тестовую регенерацию (`git checkout -- docs/codebase-map.md`) — карта коммита ветки актуальна.
- Прочитаны исходники, затронутые diff'ом, для проверки логики размещения проверки (порядок относительно паузы/workspace/spawn в `runner.py`), отсутствия цикла импорта `catalog.py -> runner.py` и доступности `doctor.runner` через фасад пакета `orchestrator/doctor/__init__.py`.

## Предложения системе

Нет.
