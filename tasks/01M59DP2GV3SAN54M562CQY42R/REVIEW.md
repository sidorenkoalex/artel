---
task: 01M59DP2GV3SAN54M562CQY42R
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Метрика «круги до кода»: аудиты SPEC, возвраты и эскалации на задачу — в report и оповещение по порогу

## Фаза A — план
- Таблица покрытия PLAN полна: требования 1–10 привязаны к шагам 1–4.
- Шаги размера MR: config+rounds, report, auto, тесты+карта.
- Подход совпадает с архитектурой: подсчёт идёт по уже выбранному `_all_steps`, это одна выборка `store.all_steps` (`orchestrator/report.py:147`), нового запроса к `steps` нет. Журнал задачи в `auto` берётся через `store.task_steps`, стоимость — через `spend.known_cost_breakdown`. В текстах PLAN мелкое расхождение: шаг 4 обещает в `tests/test_rounds.py` «медиану/среднее чистой функцией, None разбора, raise_once напрямую», а файл проверяет target внешнего проекта и пустой блок. `None` разбора и однократность покрыты долгоживущими тестами (AC-3, AC-10), поэтому дыры в покрытии это не даёт и на вердикт не влияет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/rounds.py:43` `count`: аудиты по `state -> spec_audit`, возвраты по `spec_audit.RETURN_ACTION`, возвраты с гейта — `state -> spec_writing` с префиксом `brief.SPEC_GATE_RETURN_PREFIX`, эскалации, `review_iters`, `known_cost_breakdown(...)[0]`; при `None` событие пропускается; до планки — `analyst`/`spec_auditor` |
| 2 | OK | `report._rounds_html`: окно `_in_window(created_at)`, все столбцы на месте, возвраты в форме «аудита / с гейта» |
| 3 | OK | `class="rounds-hot"` по `rounds.over_threshold` |
| 4 | OK | Строка итога: `statistics.median` (обычная медиана), среднее, составные столбцы «X / Y» |
| 5 | OK | `_by_project(window)` + h3; признак разбивки тот же, что у `_metrics_html` (все задачи пульта) |
| 6 | OK | `auto._cmd_auto` теперь обёртка: `_auto_cycle` + `rounds.raise_once` на любом выходе цикла, плюс сверка после Advanced / verifying-опроса / шага роли. `raise_alert(conn, task_target, "warning", "rounds", текст)`; оповещение внимания не используется |
| 7 | OK | Признак — запись журнала `круги до кода: оповещение`, не открытое оповещение; AC-10 (ack + закрытие оповещений внимания) зелёный |
| 8 | OK | `config.ROUNDS_ALERT_SPEC_AUDITS=3`, `ROUNDS_ALERT_ESCALATIONS=2`; одна функция `over_threshold` для блока и для оповещения |
| 9 | OK | Секция добавлена последней, прежние не тронуты; diff `tests/` — только новый `tests/test_rounds.py`, прежние тесты не менялись |
| 10 | OK | Долгоживущий `tests/test_01m59dp2gv3san54m562cqy42r_rounds.py` (11 тестов) + `tests/test_rounds.py`; планка AC-12 зелёная |

Тесты: у обоих методов `tests/test_rounds.py` в докстринге есть «Ловит мутацию» с наблюдаемым расхождением. Свойства долгоживущего файла они не повторяют: долгоживущий проверяет только `DEFAULT_TARGET`, а `test_rounds.py` — внешний проект и пустое окно. Целостность: ни один тест, гейт или лимит не ослаблен. Вне зон изменён только `config.py`, это общая зона по требованию 8. «Влияние на систему» в PLAN совпадает с diff.

## Замечания

Замечаний уровня blocker/major/minor нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m59dp2gv3san54m562cqy42r_rounds.py tests/test_rounds.py tests/test_report.py tests/test_report_project_label.py tests/test_01m57pmbhwk5egq8hpa5tqx72h_report.py tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py tests/test_auto_cycle.py tests/test_stall_alerts.py` — 177 passed, 127 subtests passed.
- `artel.py plank-run 01M59DP2GV3SAN54M562CQY42R` — 1 passed (`test_ac12_old_report_and_alerts.py`), код выхода 0.
- Временная мутация: в `orchestrator/rounds.py:98` target `store.task_target(...)` заменён на `config.DEFAULT_TARGET`. `tests/test_rounds.py::test_alert_target_is_external_project_of_task` упал (1 failed), код возвращён `git checkout`. Заявку второго метода проверил чтением: без ветки «нет задач» `_rounds_html([], [])` уходит в `"".join` по пустому `_by_project` и возвращает пустую строку, тест краснеет на `assertIn("нет")`.
- `python3 scripts/codebase_map.py` → `git diff -- docs/codebase-map.md`: расхождений, кроме `built_at_sha`, нет — карта свежая. Изменения откатил.

## Предложения системе
- Песочница шага ревью отклоняет `sed -i` и подстановку процесса `<(...)`, поэтому временную мутацию приходится вносить через Edit. Стоит прямо назвать это в review-checklist (раздел «Сторож — проверен временной мутацией»).
