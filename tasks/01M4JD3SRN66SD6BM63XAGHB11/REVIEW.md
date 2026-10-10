---
task: 01M4JD3SRN66SD6BM63XAGHB11
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Приложения PLAN — рубеж in_dev → verifying и CI ветки по одному правилу

## Фаза A — план

- Таблица покрытия полна: требования 1–7 привязаны к шагам 1–6.
- Шаги размера MR, по одному модулю на шаг.
- С архитектурой подход не конфликтует: правило `in_base` и узел записи
  `skip_in_base` лежат в `advance_gates/plan_appendix.py` (там же
  `git_apply` и действие журнала), `appendix_tree` и `fsm_merge_gate`
  импортируют их оттуда. CI-скрипт держит свою копию правила.
- «Влияние на систему» сходится с diff: шесть файлов кода и тестов плюс
  карта. Защищённых путей и путей «только чтение» diff не трогает
  (`git diff --stat` пакета).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `advance_gates/acceptance.py:363-378`: после проверок рабочей копии вызывается `suite_tree(conn, task_id, run_cwd, not_run=PLANK_NOT_RUN)`, дальше `run_cwd = tree.root`. В это дерево выкладываются планка (`plank_in_code_copy`), там же идут долгоживущие файлы, `_seed_repeats_escalate` и карточка. Дерево живёт в `cleanup` до конца тела. Без приложений и у проекта не артели `root` — это рабочая копия (`appendix_tree.py:255-262`). |
| 2 | OK | Гейт применимости отказывает раньше. Отказ теперь с номером: «приложение N PLAN (<пути>) не применяется…» (`plan_appendix.py:203-206`). Если отказывает само дерево, переход отклонён без прогона: `fixable` пишется действием `PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION`, иначе `PLAN_APPENDIX_GATE_FAILURE_ACTION`. |
| 3 | OK | Правило одно — `plan_appendix.in_base`. Его зовут гейт применимости, гейт мержа (`_appendix_already_in_main` → `skip_in_base`) и дерево (`_overlaid` через `skip_in_base`; `_prepared` вызывает `in_base` без записи). В CI-скрипте — копия `in_base` через `apply_appendix(..., "--reverse", "--check")`. |
| 4 | OK | У всех узлов пульта одна запись: действие `PLAN_APPENDIX_ALREADY_IN_BASE_ACTION: <пути>`, в подробностях «приложение N (<пути>) уже наложено в <where>». CI-скрипт печатает «[id] приложение N (<пути>) уже в базе: …». |
| 5 | OK | В узлах пульта одна общая функция. `scripts/plan_appendix_ci.py` не импортирует `orchestrator`; совпадение ответов проверяет AC-8 (`ReconciliationTest`) в долгоживущем файле. |
| 6 | OK | `in_base` требует `--reverse --check`. Наполовину наложенное приложение отказывает во всех четырёх узлах (AC-7, три долгоживущих файла). |
| 7 | OK | В `tests/test_appendix_tree.py` удалены только строка докстринга модуля и заголовок класса: общий `setUp` вынесен в `GitTreeCase`, методы `PreparedTreeTest` и их утверждения не менялись. Ожидания существующих тестов не тронуты. |

## Замечания

Замечаний уровня blocker/major/minor нет.

Наблюдения, которые не требуют правки:
- Рубеж `in_dev -> verifying` может записать «уже в базе» дважды на одно
  приложение: один раз гейт применимости (база сравнения), второй —
  дерево рубежа. План называет это в «Рисках», AC-4 требует только наличия
  записи.
- `SuiteTree.warning` (PLAN не прочитан) рубеж не выводит и не пишет в
  журнал. Поведение то же, что у прежнего прогона без приложений, но
  отдельного сигнала на рубеже нет. Требований SPEC это не нарушает.
- `_prepared` в коде больше не вызывается, только в
  `tests/test_appendix_tree.py`. Его оставили, чтобы не менять
  существующие тесты (требование 7) — это обосновано.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: замечаний не заведено.

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest -q tests/test_appendix_tree.py tests/test_plan_appendix.py tests/test_plan_appendix_ci.py tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py tests/test_01m466zerxqkxtr5rqcdyvdzjq_plan_appendix_ci_pr.py tests/test_refusal_classes.py` — 62 passed, 12 subtests passed. В этот прогон входят существующие тесты, которые по SPEC должны остаться зелёными: `AlreadyAppliedAppendixTest` гейта мержа, `test_appendix_already_in_base_passes_with_a_journal_record`, `test_appendix_already_in_tree_is_skipped_and_named`, а также тесты CI-скрипта на неприменимое приложение.
- `python3 -m pytest -q tests/test_01m4jd3srn66sd6bm63xaghb11_*.py tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py` — 18 passed, 15 subtests passed (76.9 с). Это три долгоживущих файла задачи (AC-1…AC-9) и прежние гейты выхода из `in_dev`.
- `artel.py plank-run 01M4JD3SRN66SD6BM63XAGHB11` — отказ «планки нет: в источнике нет файлов test_*.py». У задачи только долгоживущие файлы; их прогон — пункт выше.
- `python3 scripts/codebase_map.py`, затем `git diff -- docs/codebase-map.md | grep -v built_at_sha` — содержимое не расходится, карта свежа. Регенерированный файл возвращён `git checkout`.
- Временную мутацию `fixable = False` для `SuiteTreeRefusalClassTest` запустить не удалось: команду правки отклонил контур прав. Покраснение проверено по коду: тест утверждает `assertTrue(tree.fixable)` на отказе наложения, значит мутация из заявки делает его красным. Заявка второго метода («`fixable` на любой отказ») ловится `assertFalse(tree.fixable)` на отсутствующей ветке.
- CI коммита 5043f5d5 зелёный (16 проверок) — по пакету.

## Предложения системе

- `scripts/codebase_map.py` не знает режима `--check`: флаг молча
  игнорируется, и карта перезаписывается на месте. Ревьюверу, который
  проверяет свежесть, приходится откатывать файл руками. Стоит добавить
  режим проверки без записи — тот приём, которым пользуется CI-джоб.
