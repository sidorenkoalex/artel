---
task: 01M5NPVRRK9R6S6SD40CBJZYPT
type: spec_audit
author_role: spec_auditor
status: ready
verdict: pass
signals: "в) пути-признаки (тесты): tests/, tests/test_pull.py; в) SPEC требует приложения PLAN; д) ТЗ ссылается на ADR: ADR-0027"
spec_sha: 463f9b7eb277ac0e1f404e92696954f7d328821b
schema_version: 5
---

# SPEC-AUDIT: Прогон планки после подтяжки main — на дереве с приложениями PLAN, как на рубеже in_dev → verifying

## ТЗ и SPEC
ТЗ → SPEC. Требования ТЗ 1–4 перенесены в требования SPEC 1–5 и AC-1–AC-7;
случаи тестов ТЗ 4(а)–(д) — это AC-1, AC-2, AC-3, AC-4, AC-5. Ограничение зон
по смыслу и «Не входит» перенесены. ANSWER-n.md нет.

Решение Оператора на гейте SPEC №1 (круг 1) — все пункты внесены:
- п.1 (прежняя материализация с `preexisting` при `tree.root == wt_path`,
  `plank_in_code_copy` только для временного дерева) — требование 1 SPEC;
- п.2 (AC-3 только без `operator_pull`; на `pull-main` `Refused`
  эскалируется, `pull.py:833–839`) — требование 2 и AC-3 («Вне пути
  `pull-main`»), «Не входит»;
- п.3 (порядок: три прежние проверки раньше дерева, `suite_tree`
  непосредственно перед `acceptance.run`) — требование 3;
- п.4 (`fixable=False` → `PLAN_APPENDIX_GATE_FAILURE_ACTION`) — требование 2
  и последняя фраза AC-3;
- мелочи: в AC-6 «<имя главной ветки>»; в требовании 1
  `plank_in_code_copy(task_id, <ветка документов задачи>, tree.root)`.

SPEC → ТЗ: требований сверх ТЗ и решения нет. Требование 3 (порядок) и
оговорка про `pull-main` взяты из решения Оператора. Поправка пути
`orchestrator/plan_appendix.py` → `orchestrator/advance_gates/plan_appendix.py`
верна: файл есть только там.

Замечание без отклонения: ТЗ п.5 требует, чтобы существующие тесты «не
правились и оставались зелёными». В SPEC требование 6 оставляет только «не
правятся», а «остаются зелёными» стоит в «Не входит» с пометкой «её держит
пульт». Строку прошлого круга Оператор принял («Остальное SPEC — без
изменений»). Смысл она не ослабляет: полный набор судит пульт на рубеже,
а `tests/test_pull.py:240` прямо назван в требовании 1 как свойство, которое
надо сохранить.

## Факты против кода
Сверено с рабочим каталогом (bee11bcc):
- `orchestrator/pull.py:592` — `_materialize_and_run_plank`; :616 —
  `artifact_source.resolve` (ветка документов); :618 — `preexisting`; :620 —
  `materialize_from_branch(…, wt_path)`; :622–639 — «планка не найдена»;
  :648–661 — перечень долгоживущих; :666–676 — `ComponentsPending`;
  :679/:682 — `acceptance.run(tdir, cwd=wt_path, …)`; :684–688 — текст
  «приёмочные тесты красные после подтяжки {source_branch} (слияние сохранено,
  откат не выполняется)», `escalated`, `Conflict([], detail)`; :690–692 —
  уборка по `preexisting`. Подтверждено.
- `orchestrator/pull.py:833–839` — при `operator_pull` любой `Refused` →
  `escalated` (`UNVERIFIED_HEAD_REASON`). Подтверждено; на прочих путях
  `Refused` → `"refused"` (`orchestrator/fsm.py:285–286`), без смены состояния.
- `orchestrator/advance_gates/acceptance.py:34` — `PLANK_NOT_RUN`; :598–615 —
  `suite_tree(conn, task_id, run_cwd, not_run=PLANK_NOT_RUN)`, отказ по
  `tree.fixable`, затем `plank_in_code_copy(task_id, branch, run_cwd)`.
  Подтверждено.
- `orchestrator/fsm_autogate.py:417` — `suite_tree`. Подтверждено.
- `orchestrator/advance_gates/plan_appendix.py:28` —
  `PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION`, :40 —
  `PLAN_APPENDIX_GATE_FAILURE_ACTION`. Подтверждено.
- `orchestrator/acceptance.py:2027–2044` — `plank_in_code_copy`, в `finally`
  `drop_from_code_copy` (:2008, `rmtree` всего `tasks/<id>/`). Подтверждено.
- `tests/test_pull.py:240` — `test_preexisting_plank_dir_is_kept_after_pull`.
  Подтверждено.
- `orchestrator/appendix_tree.py:236–292` — `suite_tree`: не артель / нет
  приложений → `SuiteTree(wt, …)`; ошибки разбора → `fixable=True` (:264–268);
  сбой `_checked_out` → `fixable=False` (:275–286); наложение → `fixable=True`;
  `skip_in_base` (:280); уборка дерева в `finally` (:289–292). То, что SPEC
  говорит о `fixable=False` («например, сбой git»), подтверждено.

Наблюдения о реализации (не дефекты SPEC):
- При `branch=None` `suite_tree` копирует неотслеживаемые неигнорируемые файлы
  рабочей копии во временное дерево (`orchestrator/appendix_tree.py:133–166`).
  `tasks/` не игнорируется (`git check-ignore` пусто), поэтому планка,
  выложенная в `wt_path` на :620, попадёт в дерево копией. Вреда нет:
  `plank_in_code_copy` → `materialize_from_branch` убирает лишние файлы и
  перезаписывает выкладку (`orchestrator/acceptance.py:1790–1844`), а
  помощник `_pult.py` пересобирается под `tree.root`.
- `SuiteTree.warning` (PLAN не прочитан → прогон на `wt` без приложений,
  `orchestrator/appendix_tree.py:269–270`, `read_plan` :89) SPEC не называет.
  Рубеж verifying и автогейт его тоже не обрабатывают — расхождения с образцом
  нет.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | прогон на `wt_path` без дерева (код main) — планка, проверяющая результат приложения к защищённому файлу, красна → `escalated`; тест ждёт `Pulled` |
| AC-2 | да | путь «дерево = рабочая копия» переведён на `plank_in_code_copy`/иной `cwd` — шпион на `cwd` и `tests/test_pull.py:240` (уборка без `preexisting`) |
| AC-3 | да | `tree.root is None` проигнорирован (прогон идёт) или `escalated` вместо отказа; перепутаны или склеены константы действия — ловит вторая ветка с `fixable=False` |
| AC-4 | да | наложение своими силами без `skip_in_base` — уже наложенное приложение даёт отказ, а не `Pulled` |
| AC-5 | да | `suite_tree(...).__enter__()` без `with`/`ExitStack` — каталог `artel-appendix-suite-*` остаётся после прогона или исключения |
| AC-6 | да | красный итог на дереве даёт `Refused`/`Pulled` либо меняется текст — ловят состояние и текст |
| AC-7 | да | `extra=long_lived` отброшен или долгоживущие гонятся отдельно с `cwd=wt_path` — шпион на вызов `run` |

## Зоны
`orchestrator/pull.py`, `docs/codebase-map.md`, `tests/` покрывают всю
правку. Новый импорт `appendix_tree` в `pull.py` меняет блок «Импортирует» в
карте — регенерация в зоне. На пути `pull-main` правка `evaluate` не нужна:
AC-3 ограничен путями без `operator_pull`. Защищённые пути
(`orchestrator/config.py:769–775`) не затрагиваются: новый файл тестов — не
`conftest.py` и не `tests/test_invariants.py`. Песочница ролей не
расширяется.

## Матрица неослабления
Раздела «Меняемое поведение» в SPEC нет — ожидания существующих тестов не
меняются.

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Дерево прогона планки после подтяжки | красная планка после подтяжки эскалирует (`orchestrator/pull.py:683–688`) | да, на дереве с приложениями | AC-6 нового файла; существующие тесты `tests/test_pull.py` | ок |
| Уборка выкладки в рабочей копии | убирается материализованный каталог, уже лежавший сохраняется (`orchestrator/pull.py:690–692`; `tests/test_pull.py:240`) | да: при `tree.root == wt_path` материализация прежняя (требование 1) | `tests/test_pull.py:240`; AC-2 | ок |
| Порядок проверок до прогона | «планка не найдена», перечень, `ComponentsPending` (`orchestrator/pull.py:622–676`) | да, требование 3 | существующие тесты `tests/test_pull.py` | ок |
| Отказ по приложениям после подтяжки | раньше отказа не было | новое, строже (fail-closed) | AC-3 (обе ветки `fixable`) | ок |

## Пути обхода гейтов
1. Отказ по приложениям приходит после состоявшегося слияния. Повтор видит
   ветку не отстающей (`Fresh`), и планку после подтяжки он не гоняет; так же
   было и у прежних `Refused` (`orchestrator/pull.py:661`, :676). Смысл
   проверки держат следующие рубежи (`in_dev → verifying`, автогейт, гейт
   мержа): они сами строят `suite_tree` и откажут тому же приложению. Это
   отмечено в прошлом круге, Оператор оставил SPEC без изменений — отклонение
   не поднимаю.
2. Других путей не нашёл: буквальное выполнение требований 1–3 даёт тот же
   узел дерева и выкладки, что на рубеже verifying.

## Вердикт
pass — отклонений нет. Все четыре пункта и обе мелочи прошлого круга внесены
в SPEC по решению Оператора №1. Факты о коде подтверждены (раздел «Факты
против кода»). Каждый AC ловит правдоподобную мутацию. Зоны достаточны.

Замечания без решения: «остаются зелёными» из ТЗ п.5 — в «Не входит»
(раздел «ТЗ и SPEC»); копия выкладки из `wt_path` во временное дерево
безвредна (`orchestrator/appendix_tree.py:133–166`,
`orchestrator/acceptance.py:1790–1844`).
