---
task: 01M5NPVRRK9R6S6SD40CBJZYPT
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/; в) SPEC требует приложения PLAN; д) ТЗ ссылается на ADR: ADR-0027"
spec_sha: 9516cd9a7abb9a0dcf8e08edaa10b83cf233d325
schema_version: 5
---

# SPEC-AUDIT: Прогон планки после подтяжки main — на дереве с приложениями PLAN, как на рубеже in_dev → verifying

## ТЗ и SPEC
ТЗ → SPEC: требования 1–5 ТЗ перенесены в SPEC (требования 1–5, AC-1–AC-7);
случаи теста ТЗ 4(а)–(д) раскрыты как AC-1–AC-5; ограничение зон по смыслу
и «Не входит» перенесены. ANSWER-n.md нет, решений Оператора на гейте SPEC
в брифе нет. Поправка пути `orchestrator/plan_appendix.py` →
`orchestrator/advance_gates/plan_appendix.py` верна (файл есть только там).

Расхождения:
1. ТЗ, требование 2: «состояние не меняется на `escalated` **молча**».
   SPEC AC-3: «состояние задачи не становится `escalated`» — безусловно.
   Это строже ТЗ и неверно для пути `pull-main` (см. «Факты», п. 2).
2. Требования 6–7 SPEC (AC-6, AC-7) — раскрытие требования 3 ТЗ и «долгоживущие
   файлы перечня» требования 1 ТЗ; лишнего требования в SPEC нет.

## Факты против кода
Подтвердилось (рабочий каталог на bee11bcc = origin/main из ТЗ):
- `orchestrator/pull.py:592` — `_materialize_and_run_plank`; :620 —
  `acceptance.materialize_from_branch(… wt_path)`; :679/:682 —
  `acceptance.run(tdir, cwd=wt_path, …)`; :684–687 — текст «приёмочные тесты
  красные после подтяжки {source_branch} (слияние сохранено, откат не
  выполняется)» и `set_state(… "escalated" …)`, `Conflict([], detail)`.
- `orchestrator/advance_gates/acceptance.py:34` — `PLANK_NOT_RUN`; :598–615 —
  `suite_tree(…, not_run=PLANK_NOT_RUN)`, отказ по `tree.fixable`, затем
  `plank_in_code_copy(task_id, branch, run_cwd)`.
- `orchestrator/fsm_autogate.py:417` — `suite_tree`.
- `orchestrator/advance_gates/plan_appendix.py:28`, :40 — константы действий;
  :233 — `skip_in_base`. `orchestrator/appendix_tree.py:236–292` —
  `suite_tree`: не артель / нет приложений → `SuiteTree(wt, …)`; иначе временное
  дерево, уборка в `finally` (:289–292).

Не учтено SPEC (по коду):
1. `acceptance.plank_in_code_copy` (`orchestrator/acceptance.py:2027–2044`)
   убирает выкладку `drop_from_code_copy` (`orchestrator/acceptance.py:2008`)
   — `rmtree` всего `tasks/<id>/` без учёта того, лежал ли каталог до
   выкладки. Текущий `_materialize_and_run_plank` хранит `preexisting`
   (`orchestrator/pull.py:616–617`, :690–692), и его держит существующий тест
   `tests/test_pull.py:240` (`test_preexisting_plank_dir_is_kept_after_pull`).
   На пути «дерево = рабочая копия» (не артель / PLAN без приложений —
   большинство задач) требование 1 «выкладывается … `plank_in_code_copy`»
   ломает этот тест, а требование 5 запрещает его править. SPEC не говорит,
   какое из двух главнее: «тот же узел» на всех путях, или прежняя
   материализация с `preexisting` при `tree.root == wt_path` («поведение
   прежнее» требования 1).
2. `orchestrator/pull.py:833–839`: при `operator_pull=True` (команда
   `pull-main`, `orchestrator/pull_main.py:66`) любой `Refused` из
   `_materialize_and_run_plank` переводится в `escalated` с
   `UNVERIFIED_HEAD_REASON`. Новый отказ по приложениям вернёт `Refused` — на
   этом пути задача станет `escalated` вопреки AC-3, а правка `evaluate` вне
   зоны («только `_materialize_and_run_plank`»). AC-3 надо ограничить путями
   без `operator_pull` или назвать исход `pull-main` явно.
3. Порядок проверок. В `_materialize_and_run_plank` сейчас: материализация →
   «планка не найдена» (`pull.py:621–637`) → перечень долгоживущих
   (`:644–656`) → `ComponentsPending` (`:661–671`) → прогон. SPEC не говорит,
   куда встаёт `suite_tree`. Образец рубежа (`advance_gates/acceptance.py:598`
   против :635) ставит дерево ДО проверки отсутствия планки: тогда задача без
   планки (легитимный `skip_tests`) с неразбираемым приложением получит
   `Refused` вместо прежнего `Pulled` (`tests/test_pull.py:198`) — а требование
   3 говорит, что «порядок прочих проверок `pull` не меняется».
4. AC-6 «после подтяжки <ветка>»: в коде `{source_branch}` (`pull.py:684`) —
   имя главной ветки, не ветки задачи; слово «ветка» читается двояко
   (мелочь, на текст это не влияет).
5. Имя параметра: `plank_in_code_copy(task_id, branch, …)` ждёт ветку
   документов (`artifact_source.resolve`, `pull.py:614`), а у
   `_materialize_and_run_plank` параметр `branch` — кодовая ветка задачи.
   SPEC этого не уточняет; подставить `branch` дословно — ошибка (ловушка для
   исполнителя, не дефект SPEC).

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | `acceptance.run(…, cwd=wt_path)` без дерева (код main) — планка, проверяющая результат приложения, красна → `escalated`; тест ждёт `Pulled` и выкладку в `tree.root` |
| AC-2 | да | дерево берётся всегда временным (или `branch=t["branch"]`) — шпион на `cwd` видит не `wt_path` |
| AC-3 | частично | `tree.root is None` проигнорирован, прогон на `wt_path` — шпион прогона и журнал ловят. Но AC-3 не требует теста на ветку `fixable=False`: мутация «всегда `PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION`» (или обмен двух констант) проходит тест только с неприменимым приложением. Отклонение |
| AC-4 | да | наложение своими силами (`apply_in_order` без `already_applied`) вместо `suite_tree` — приложение, уже бывшее в main, даёт отказ, не `Pulled` |
| AC-5 | да | `suite_tree(…).__enter__()` без `with`/`ExitStack` — временный каталог `artel-appendix-suite-*` остаётся после прогона/исключения |
| AC-6 | да | красный итог на дереве возвращает `Refused`/`Pulled` или меняет текст — ловят состояние и текст |
| AC-7 | да | `extra=long_lived` отброшен или гонится отдельным прогоном с `cwd=wt_path` — шпион на вызов `run` |

## Зоны
`orchestrator/pull.py`, `docs/codebase-map.md`, `tests/` покрывают правку:
`pull.py` начнёт импортировать `appendix_tree` — блок «Импортирует» в карте
изменится, перегенерация карты в зоне. Защищённых путей
(`config.PROTECTED_PATHS`) задача не трогает, песочница ролей не
расширяется. Оговорка: AC-3 на пути `operator_pull` (см. «Факты», п. 2)
нельзя выполнить без правки `pull.evaluate` (`pull.py:833`) — это вне
ограничения зоны «только `_materialize_and_run_plank`».

## Матрица неослабления
SPEC раздела «Меняемое поведение» не несёт — существующие ожидания не
меняются, раздел и не нужен. Раздела матрицы в SPEC тоже нет; по свойствам,
которые задача трогает:

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Дерево прогона планки после подтяжки | красная планка после подтяжки эскалирует (`orchestrator/pull.py:683–688`; `tests/test_pull.py:325`) | да, на дереве с приложениями (как рубеж verifying) | AC-6 нового файла; `tests/test_pull.py:325` | ок |
| Уборка выкладки планки | материализованный каталог убран, уже лежавший — сохранён (`orchestrator/pull.py:690–692`; `tests/test_pull.py:218`, :240, :263) | под угрозой: `plank_in_code_copy` сносит `tasks/<id>/` целиком (`orchestrator/acceptance.py:2008`) | `tests/test_pull.py:240` станет красным | вопрос Оператору (см. «Вердикт», п. 1) |
| Отказ по приложениям после подтяжки | раньше отказа не было: прогон без приложений | новое, строже (fail-closed) | AC-3 | ок, с оговоркой п. 2 вердикта |
| Легитимный `Pulled` без планки (`skip_tests`) | `orchestrator/pull.py:621–637`; `tests/test_pull.py:198` | зависит от места `suite_tree` (не задано) | `tests/test_pull.py:198` (только PLAN без приложений) | вопрос Оператору (п. 3) |

## Пути обхода гейтов
1. Новый отказ (`Refused`) приходит ПОСЛЕ состоявшегося слияния
   (`pull.py:821–830`): слияние остаётся в ветке, повтор `advance`/`approve`
   видит ветку не отстающей (`pull.py:786`, `Fresh`) и планку после подтяжки
   не гоняет вовсе. Для прежних отказов (`pull.py:650`, :670) так было и раньше;
   смысл гейта держат следующие рубежи (`in_dev → verifying`,
   `fsm_merge_gate.py`), которые сами строят `suite_tree` и откажут тому же
   приложению. Отдельного отклонения не поднимаю, но SPEC этого не называет.
2. Буквальное «тот же узел `plank_in_code_copy`» только на временном дереве и
   прежняя материализация на рабочей копии — допустимое прочтение
   требования 1 («поведение прежнее»), обхода не даёт; обратное прочтение
   ломает существующий тест (п. 1 вердикта).
3. AC-3 проверяем только ветку `fixable=True` — перепутанный класс отказа
   (чинит роль ↔ чинит тот, кто разбирается с git) пройдёт планку (п. 4).

## Вердикт
concerns — SPEC можно вести дальше, но на гейте Оператору нужно решить четыре
пункта:

1. Требование 1 (`plank_in_code_copy`) против требования 5 на пути
   «дерево = рабочая копия»: `orchestrator/acceptance.py:2008` сносит
   `tasks/<id>/` целиком, `tests/test_pull.py:240` требует сохранить уже
   лежавший каталог (`orchestrator/pull.py:616–617`, :690–692). Нужно указать:
   прежняя материализация с `preexisting` при `tree.root == wt_path`.
2. AC-3 «состояние не становится `escalated`» ложно на пути `pull-main`:
   `orchestrator/pull.py:833–839` эскалирует любой `Refused`; правка там вне
   зоны. Ограничить AC-3 путями без `operator_pull`. ТЗ, требование 2
   («молча»), это допускает.
3. Место `suite_tree` относительно проверок «планка не найдена»,
   «перечень долгоживущих» и `ComponentsPending` (`orchestrator/pull.py:621–671`)
   не задано, а требование 3 запрещает менять порядок; образец рубежа
   (`orchestrator/advance_gates/acceptance.py:598` против :635) — дерево
   раньше проверки планки. Нужно указать порядок.
4. AC-3 не требует теста на `fixable=False` → `PLAN_APPENDIX_GATE_FAILURE_ACTION`
   (`orchestrator/advance_gates/acceptance.py:603–608`): подмена класса отказа
   не ловится.

Мелочи без решения: AC-6 «<ветка>» — в коде имя главной ветки
(`orchestrator/pull.py:684`); параметр `branch` для `plank_in_code_copy` —
ветка документов (`orchestrator/pull.py:614`), не кодовая.
