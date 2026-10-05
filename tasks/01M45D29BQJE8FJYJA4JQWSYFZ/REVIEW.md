---
task: 01M45D29BQJE8FJYJA4JQWSYFZ
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: new разбирает «Порядок: после …» ТЗ и заявляет merge_after до аналитика

## Фаза A: план

- Таблица покрытия PLAN полна: требования 1–11 привязаны к шагам; п. 7
  честно помечен «без нового кода» — колонка и есть заявленное значение,
  `answer` в `escalated` уже пишет её через `merge_after.rewrite`
  (AC-12 зелёный это подтверждает).
- Шаги — размера MR (три модуля кода + один файл тестов + приложения).
- Подход согласован с архитектурой: вся механика в
  `orchestrator/merge_after.py`, `catalog.cmd_new` и
  `fsm._approve_spec_gate` только вызывают её узлы; правила `check` не
  скопированы в `catalog.py` (требование 2) — добавлен keyword-only
  `target` и `task_id=None`.
- Защищённые пути не тронуты: правки `skills/spec-authoring.md` и
  `templates/SPEC.md` — приложениями к PLAN; `git apply --check` по ним
  подтверждён планкой (`test_ac15_plan_appendices.py` зелёный).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `merge_after._ORDER_LINE_RE` — `^Порядок:[ \t]+после(?!\w)` с `re.M`, хвост режется на «(»/«.», элементы — `guard.merge_after_items`, форма — через `check` (`guard.merge_after_form_errors`); повтор строки — отказ; «послезавтра»/отступ не заявляют (`tests/test_merge_after_declared.py`). |
| 2 | OK | `catalog.cmd_new`: разбор тем же рубежом, что `_tz_path_refusal`, до клона/id/ветки/строки БД; `target` вычислен раньше и передан явно; обе причины склеены в один `sys.exit` с «задача не заведена» (AC-6, AC-7). |
| 3 | OK | `merge_after.record_declared` после строки БД: колонка + журнал «merge_after заявлен Оператором» с полными id. |
| 4 | OK | `status_suffix`: «[мерж после: …]» в `spec_writing`/`spec_gate`, состояние из БД на каждый вызов; «[ждёт мержа:» и прочие состояния без изменений. `show_line` печатает в любом состоянии (AC-8). |
| 5 | OK | `spec_gate_declared_refusal` вызывается после `spec_gate_value` и до `update_task`; отказ через тот же журнал «approve отклонён», каналы снятия (мандат `artel.py answer`, эскалация аналитика) названы. |
| 6 | OK | Добавка принимается только при упоминании в разделе обоснования (словом целиком — полным id или элементом поля); журнал «merge_after: добавлено аналитиком» после записи колонки. |
| 7 | OK | Без нового кода; AC-12 (обе ветки, X и «нет») зелёные. |
| 8 | OK | Канарейка (`canary=True`) строку не разбирает; `spawn_subtask` не тронут; без заявленного — сверки нет (AC-13). Повторный приход на гейт после прохода — без сверки (`_declared_in_force` по журналу `state -> tests_writing`/`state -> in_dev`), чтобы не сломать существующий `test_ac14_show_lists_all_dependencies_with_states`. |
| 9 | OK | Первая строка docstring `merge_after.py` обновлена; карта свежа (регенерация даёт пустой дифф, см. ниже). |
| 10 | OK | Оба приложения в PLAN, правило «все без исключения», «снять может только Оператор», раздел «## Обоснование зависимостей мержа» — есть. |
| 11 | OK | Долгоживущие файлы задачи не правились; `tests/test_merge_after_declared.py` покрывает только углы, не повторяя их. |

## Замечания

Блокирующих и major-замечаний нет. Наблюдения без требования правки:

- (не замечание) `orchestrator/merge_after.py::_declared_in_force` читает
  признак «гейт SPEC пройден» из журнала переходов — задача, переведённая
  мимо `set_state`, будет сверяться повторно. Риск честно описан в PLAN
  («Риски»), штатного пути нет.
- (не замечание) Перечень строки кончается только на «(»/«.» и конце
  строки — хвост вида «после X — после мержа Y» даст отказ `new` формой
  элемента. Это буква SPEC п. 1, отказ громкий, не молчаливая потеря.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: замечаний в этой итерации не заведено.

## Вердикт

approved

## Проверено исполнением

- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M45D29BQJE8FJYJA4JQWSYFZ`
  — 4 passed (AC-14 карта, AC-15 приложения PLAN), код выхода 0.
- `python3 -m pytest -q` по затронутым модулям:
  `tests/test_01m45d29bqje8fjyja4jqwsyfz_*.py` (оба долгоживущих),
  `tests/test_merge_after_declared.py`, `tests/test_01m44ep0d47f498tee08mngbyt_*.py`,
  `test_merge_after.py`, `test_catalog_tz_path_check.py`,
  `test_catalog_tz_zones_parsing.py`, `test_zones_approve.py`,
  `test_fsm_spec_gate_path_check.py`, `test_fsm_spec_gate_reject.py`,
  `test_canary_drive.py`, `test_answer_mandate.py`,
  `test_catalog_spawn_subtask.py`, `test_catalog_status_log.py` —
  149 passed, 67 subtests passed.
- Временные мутации (код возвращён `git checkout`, `git status` чистый):
  - `_justified` подстрокой вместо слова + снят `_declared_in_force` →
    `tests/test_merge_after_declared.py`: 2 красных
    (`test_short_prefix_inside_other_id_is_not_justification`,
    `test_no_check_after_spec_gate_was_passed`) — заявки исполнимы.
  - вызов `spec_gate_declared_refusal` в `fsm._approve_spec_gate`
    отключён → `tests/test_01m45d29bqje8fjyja4jqwsyfz_spec_gate_declared.py`:
    5 красных (AC-9, AC-10×2, AC-11, AC-12 замена) — сторож после мержа
    работает.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`
  — расхождений нет (карта свежа), регенерация откачена.
- Проба CRLF: строка «Порядок: после <id>, <префикс>\r\n» разбирается в
  те же элементы без ошибок формы (`guard.merge_after_items` срезает `\r`).
- Сверка «тесты не ослаблены»: diff `tests/` — только новый файл
  `tests/test_merge_after_declared.py`, существующие методы не менялись.

## Предложения системе

- Признак «задача уже прошла гейт SPEC» выводится из журнала переходов
  (`merge_after._declared_in_force`) — тот же вопрос встанет у
  `catalog._record_preliminary_zones`; стоит один общий узел в `store`.
