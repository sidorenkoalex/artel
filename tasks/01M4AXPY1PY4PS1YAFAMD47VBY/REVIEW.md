---
task: 01M4AXPY1PY4PS1YAFAMD47VBY
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Оборванная канарейка не оставляет прогонов и клонов; канарейка отвязывается сама

## Гейт плана (фаза A)

Покрытие требований в таблице плана полное: 1–4, 5–6, 7–9 и 10 имеют отдельные проверяемые шаги. Шаги соразмерны MR и не конфликтуют с заявленной архитектурой. Влияние и откат описаны. Замечания ниже относятся к реализации и к неполному тестовому сторожу двух сценариев ownership.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Обработчик SIGTERM/SIGHUP прерывает ведение; существующие `finally` снимают группы и удаляют оба каталога. |
| 2 | OK | При сигнале записывается красная строка с именем сигнала и без нового `verdict`. |
| 3 | OK | `run.json` клона читается в `finally`, группа сохранённого pid снимается для штатного, ошибочного и сигнального выхода. |
| 4 | Не полностью | Маркеры пишутся, но marker origin не участвует в определении его живого владельца (R1-F2). |
| 5 | OK | Watchdog распознаёт временные каталоги и исключает их при живом владельце. |
| 6 | Не реализовано полностью | Живой произвольный `suite-run` защищает все временные базы, в том числе сироты (R1-F1); живой origin также может быть удалён (R1-F2). |
| 7 | OK | `--detach` создаёт новую сессию, лог и файл результата и сразу печатает их пути с pid. |
| 8 | OK | Справка называет `--detach` и штатность для сессии Оператора. |
| 9 | OK | В `docs/operator-session.md` добавлены оба требуемых правила. |
| 10 | Не полностью | Профильные тесты и заявки на мутации есть, но не сторожат сценарии R1-F1 и R1-F2. |

## Замечания

- major — orchestrator/doctor/orphans.py:58-91 — `_live_suite_run()` возвращает один глобальный bool: любой живой pid из любого `logs/suite-run/*/run.json` делает живым каждый `artel-suite-base-*` без маркера. Воспроизведение с двумя мёртвыми `artel-suite-base-*` и одним несвязанным `run.json` с pid текущего процесса дало `found=[]` вместо обоих каталогов. Поэтому `doctor --fix` систематически оставит сироты, пока идёт хотя бы один обычный suite-run, вопреки требованию 6. Связать живой прогон с конкретным holder (либо пользоваться его собственным маркером; legacy-связь должна сопоставлять именно этот каталог) и добавить тест: несвязанный живой прогон не защищает мёртвую базу.
- major — orchestrator/doctor/orphans.py:71-85; orchestrator/canary.py:1205-1208 — особая ветка для `artel-canary-origin-*` игнорирует собственный `.artel-canary-owner` и считает origin живым только после появления ссылки на него в `.git/config` клона. Между записью живого маркера и `git remote set-url`, а также при временной недоступности config, `doctor --fix` назовёт и удалит origin активной канарейки. Изолированно: `liveness.owner_alive(origin) == True`, но `_temp_owner_alive(origin) == False` и origin попадает в `_orphan_temp_dirs()`. Сначала проверять marker самого origin тем же способом, что и для клона; связь через remote оставить только как совместимый fallback, и добавить тест окна до `set-url`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/doctor/orphans.py:58-91 | Глобальный признак живого `suite-run` защищает все `artel-suite-base-*`, а не каталог конкретного прогона. | `doctor --fix` не удаляет сироты при любом несвязанном живом suite-run. | Связать run с конкретной базой или опираться на её marker; покрыть несвязанный живой run тестом. |
| R1-F2 | open | orchestrator/doctor/orphans.py:71-85; orchestrator/canary.py:1205-1208 | Проверка origin обходит его живой marker до появления remote-связи. | `doctor --fix` способен удалить origin активной канарейки. | Проверять marker origin первым и покрыть промежуток до `git remote set-url` тестом. |

## Вердикт

changes_requested: исправить R1-F1 и R1-F2, включая указанные сторожа регрессии.

## Проверено исполнением

- `python3 -m pytest tests/test_01m4axpy1py4ps1yafamd47vby_canary_detach.py tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py tests/test_canary_detach_result.py tests/test_canary_doctor_owner.py` — 15 passed за 48.53 с.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4AXPY1PY4PS1YAFAMD47VBY` — зафиксированная планка: 1 passed.
- Изолированная проверка `_orphan_temp_dirs()` с двумя мёртвыми базами и несвязанным живым `run.json` вернула `found=[]`; отдельная проверка origin с marker текущего pid вернула `_temp_owner_alive=False` и включила origin в сироты.

## Предложения системе

