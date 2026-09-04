---
task: 01M1NBWPKNBXP9ZXXQDJM7AXPJ
type: plan
author_role: developer
status: ready
schema_version: 3
---

# PLAN: Сверка свежести ветки против main артели на origin

## Подход

Три независимых узла:

1. **Сверка свежести против origin, не пина** (`orchestrator/fsm.py::
   _pull_main_or_escalate`, AC-1..AC-4, AC-8). Новая функция
   `fsm._origin_main_sha(target_name)` делает `git fetch <remote>
   <branch>` (источник — узел 3 ниже) и возвращает `sha` (`rev-parse
   FETCH_HEAD`) — она СВОЯ копия узла `fsm_merge_gate._origin_main_sha`
   (тот же приём точечного дублирования по модулю, что уже несёт
   `MAP_REL`): `fsm_merge_gate` импортирует `fsm`, обратный импорт завёл
   бы цикл; там `_origin_main_sha` остаётся про main АРТЕЛИ конкретно
   (плотницкий merge Stage0, только self-target/`operator` гейт) и этой
   задачей не тронут. `base = fsm._origin_main_sha(target_name)` идёт и
   в `gitcmd.commits_behind(branch, base=base)` (сверка), и в `git merge
   --no-ff <base>` внутри worktree задачи (подтяжка) — один и тот же
   `base` для обеих операций, `config.MAIN_BRANCH` в коде узла остаётся
   только ИМЕНЕМ ветки self-target, которую фетчим, не источником
   сравнения. `git fetch` пишет только в объектную базу/`FETCH_HEAD`
   `config.ROOT` — ни рабочее дерево, ни HEAD, ни зафиксированный там
   пин не трогает (AC-8); `gitcmd.commits_behind` уже принимает `base`
   параметром (существующая сигнатура, менять не пришлось). `base` не
   ответила (`None`/пустая строка — git/fetch/rev-parse не ответили,
   либо конфигурация target'а не читается) — переход возвращает
   `"fresh"` немедленно, ДО вызова `commits_behind`/`merge` (REVIEW.md
   R1-F1, итерация 1: литерал `"FETCH_HEAD"` в качестве `base` здесь
   раньше подставлялся вместо честного no-op — небезопасно, `FETCH_HEAD`
   `config.ROOT` почти никогда не пуст на живом пульте, а внутри
   worktree задачи резолвится в СВОЙ приватный `FETCH_HEAD`, git 2.5+ —
   ни то, ни другое не «ничего не делать»).
   Три точки вызова `_pull_main_or_escalate` (`in_dev -> review`,
   `acceptance -> merge_gate`, окно `merge_gate`) не тронуты — они уже
   зовут этот единственный узел, менять их незачем (AC-3 закрывается
   самим фактом единственной точки правки).

2. **Ожидание CI на пути "fresh" после push** (`orchestrator/
   fsm_merge_gate.py::_cmd_approve_merge_gate`, AC-5..AC-7). На ветке
   `pull_outcome == "fresh"` тело гейта больше не зовёт `ci.
   branch_status` само и не отказывает по одному опросу: если
   `confirmed_ci_note is None`, возвращает `("wait", branch)` — тот же
   сигнал, что уже несёт ветка `"pulled"`. Внешний цикл
   `_cmd_approve_merge_gate_cycle` (не менялся) сам не различает, ПОЧЕМУ
   пришёл `("wait", ...)` — гоняет `_wait_for_branch_ci_green` вне
   мьютекса и на следующем заходе передаёт подтверждённый статус телу
   через уже существующий параметр `confirmed_ci_note`. Потолок ожидания
   — существующая `config.MERGE_GATE_CI_WAIT_CEILING_SEC`, второй
   константы не заводилось (AC-6): цикл её и так уже читает.
   `_wait_for_branch_ci_green` уже несёт ре-ран флейка
   (`_ci_confirm_red_or_flake`) — путь "fresh" не теряет эту механику
   (SPEC T082), просто доходит до неё через общий цикл, как и путь
   "pulled".

3. **Remote/репозиторий из конфигурации target'а, не хардкод origin**
   (`orchestrator/fsm.py::_origin_main_source`, требование 5, AC-10;
   ANSWER-1, вопрос отвечен ПОСЛЕ лока приёмочной планки — юнит-тест
   пишется здесь, в `tests/`, не в залоченных `acceptance_tests/`).
   Self-target (`config.DEFAULT_TARGET`) — литерал `"origin"`/`config.
   MAIN_BRANCH` БЕЗ обращения к `targets.yaml` (ANSWER-1: «для
   self-target — origin пульта»; лёгкие песочницы AC-1..AC-9 намеренно
   не заводят `config.TARGETS` для self-target сценария — чтение файла
   здесь безусловно сломало бы их, AC-9). Любой другой target —
   `targets.target(name)["url"]` как remote, `["base"]` как ветка:
   `targets.yaml` не несёт отдельного поля «имя remote» (это ПРОТЕКТЕД
   путь — `no_paths` самой записи `artel`, править его вне права
   разработчика), а `git fetch`/`git merge` одинаково принимают вторым
   аргументом и имя настроенного remote, и голый URL — `url` уже
   существующее поле записи (ADR-0003 п.2), «конфигурация target», без
   которой AC-10 не закрыть новым полем схемы. Запись target'а не
   читается (`targets.TargetsError`, файл/запись не годны) —
   `_origin_main_source` возвращает `None`, `_origin_main_sha`
   деградирует на «ничего не делать» ТЕМ ЖЕ путём, что и «git не
   ответил»: молчаливый откат на `"origin"` пульта здесь был бы ОПАСНЕЕ
   обычной деградации — сравнил/смержил бы задачу внешнего target
   против совсем другого репозитория (главной копии пульта), а не
   «ничего не сделал».

Все три узла используют существующие механизмы (`commits_behind
(base=...)`, `confirmed_ci_note`, `_wait_for_branch_ci_green`, поле
`url`/`base` записи target'а) — новых абстракций, кроме двух маленьких
функций `_origin_main_sha`/`_origin_main_source`, не вводилось; новых
полей `targets.yaml` не заводилось (протектед путь).

## Шаги

1. `orchestrator/fsm.py`: `_origin_main_source(target_name)` +
   `_origin_main_sha(target_name)`; `_pull_main_or_escalate` берёт
   `target_name = t["target"] or config.DEFAULT_TARGET` и сверяется/
   мержит против `base` (target-специфичный origin), не `config.
   MAIN_BRANCH`.
2. `orchestrator/fsm_merge_gate.py`: путь `pull_outcome == "fresh"` без
   `confirmed_ci_note` возвращает `("wait", branch)` вместо разового
   опроса `ci.branch_status` и немедленного отказа.
3. Юнит-тесты: `tests/test_branch_freshness_gate.py` (AC-2, AC-4 —
   сверка/merge против origin, не пина; AC-10 — `TargetSourcedRemoteTest`,
   remote/branch из конфигурации не-self target'а, не хардкод origin
   пульта), `tests/test_merge_gate_ci_wait.py` (AC-7), `tests/
   test_ci_status_kind_gate.py` (класс поведения "running"/"unknown" на
   пути fresh сохранён, но через цикл ожидания — `FakeClock`, часы
   заглушены), `tests/test_invariants.py` (требование 6 — merge без
   зелёного CI — тот же приём заглушки часов). Правка существующего
   `tests/test_fsm_merge_gate_done_snapshot.py`: два теста звали тело
   гейта напрямую без `confirmed_ci_note` (докстрайл файла — приём,
   принятый ДО этой задачи) — с новым контрактом пути "fresh" такой
   вызов больше не завершается синхронно; передан явный
   `confirmed_ci_note`, совпадающий с уже замоканным в `setUp`
   `ci.branch_status` — тот же самый узел, что и настоящий внешний цикл
   подставил бы сюда сам. Ассерты (`done`, снапшот, удаление
   артефактной ветки) не ослаблены — изменился только способ дойти до
   вызова тела.
4. Приёмочные тесты `tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests/`
   (AC-1..AC-9) уже поставлены test_author — не редактировались; AC-10
   в них нет (ANSWER-1: добавлена после лока планки, тест — в `tests/`,
   дополнение планки под AC-10 вносит Оператор командой `amend-tests`
   после сдачи).
5. REVIEW.md итерация 1 (R1-F1, major): `_pull_main_or_escalate`
   (`orchestrator/fsm.py`) на вырожденной `_origin_main_sha() → None`/
   пустая строка возвращает `"fresh"` немедленно вместо подстановки
   литерала `"FETCH_HEAD"` в `commits_behind`/`merge` (тот литерал не
   был честным no-op — см. «Подход», узел 1). R1-F2 (minor):
   commit-сообщение merge несёт реальную ветку источника
   (`_origin_main_source(target_name)[1]`), не литерал `config.
   MAIN_BRANCH`. Новый регресс-тест `tests/test_branch_freshness_gate.
   py::test_advance_treats_origin_fetch_failure_as_fresh` (R1-F1); тесты
   этого файла и `tests/test_fsm_map_conflict_autoresolve.py`,
   ранее полагавшиеся на falsy-деградацию `fake_git` (пустая строка из
   `rev-parse FETCH_HEAD` вместо `None`), получили явную truthy-заглушку
   `fsm._origin_main_sha` в `setUp` — не ослабление, тот же путь
   исполнения, что и раньше.
6. REVIEW.md итерация 3 (ANSWER-2 Оператора: закрыть R2-F1 и R3-F1 по
   леджеру, ничего сверх). R2-F1 (major, перенесено без изменений с
   итерации 2 — регрессия шага developer между итерациями 2 и 3
   потеряла текст итерации 2 в REVIEW.md на артефактной ветке, не
   затронув код; вынесено в «Предложения системе» ревьювером итерации
   3, здесь не чинится — вне права разработчика): всем 11 новым/
   изменённым тестовым методам этой ветки (`tests/
   test_branch_freshness_gate.py` — 4 метода, `tests/
   test_merge_gate_ci_wait.py` — 1, `tests/test_ci_status_kind_gate.py`
   — 2, `tests/test_invariants.py` — 2, `tests/
   test_fsm_merge_gate_done_snapshot.py` — 2) добавлена строка `Ловит
   мутацию: …` в докстринг — по образцу ретрофита `77c823a6`
   (`tests/test_amend.py`), каждая называет конкретную правдоподобную
   мутацию (перепутанный литерал вместо зафетченного sha, убранный
   ранний возврат, смешение путей "running"/"unknown" с красным
   статусом CI, пропущенная/переставленная публикация снапшота или
   удаление артефактной ветки) и наблюдаемое расхождение, на котором
   тест покраснеет. R3-F1 (minor): `_auto_resolve_map_conflict`
   принимает `source_branch` параметром (использован в её
   commit-сообщении, `fsm.py:116`); вычисление `source`/`source_branch`
   в `_pull_main_or_escalate` поднято перед первой точкой
   использования — сразу после `target_name`, до `_origin_main_sha`
   (`fsm.py:266-267`); литерал `config.MAIN_BRANCH` заменён на
   `source_branch` во всех оставшихся местах той же функции (докстринг,
   эскалации «worktree не создан»/«конфликт подтяжки»/«приёмка красная
   после подтяжки») — для self-target `source_branch == config.
   MAIN_BRANCH` байт-в-байт, вывод не меняется. Правка изолирована в
   `orchestrator/fsm.py` и `tests/`; `tests/
   test_fsm_map_conflict_autoresolve.py` не звал
   `_auto_resolve_map_conflict` напрямую (только через
   `_pull_main_or_escalate`) — смена сигнатуры без правки этого файла.

   Итоговые строки прогонов на финальном рабочем дереве этой итерации:
   - `python3 -m unittest discover -s tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/
     acceptance_tests -p "test_ac*.py" -v` — `Ran 9 tests ... OK` (AC-1..
     AC-9, планка не тронута).
   - `python3 -m unittest tests.test_branch_freshness_gate
     tests.test_fsm_map_conflict_autoresolve tests.test_gitcmd_branch_reads
     tests.test_merge_gate_ci_wait tests.test_ci_status_kind_gate
     tests.test_invariants tests.test_fsm_merge_gate_done_snapshot -v` —
     `Ran 92 tests ... OK`.
   - `python3 -m unittest discover -s tests -q` — полный набор, код
     возврата 0 (`OK`, без `FAILED`/`ERROR`); те же 1391 тестов, что
     видела итерация 3 REVIEW.md (`git diff` по задачным файлам с
     `58f1a582` — пусто, кроме самой правки R2-F1/R3-F1).
   - `python3 scripts/codebase_map.py` — diff с закоммиченным
     `docs/codebase-map.md` отличается ТОЛЬКО строкой `built_at_sha`;
     рабочее дерево возвращено `git checkout -- docs/codebase-map.md`,
     регенерация/коммит карты этой правкой не требуются.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (сверка/подтяжка против origin) | 1 |
| 2 (гейт ждёт CI циклом на пути fresh после push) | 2 |
| 3 (расхождение пина не влияет ни на что кроме doctor) | 1 (не тронут doctor.py вовсе) |
| 4 (существующие тесты зелёные, расширены не переписаны) | 3 |
| 5 (remote/репозиторий из конфигурации target'а) | 1, 3 |

## Влияние на систему

- Тронутые узлы — `fsm._pull_main_or_escalate`/новые `fsm.
  _origin_main_sha`/`fsm._origin_main_source` и `fsm_merge_gate.
  _cmd_approve_merge_gate` (одна ветка `if`). `doctor.py`, `pin.py`,
  механика `pin-update` не затронуты (SPEC «Не входит»), `targets.yaml`/
  `orchestrator/targets.py` не менялись (используется только уже
  существующее поле `url`/`base` через уже существующий `targets.
  target()`). Шаг 6 (R3-F1) добавил параметр `source_branch` в
  `_auto_resolve_map_conflict` — единственный вызывающий код
  (`_pull_main_or_escalate`, тот же модуль) обновлён тем же коммитом,
  внешних вызывающих нет (`grep` подтверждает).
- Гейты/лимиты/инварианты не ослаблены: путь "fresh" после push теперь
  СТРОЖЕ прежнего (ждёт подтверждённого зелёного CI циклом вместо
  разового опроса), не слабее. Мьютекс merge-окна и его дисциплина
  (взять/отпустить вокруг каждого захода в тело) не изменены — второй
  повод для `("wait", ...)` идёт по тому же самому пути, что и первый.
  Деградация target-конфигурации на «ничего не делать» (не на литерал
  `"origin"`) — СТРОЖЕ прежнего в новом смысле: не смешивает историю
  внешнего target'а с историей пульта при поломанной записи (риск,
  которого до этой задачи не существовало вовсе — не-self target
  раньше не сверялся так никогда).
- `gitcmd.commits_behind` уже принимал `base` параметром до этой задачи
  (правка не потребовалась) — риска регресса вызывающих без `base`
  (используют `config.MAIN_BRANCH` по умолчанию, как раньше) нет.
- Откат — `git revert` двух коммитов правки (fsm.py/fsm_merge_gate.py +
  соответствующие тесты); ничего вовне этих двух модулей не зависит от
  нового поведения.
- Один существующий юнит-тест (`tests/
  test_fsm_merge_gate_done_snapshot.py`) адаптирован под новый
  синхронный контракт тела гейта (см. Шаг 3) — без ослабления проверяемых
  условий, только способ вызова.

## Риски

- `_origin_main_sha` в `fsm.py` дублирует одноимённый узел
  `fsm_merge_gate.py` (разный модуль, тот же приём) — сознательно, чтобы
  не заводить цикл импорта (`fsm_merge_gate` уже импортирует `fsm`).
  Если оба узла разойдутся при будущей правке одного без другого — увидит
  ревью следующей задачи; отдельного докстрайна с явным упоминанием пары
  на обеих сторонах достаточно для сегодняшнего объёма.
- Требование 5/AC-10 читается на существующем поле `url` записи
  target'а как на remote git-fetch/merge — рабочий приём (git одинаково
  принимает URL и имя настроенного remote), но НЕ факт заведения
  реального клона внешнего target'а в `.artel/projects/<target>/
  workspace/` (эта инфраструктура, по докстрайну `runner.role_cwd`, ещё
  не построена — маркер A2b в коде): для существующего единственного
  target'а (`artel`, self) поведение не меняется байт-в-байт; для
  гипотетического внешнего target'а это готовит абстракцию, но полный
  контур подтяжки вне `config.ROOT` (собственный клон, собственный
  worktree) — отдельная, более крупная задача, не входящая в SPEC этой
  (материал «исследование готовности к внешнему проекту, 04.09»
  ссылается именно на этот развод: remote-конфигурация уже нужна
  сегодня, полный клон — позже).

## Предложения системе

(пусто)
