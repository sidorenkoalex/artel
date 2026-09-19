---
task: 01M2XFSNVGWA2VX5XFEYR93Y4Z
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Гейт зон при выданном мандате без раздела PLAN: auto запускает developer вместо остановки

## Фаза A: гейт плана

- Таблица покрытия PLAN полна: требования 1-7 SPEC разложены по шагам
  1-5, каждое требование имеет шаг кода и шаг тестов.
- Шаги — единицы размера MR (три файла кода, три файла тестов, карта);
  не микрооперации и не «сделать всё».
- Подход не конфликтует с архитектурой: `brief.py`/`fsm_advance.py`/
  `store.py` не тронуты (SPEC «Не входит»), константа действия
  импортируется по уже существующей цепочке `auto -> fsm -> fsm_advance
  -> advance_gates.zones`, копия перечня `ROLE_NOT_FINISHED_REFUSAL_ACTIONS`
  в `brief.py` намеренно не расширена (иначе AC-4 сломался бы).
- Расхождение SPEC «переход `in_dev -> review`» с фактическим
  `in_dev -> verifying` (ADR-0015) в PLAN названо явно; планка задачи
  моделирует свою мини-FSM, юнит-тест проверяет реальный `verifying` —
  замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (гейт зон различает причину: мандат покрывает все пути вне зон, раздел PLAN отсутствует/не совпадает — отдельное действие, пути мандата в тексте, подсказка «оформи раздел PLAN») | OK | `orchestrator/advance_gates/zones.py:25-26` константа, `:295-309` ветка: покрытие тем же `_touches_zone`, что у исключения AC-3; `detail` несёт `«Расширение зон разрешено: <пути мандата>»` и причину («отсутствует» / «не совпадает с мандатом (в разделе: …)»), `hint` — «оформи раздел … строка «Пути: …»». Покрыто `tests/test_zones_gate.py::ZonesGateMandateWithoutPlanSectionTest` (отсутствует / не совпадает / префикс директории / `zones_extension` не тронут). |
| 2 (текст и имя отказа без мандата не меняются) | OK | Прежний `detail` (`zones.py:286-288`) и `hint` (`:311-314`) не правлены, новая ветка вставлена между ними и срабатывает только при непустом мандате, покрывающем ВСЕ `out_of_zone` (`all`, не `any`). Байт-в-байт проверяют `test_no_mandate_keeps_the_old_refusal_byte_for_byte` и `test_mandate_covering_only_part_of_the_paths_keeps_the_old_refusal` против захардкоженных строк. |
| 3 (`_pre_advance_step`: новое действие в `in_dev` — класс «роль ещё не закончила», история в бриф, стоп-кран не бьёт) | OK | `orchestrator/auto.py:826-835`: `mandate_without_plan` исключён из `other_class_refusal`, `cycle.prev_refusal` на нём не выставляется, возвращается `None`. Бриф: `store.refusal_history` отбирает по префиксу «переход отклонён» (`store.py:333,363`), `brief.advance_refusal_history` вычитает только два литерала `_ROLE_NOT_FINISHED_REFUSAL_ACTIONS` (`brief.py:66-69,687-688`) — новое действие попадает в блок без правки `brief.py` (дифф `brief.py` пуст, проверено `git diff --stat`). Интеграционный тест `test_incident_runs_one_developer_step_with_mandate_paths_in_the_brief` перехватывает текст `advance_refusal_history` изнутри шага и находит в нём действие и путь мандата. |
| 4 (отказ без мандата в `in_dev` — как сегодня, два одинаковых дают `Stop`) | OK | Ветка `other_class_refusal == cycle.prev_refusal` (`auto.py:836-841`) не тронута; исключение — сравнение по полному тексту константы, не по префиксу «гейт зон» (`test_other_in_dev_refusal_still_stops_on_the_second_repeat`, `test_without_a_mandate_stops_without_running_the_role`). |
| 5 (защита от кружения: повтор после шага developer — `Stop`, роль получает ровно один шаг) | OK | `_role_step_between_repeated_refusals` (`auto.py:688-711`) идёт по журналу до `journaled_before` назад до предыдущего такого же отказа, граница визита — `state -> …`. Проверил вручную, что между шагами роли нет пост-шагового advance (`_cmd_auto` `auto.py:1030-1039`, `_role_run_step` `:939-943`, в `runner.py` `cmd_advance` не зовётся) — значит после шага роли следующий отказ того же действия в журнале всегда идёт через запись `agent run finished`, и помощник отличает «шаг был» от «шага не было». Стоп-текст тот же, что у T038. |
| 6 (`zones-extend` называет `artel.py auto <id>`) | OK | `orchestrator/answer.py:230-235`, только в ветке «раздел не совпадает»; `zones_extension` и журнальная запись прежние (`test_plan_without_section_names_auto_as_the_next_command`, контрольный `test_matching_plan_section_does_not_print_the_auto_hint`). |
| 7 (тесты сценария инцидента и соседних веток; названные наборы зелёные) | OK | AC-8 воспроизведён настоящим `fsm.cmd_advance` с мандатом на диске (`AutoRunsDeveloperOnMandateWithoutPlanSectionTest`: один шаг developer, 2 записи нового действия, `verifying` после оформленного раздела, `Stop` после шага без раздела, `Stop` без мандата без единого шага). AC-9 — прогон ниже. |

Дополнительно по чек-листу:
- **Тесты**: у каждого нового теста есть заявка «Ловит мутацию: …», и
  заявленная мутация правдоподобна (перенос чтения мандата внутрь ветки
  `extension_paths`, `any` вместо `all`, равенство строк вместо префикса,
  проверка «шаг с входа в состояние» вместо «шаг между отказами»,
  исключение по префиксу «гейт зон» и т.д.); докстринги описывают
  сценарий и наблюдаемое свойство. Дифф `tests/` не содержит удалённых
  или изменённых ассертов — единственные минус-строки это перестановка
  импортов в `tests/test_auto_cycle.py:26-28`.
- **Системная целостность**: `tasks/`, `skills/`, `templates/`,
  `gates.yaml`, `roles.yaml`, `.github/`, `brief.py`, `fsm_advance.py`,
  `store.py` не тронуты (пустой `git diff --stat` по этим путям).
  Гейт зон не ослаблен: без совпадающего раздела PLAN переход по-прежнему
  ОТКАЗЫВАЕТ, `zones_extension` пишется только в прежней ветке AC-3
  (`test_named_refusal_leaves_zones_extension_untouched`). Безусловный
  отказ защищённого пути стоит выше новой ветки и не тронут. Планка
  приёмки без пометок `manual|skip` (grep по `acceptance_tests/`).
  Секция PLAN «Влияние на систему» совпадает с фактическим диффом.
  Откат — revert одного merge-коммита, схема БД не менялась.
- **Безопасность**: новых источников недоверенного ввода нет, мандат
  разбирается по тому же префиксу и с той же защитой от автокоммита роли
  (`_answer_commit_is_role_step_autocommit`), что и раньше.
- **Простота**: помощник из восьми строк, без новых абстракций.
- **Карта**: `docs/codebase-map.md` регенерирована тем же коммитом;
  перегенерация в ревью даёт нулевой дифф без строки `built_at_sha`.

## Замечания

(замечаний нет)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved.

Наблюдение без замечания (в реестр не заношу — не дефект относительно
SPEC, решение о желательности за Оператором): защита от кружения
считает «гарантированный шаг» от БЛИЖАЙШЕГО предыдущего отказа того же
действия, поэтому после `Stop` повторный `artel.py auto <id>` без
правок даёт developer ещё один шаг (журнал `R1, шаг, R2, auto старт,
R3` — помощник упирается в `R2` с `seen_role_step=False`). До задачи
перезапуск стоил ноль шагов роли (два отказа и `Stop`), теперь — один
шаг developer за каждый перезапуск. Это согласуется с семантикой
стоп-крана T038 «на вызов», и повторный шаг роли — как раз то, за чем
Оператор перезапускает цикл; если Оператор хочет строгого «один шаг на
визит состояния», помощнику достаточно продолжать обход за предыдущий
отказ, пока не встретится шаг роли или граница `state ->`.

## Проверено исполнением

- `python3 -m pytest tasks/01M2XFSNVGWA2VX5XFEYR93Y4Z/acceptance_tests
  -p no:cacheprovider -q` — 17 passed (планка задачи, включая AC-9 с
  прогоном названных наборов).
- `python3 -m pytest tests/test_zones_gate.py tests/test_zones_approve.py
  tests/test_auto_cycle.py tests/test_answer.py
  tests/test_advance_refusal_history.py -p no:cacheprovider -q` —
  122 passed, 28 subtests passed.
- Перегенерация `scripts/codebase_map.py` во временную копию и сравнение
  с `docs/codebase-map.md` без строки `built_at_sha` — расхождений нет
  (файл в дереве восстановлен, рабочая копия чиста).
- `git diff 56b8e043...HEAD -- tests/ | grep '^-'` — минус-строки только
  в импортах `tests/test_auto_cycle.py`, ассерты не удалялись.
- `git diff 56b8e043...HEAD --stat -- tasks/ skills/ templates/
  gates.yaml roles.yaml .github/ orchestrator/brief.py
  orchestrator/fsm_advance.py orchestrator/store.py` — пусто.
- `grep -rn "AC-[0-9]*: *\(manual\|skip\)"` по планке — пусто.
- Чтение вне пакета (причина — проверить требование 5 и AC-4):
  `orchestrator/auto.py` (`_cmd_auto`, `_role_run_step`,
  `_pre_advance_step`), `orchestrator/runner.py` (grep `cmd_advance` —
  отсутствует), `orchestrator/store.py::refusal_history`,
  `orchestrator/brief.py::advance_refusal_history`,
  `orchestrator/advance_gates/_base.py` (отказ журналируется актором
  `fsm`, `_advance_refusal` его видит). SPEC/PLAN/TZ прочитаны с диска
  `tasks/<id>/`, потому что пакет их не включил (артефакты живут в
  артефактной ветке, не в кодовой).
- CI коммита ce7ffac8 зелёный (7 проверок, по описи пакета).

## Предложения системе

- Ревью-пакет показал «SPEC.md/PLAN.md не показан: файл не найден в
  ветке task/…», хотя артефакты штатно лежат в артефактной ветке
  `artifact/<id>` и уже материализованы в `tasks/<id>/` рабочего
  каталога (SPEC 01M1NKTF173WV5CPDZ1C3WW69K). Сборщику пакета
  (`orchestrator/context_package.py`/`review.py`) стоит читать SPEC/PLAN
  из артефактной ветки или с диска, иначе ревьювер каждый раз добирает
  их сам — класс «пакет отстал от механики артефактной ветки».
- Комментарий у `ROLE_NOT_FINISHED_REFUSAL_ACTIONS` в `auto.py`/`brief.py`
  обещает «те же значения в обоих местах», но с этой задачи смысл пар
  разошёлся («не бить стоп-краном» ≠ «не показывать роли») — PLAN это
  уже отметил; подтверждаю как отдельное наблюдение ревью.
