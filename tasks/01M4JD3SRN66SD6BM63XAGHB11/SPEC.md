---
task: 01M4JD3SRN66SD6BM63XAGHB11
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/advance_gates/acceptance.py, orchestrator/advance_gates/plan_appendix.py, orchestrator/appendix_tree.py, orchestrator/fsm_merge_gate.py, scripts/plan_appendix_ci.py, docs/codebase-map.md, tests/
budget_usd: 40
---

# SPEC: Приложения PLAN — рубеж in_dev → verifying и CI ветки по одному правилу

## Контекст
Рубеж `in_dev -> verifying` гоняет планку и долгоживущие файлы задачи в
рабочей копии без приложений PLAN
(`orchestrator/advance_gates/acceptance.py::_acceptance_run_body`:
`workspace.ensure`, `acceptance.plank_in_code_copy`, `acceptance.run`), тогда
как автогейт, approve и suite-run накладывают их через
`orchestrator/appendix_tree.py::suite_tree`. Из-за этого сторож свойства,
приезжающего приложением PLAN, на рубеже красен по построению (06.10, часть 2
этапа 3, 01M45FK56D: 3 эскалации и 2 решения Оператора на одном рубеже).
Признание «приложение уже в базе» (`git apply --reverse --check`) написано
трижды (`fsm_merge_gate._appendix_already_in_main`, вложенная `in_tree` в
`appendix_tree._prepared` — без записи в журнал,
`advance_gates/plan_appendix._appendix_already_in_base`), а в
`scripts/plan_appendix_ci.py` его нет вовсе: операторский коммит защищённого
файла вперёд кода валит CI ветки «не накладывается на дерево чекаута», хотя
приложение уже в базе (06.10).

## Требования

1. Рубеж `in_dev -> verifying` прогоняет планку и долгоживущие файлы задачи на
   дереве с наложенными приложениями PLAN — тем же узлом, что автогейт,
   approve и suite-run (`appendix_tree.suite_tree` или его общая часть).
2. Неприменимое приложение PLAN на рубеже `in_dev -> verifying` — именованный
   отказ перехода (номер приложения и его пути), как у узлов автогейта,
   approve и suite-run; прогона планки при этом нет.
3. Признание «приложение PLAN уже в базе» — одно правило для четырёх узлов:
   гейт мержа (`orchestrator/fsm_merge_gate.py`), дерево полного прогона
   (`orchestrator/appendix_tree.py`, в том числе на рубеже из требования 1),
   гейт применимости на выходе `in_dev`
   (`orchestrator/advance_gates/plan_appendix.py`) и CI ветки
   (`scripts/plan_appendix_ci.py`): приложение, которое не накладывается прямо,
   но обратная проверка (`git apply --reverse --check`) проходит, пропускается,
   а не отказывает.
4. Пропуск по требованию 3 сопровождается записью. У узлов пульта (гейт
   мержа, дерево полного прогона — в том числе на рубеже из требования 1,
   гейт применимости на выходе `in_dev`) это запись журнала задачи в
   нынешней форме гейта применимости: действие —
   `plan_appendix.PLAN_APPENDIX_ALREADY_IN_BASE_ACTION` («приложение PLAN уже
   в базе»), за ним `: ` и пути приложения через `, `; номер приложения — в
   подробностях записи вида «приложение N (<пути>)». Все узлы пульта пишут
   именно эту форму. У CI-скрипта — строка вывода с номером приложения и
   словами «уже в базе».
5. В узлах пульта признание реализовано одной общей функцией, где это
   возможно. `scripts/plan_appendix_ci.py` по-прежнему не импортирует модули
   пульта (пакет `orchestrator`) и повторяет то же правило у себя; совпадение
   ответов правила пульта и правила CI-скрипта проверяется тестом сверки.
6. Приложение, которое не накладывается ни прямо, ни обратно, — по-прежнему
   отказ во всех четырёх узлах требования 3 (ослабления нет).
7. Смена ожидания существующего тестового метода `tests/` допустима только
   перечнем раздела «Меняемое поведение» этого SPEC (инвариант 38); вне
   перечня ожидания существующих тестов не меняются.

## Критерии приёмки

AC-1. Задача с приложением PLAN к защищённому тесту, без которого её код
красен: рубеж `in_dev -> verifying` проходит (планка и долгоживущие файлы
зелёные на дереве с наложенным приложением); та же задача без наложения
приложения на рубеже (мутация) — рубеж красный.

AC-2. Приложение PLAN, не накладывающееся на дерево ветки ни прямо, ни
обратно: рубеж `in_dev -> verifying` отказывает переходу, отказ называет номер
приложения и его пути; планка не запускалась.

AC-3. Приложение PLAN, уже наложенное в базе (обратная проверка проходит,
прямая — нет): `scripts/plan_appendix_ci.py` на ветке задачи завершается кодом
0 и печатает строку с номером приложения и словами «уже в базе».

AC-4. То же уже наложенное приложение: рубеж `in_dev -> verifying` (гейт
применимости на выходе `in_dev` и прогон планки) пропускает его, переход не
отказан, в журнале задачи есть запись с действием
`PLAN_APPENDIX_ALREADY_IN_BASE_ACTION + ": " + <пути приложения>` и
подробностями, содержащими «приложение N (<пути>)» с номером этого
приложения.

AC-5. То же уже наложенное приложение: гейт мержа пропускает его, в журнале
задачи есть запись с действием
`PLAN_APPENDIX_ALREADY_IN_BASE_ACTION + ": " + <пути приложения>` и
подробностями, содержащими «приложение N (<пути>)» с номером этого
приложения.

AC-6. То же уже наложенное приложение: дерево полного прогона
(`appendix_tree.suite_tree` — путь автогейта, approve и suite-run)
пропускает его, прогон не отказан, в журнале задачи есть запись с действием
`PLAN_APPENDIX_ALREADY_IN_BASE_ACTION + ": " + <пути приложения>` и
подробностями, содержащими «приложение N (<пути>)» с номером этого
приложения.

AC-7. Приложение, не накладывающееся ни прямо, ни обратно, — отказ во всех
четырёх узлах: гейт мержа, дерево полного прогона, гейт применимости на выходе
`in_dev` отказывают; `scripts/plan_appendix_ci.py` завершается кодом 1 с
номером приложения в выводе.

AC-8. Тест сверки: на одном наборе случаев (приложение накладывается прямо;
уже в базе; не накладывается ни прямо, ни обратно) признание узлов пульта и
признание `scripts/plan_appendix_ci.py` дают одинаковый ответ по каждому
случаю.

AC-9. `scripts/plan_appendix_ci.py` не импортирует модулей пакета
`orchestrator`.

## Оценка объёма и деление

Сработавшие сигналы: число файлов зоны ≥ 5 (пять модулей кода плюс
`docs/codebase-map.md` и `tests/`); `budget_usd` ≥ $30 (рамка ТЗ $40).

Материал для решения Оператора — **обоснование монолита**. Естественный разрез
— (а) общее правило «уже в базе» в трёх узлах пульта и CI-скрипте,
(б) прогон рубежа `in_dev -> verifying` через `suite_tree`. Против него:
критерии ТЗ связывают обе части — AC-4 требует пропуска «уже в базе» именно
на рубеже из (б) с записью, которую задаёт (а), а тест сверки AC-8 и отказ
«во всех четырёх узлах» AC-7 проверяют узлы обеих частей разом; часть (б),
смёрженная раньше (а), даст на рубеже признание без записи в журнал
(сегодняшняя `in_tree` в `_prepared`), то есть промежуточное поведение,
расходящееся с требованием 4. Кроме того, рамка ТЗ $40 ниже суммы двух
минимальных потолков подзадач (2 × $25). Решение — за Оператором на гейте
SPEC.

## Не входит

- Условия шагов CI по событиям push/pull_request, наложение приложений в CI
  по pull_request — сделано 01M466ZERX.
- Уточнение урока «защищённый файл — первым» в `docs/operator-session.md` —
  правка Оператора.
- `amend-tests` и помощник планки `_pult.py` — отдельная задача.
- Правка путей «только чтение» ТЗ: `orchestrator/fsm_autogate.py`,
  `orchestrator/fsm.py`, `orchestrator/suite_run.py`,
  `orchestrator/acceptance.py`, `orchestrator/amend.py`,
  `orchestrator/workspace.py`, `orchestrator/config.py`,
  `orchestrator/zone_lock.py`, `orchestrator/catalog.py`,
  `orchestrator/doctor/`, `orchestrator/merge_after.py`, `scripts/guard.py`,
  `.github/workflows/ci.yml`, `tests/test_invariants.py`, `targets.yaml`,
  `docs/invariants.md`, `docs/adr/`, `docs/roadmap.md`, `docs/backlog.md`,
  `docs/operator-session.md`, `templates/`, `skills/`, `CLAUDE.md`,
  `models.yaml`, `roles.yaml`, `.artel/`.

## Материалы

- ТЗ: строки копилки 06.10 «Рубеж in_dev → verifying гоняет планку без
  приложений PLAN» и «Признание "приложение PLAN уже наложено в базе" есть не
  у всех узлов»; решение Оператора 10.10.2026 (очередь критичных, пункт 2).
- Адреса (main c6c9245c, сверено аналитиком на 9738666a):
  `orchestrator/advance_gates/acceptance.py::_acceptance_run_body`;
  `orchestrator/appendix_tree.py::_prepared` (вложенная `in_tree`, ~187) и
  `suite_tree` (~204); `orchestrator/fsm_merge_gate.py::_appendix_already_in_main`
  (~851); `orchestrator/advance_gates/plan_appendix.py::_appendix_already_in_base`
  (~212, действие журнала `PLAN_APPENDIX_ALREADY_IN_BASE_ACTION` = «приложение
  PLAN уже в базе», ~209); `scripts/plan_appendix_ci.py::apply_appendix`
  (~188) и `run` (~202–237).
- Существующие тесты CI-скрипта: `tests/test_plan_appendix_ci.py`,
  `tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py`
  (`InapplicableAppendixTest`),
  `tests/test_01m466zerxqkxtr5rqcdyvdzjq_plan_appendix_ci_pr.py`
  (`PullRequestInapplicableTest`).
- Форма записи журнала (требование 4) — решение Оператора на гейте SPEC
  10.10.2026: сохранить нынешнюю форму гейта применимости, существующие тесты
  не меняются, поэтому раздела «Меняемое поведение» нет. Тесты, которые эта
  форма обязана держать зелёными: `tests/test_plan_appendix.py`
  (`test_appendix_already_in_base_passes_with_a_journal_record`, ~566–597 —
  действие ровно `PLAN_APPENDIX_ALREADY_IN_BASE_ACTION: <пути>`, в
  подробностях «приложение 1 (<путь>)»);
  `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py::AlreadyAppliedAppendixTest`
  (~240–293 — ищет в «действие | подробности» слова «уже» и «main» и имя
  приложения: сегодня гейт мержа пишет действие «приложение PLAN уже в main:
  <пути>», после выравнивания слово «main» остаётся в подробностях — база,
  где найдено приложение, — подтянутый main);
  `tests/test_appendix_tree.py::test_appendix_already_in_tree_is_skipped_and_named`
  (~81 — признак прогона `_prepared` «уже в дереве: приложения 1»). Если
  неприменимый дифф в тестах CI-скрипта окажется обратимо применимым к их
  дереву, это вопрос эскалации, а не тихая правка ожидания (требование 7).
