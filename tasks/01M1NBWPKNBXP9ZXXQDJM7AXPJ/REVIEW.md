---
task: 01M1NBWPKNBXP9ZXXQDJM7AXPJ
type: review
author_role: reviewer
status: changes_requested
iteration: 2
schema_version: 3
---

# REVIEW: Сверка свежести ветки против main артели на origin

## Фаза A: гейт плана

PLAN.md итерации 2 добавляет только шаг 5 (описание правки R1-F1/R1-F2)
поверх плана итерации 1 — таблица покрытия требований 1–5 → шаги 1–3
не изменилась и остаётся полной. Шаги по-прежнему единицы размера MR,
подход не конфликтует с архитектурой (переиспользует
`commits_behind(base=...)`, `confirmed_ci_note`,
`_wait_for_branch_ci_green`, поле `url`/`base` записи target'а). Правки
R1-F1/R1-F2 корректно описаны шагом 5 и соответствуют фактическому
коду — см. Фазу B.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (сверка/подтяжка против origin, не пина) | OK | `fsm._origin_main_sha`/`_pull_main_or_escalate` (fsm.py:128–286); AC-1/AC-4 зелёные. |
| 2 (гейт `merge_gate` ждёт CI циклом на пути "fresh" после push) | OK | `fsm_merge_gate.py` (ветка `pull_outcome == "fresh"`) возвращает `("wait", branch)` вместо разового опроса, ре-ран флейка (`_ci_confirm_red_or_flake`) сохранён через общий `_wait_for_branch_ci_green`; AC-5/AC-7 зелёные. |
| 3 (расхождение пина не влияет ни на что, кроме `doctor`) | OK | R1-F1 закрыт: `_origin_main_sha() is None` → ранний `return "fresh"` ДО `commits_behind`/`merge` (fsm.py:266-269), литерал `"FETCH_HEAD"` убран целиком. `doctor.py`/`pin.py` не тронуты. Регресс-тест `test_advance_treats_origin_fetch_failure_as_fresh` зелёный (см. «Проверено исполнением»). |
| 4 (существующие тесты зелёные, расширены не переписаны) | OK | 1356/1356 `tests/` зелёные, 9/9 приёмочных зелёные. Правки внутри существующих тестов (`test_branch_freshness_gate.py`, `test_ci_status_kind_gate.py`, `test_invariants.py`, `test_fsm_merge_gate_done_snapshot.py`, `test_fsm_map_conflict_autoresolve.py`) — не ослабление, см. итерацию 1 и «Проверено исполнением» здесь. |
| 5 (remote/репозиторий из конфигурации target'а) | OK | `_origin_main_source` (fsm.py:128–164); AC-10 юнит-тест зелёный. R1-F2 закрыт: commit-сообщение подтяжки несёт `source_branch = _origin_main_source(target_name)[1]`, не литерал `config.MAIN_BRANCH` (fsm.py:282-285). |

## Замечания

- major — `tests/test_branch_freshness_gate.py`, `tests/test_merge_gate_ci_wait.py`,
  `tests/test_ci_status_kind_gate.py`, `tests/test_invariants.py`,
  `tests/test_fsm_merge_gate_done_snapshot.py` — ни один новый и ни один
  изменённый в этой ветке тестовый метод не несёт в докстринге заявку
  `Ловит мутацию: …` (skills/test-authoring.md; review-checklist, Фаза B
  п.3). Конвенция введена коммитом `ec80cd60` 2026-09-02 — раньше SPEC
  (`fdf31466`, 2026-09-04 08:42), PLAN и обеих итераций этого ревью, то
  есть действовала весь срок жизни задачи; в этом же репозитории уже
  есть прецедент, где ревью другой задачи (01M1HNNHDMP2C1AJTH5QF1BTN2,
  коммит `77c823a6`) потребовало ретрофита ровно этого докстринга.
  Полный список задетых методов:
  - `tests/test_branch_freshness_gate.py::BranchFreshnessGateTest::test_advance_pulls_main_and_advances_when_acceptance_green` (изменён — новые assert'ы AC-2/R1-F1, заявки нет)
  - `tests/test_branch_freshness_gate.py::BranchFreshnessGateTest::test_freshness_check_never_defaults_base_to_local_pin` (новый, AC-4)
  - `tests/test_branch_freshness_gate.py::BranchFreshnessGateTest::test_advance_treats_origin_fetch_failure_as_fresh` (новый, R1-F1)
  - `tests/test_branch_freshness_gate.py::TargetSourcedRemoteTest::test_pull_freshness_fetches_target_url_not_pult_origin` (новый, AC-10)
  - `tests/test_merge_gate_ci_wait.py::FreshPathDefersToWaitLoopTest::test_fresh_with_no_confirmed_note_returns_wait_without_polling_ci` (новый, AC-7)
  - `tests/test_ci_status_kind_gate.py::NonRedStatusSkipsRerunTest::test_still_running_does_not_trigger_a_rerun` (изменён — assertEqual→assertGreater)
  - `tests/test_ci_status_kind_gate.py::NonRedStatusSkipsRerunTest::test_unknown_status_does_not_trigger_a_rerun` (изменён — assertEqual→assertGreater)
  - `tests/test_invariants.py::MergeNeedsGreenCiTest::test_no_merge_without_a_green_ci` (изменён — добавлена заглушка часов)
  - `tests/test_invariants.py::MergeNeedsGreenCiTest::test_the_refusal_names_the_reason_in_the_journal` (изменён — запрос журнала обобщён)
  - `tests/test_fsm_merge_gate_done_snapshot.py::DonePathSnapshotTest::test_done_transition_publishes_a_snapshot_like_killed_does` (изменён — явный `confirmed_ci_note`)
  - `tests/test_fsm_merge_gate_done_snapshot.py::DonePathSnapshotTest::test_done_snapshot_removes_the_pult_artifact_branch` (изменён — явный `confirmed_ci_note`)

  Последствие: без заявленной мутации ревьювер не может сверить
  чувствительность теста с конкретной правдоподобной поломкой (обязанность
  Фазы B п.3) — приходится либо доверять на слово, либо реконструировать
  мутацию самому, что сама же конвенция запрещает ("сверяй тест С НЕЙ, а
  не мысленным мутационным тестом по наитию"). Функционально сами тесты,
  насколько можно судить по чтению, содержательны (докстринги описывают
  сценарий и наблюдаемое свойство, не пересказывают имя метода) — дефект
  чисто в отсутствии заявки, не в слабости самой проверки.
  Предложение: добавить строку `Ловит мутацию: …` в докстринг каждого
  перечисленного метода — по образцу ретрофита `77c823a6`
  (tests/test_amend.py).

### Итог по замечаниям итерации 1

R1-F1 и R1-F2 проверены исполнением (см. «Проверено исполнением») —
оба фактически исправлены так, как описывает реестр ниже, оба
переведены в `accepted`.

### Сценарий поломки R1-F1 (архивно, итерация 1)

`_origin_main_sha` докстринг (fsm.py:128 и далее) заявляет: «`None` —
... вызывающий код обязан деградировать так же, как при неответившем
git» и «сверка ниже деградирует на "ничего не делать"». На практике это
не так для ОБОИХ путей к `None`:

1. **Конкурентность, новая в этом PR.** До этой задачи `_pull_main_or_
   escalate` не делала `git fetch` вовсе в двух из трёх точек вызова
   (`in_dev -> review`, `acceptance -> merge_gate`) — только третья
   (окно `merge_gate`) защищена `merge_lock` (единственный мьютекс на
   весь пульт, `orchestrator/merge_lock.py:1-8`). Теперь ВСЕ три точки
   делают `gitcmd.git("fetch", ...)` в общем `config.ROOT`
   (`gitcmd.py:9-19` — `git()` всегда `cwd=config.ROOT`), а две из трёх
   — БЕЗ какой-либо сериализации между разными задачами. Две разные
   задачи, одновременно проходящие `in_dev -> review`, реалистично
   могут столкнуться на `git fetch` в одном и том же репозитории (lock
   ref-файлов) — один из двух `fetch` завершится ненулевым кодом.
2. **`FETCH_HEAD` в `config.ROOT` — общее, устойчивое состояние, не
   «пусто по умолчанию».** В живом пульте оно почти всегда содержит
   что-то от ПРЕДЫДУЩЕГО успешного фетча (свой собственный —
   self-target фетчится регулярно и этим узлом, и уже существующим
   `fsm_merge_gate._origin_main_sha`; либо чужой — другого target'а).
   Поэтому на `_origin_main_sha() is None` (сбой fetch ИЛИ
   `targets.TargetsError` неисправной записи target'а) `base` —
   литерал `"FETCH_HEAD"`, и `gitcmd.commits_behind(branch,
   base="FETCH_HEAD")` (`gitcmd.py:47-66`, выполняется тоже в
   `config.ROOT`) сравнивает ветку задачи НЕ «ни с чем», а с ЧЕМ
   ПОПАЛО, что там сейчас лежит — в том числе, для внешнего target'а,
   с main АРТЕЛИ (или наоборот). Заявленная докстрингом гарантия
   «молчаливый откат ... был бы ОПАСНЕЕ обычной деградации» (PLAN,
   узел 3) для этого случая НЕ выполняется — обычная деградация здесь
   и есть тот опасный откат.
3. **Merge внутри `wt_path` (fsm.py:273) той же строкой `"FETCH_HEAD"`
   резолвится в СОВСЕМ ДРУГОЙ файл.** Начиная с git 2.5 `FETCH_HEAD`
   приватен для каждого worktree (подтверждено `git worktree --help`:
   «sharing everything except per-worktree files» и `git help
   gitrepository-layout`: «most of files in $GIT_DIR are per-worktree
   with a few known exceptions» — ровно тот факт, на который сам
   докстринг `_origin_main_sha` (fsm.py, комментарий про «начиная с git
   2.5») ссылается как на причину НЕ использовать литерал `"FETCH_HEAD"`
   в обычном случае). `gitcmd.in_repo(wt_path, "merge", ...)` —
   `git -C <wt_path> merge ...` (`gitcmd.py:104-115`) — то есть merge
   резолвит `"FETCH_HEAD"` в приватном `FETCH_HEAD` `wt_path`, НЕ в том,
   что только что (или год назад) зафетчил `config.ROOT`. В типичном
   случае worktree задачи никогда сам не фетчил — merge отказывает
   («not something we can merge»), задача ложно эскалируется на пустом
   месте (шум, ложные эскалации по вине временного сбоя фетча). Худший
   случай — worktree задачи когда-то нёс собственный `FETCH_HEAD»
   (например, ролевой агент вручную гонял `git fetch`/`git pull` внутри
   своего worktree в рамках разработки) — тогда merge молча вольёт
   СТАРОЕ/ПОСТОРОННЕЕ содержимое этого приватного `FETCH_HEAD`, и задача
   решит, что подтянула актуальный main, хотя это не так.

Ни один AC не покрывает деградацию `_origin_main_sha() is None` внутри
`_pull_main_or_escalate` (все AC-1..AC-10 проверяют путь, где
`git fetch` реально успевает — приёмочная песочница `OriginDivergedSandbox`
всегда исполняет настоящий git без искусственного сбоя фетча) — дефект
не поймается существующим набором.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/fsm.py:266-269 | Деградация `_origin_main_sha() is None` подставляет литерал `"FETCH_HEAD"` вместо истинного no-op | Сравнение/merge против постороннего состояния `config.ROOT`; для merge — против приватного `FETCH_HEAD` чужого worktree (ложная эскалация в типичном случае, риск тихого неверного merge в худшем) | Проверено: `base = _origin_main_sha(target_name); if not base: return "fresh"` (fsm.py:265-269) — ранний выход ДО `commits_behind`/`merge`; единственное оставшееся в файле использование `"FETCH_HEAD"`-литерала (fsm.py:194, `rev-parse FETCH_HEAD` внутри `_origin_main_sha` сразу после успешного `fetch` в `config.ROOT`) — легитимное чтение результата только что сделанного fetch'а, не подстановка в `base` сверки/merge (`grep -n '"FETCH_HEAD"' orchestrator/fsm.py` — единственное вхождение вне докстрингов/комментариев). Регресс-тест `test_advance_treats_origin_fetch_failure_as_fresh` зелёный, проверяет ровно этот путь (`_origin_main_sha` замокан на `None`, `commits_behind`/`merge`/`acceptance.run` не вызваны, состояние — `review`, тот же исход, что «не отстала»). |
| R1-F2 | accepted | orchestrator/fsm.py:282-285 | Commit-сообщение подтяжки жёстко называет `config.MAIN_BRANCH`, даже когда реальный источник merge — `base` внешнего target'а | Вводящее в заблуждение сообщение коммита для не-self target'а (не влияет ни на один AC) | Проверено: `source_branch = source[1] if source is not None else config.MAIN_BRANCH`, merge-сообщение — `f"{task_id}: подтяжка {source_branch}"`, литерал `config.MAIN_BRANCH` в f-строке заменён. |
| R2-F1 | open | tests/test_branch_freshness_gate.py и ещё 4 файла (список выше) | Ни один новый/изменённый тест этой ветки не несёт докстринг-заявку `Ловит мутацию: …` | Ревьювер не может сверить чувствительность теста с конкретной заявленной мутацией (Фаза B п.3) — обязанность конвенции, действующей с 2026-09-02 | Добавить строку `Ловит мутацию: …` в докстринг каждого перечисленного метода |

## Вердикт

changes_requested — один major (R2-F1): добавить заявленную мутацию
`Ловит мутацию: …` в докстринг каждого из 11 перечисленных тестовых
методов. R1-F1 и R1-F2 закрыты — код и регресс-тесты подтверждены
исполнением, замечания переведены в `accepted`.

## Проверено исполнением

- Рабочее дерево на входе снова несло непроиндексированные удаления
  всего `tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/` — восстановлено `git
  checkout -- tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/` (по прецеденту памяти),
  `git status` после — чисто.
- Инкрементальный diff пакета не собрался (невалидный sha
  `00e32aaf...`) — не совпадает ни с одним коммитом истории; найден
  фактический коммит вердикта итерации 1 (`git log --oneline --all --
  tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/REVIEW.md` → `567dd84e`, первое
  появление REVIEW.md с `iteration: 1`) и собран `git diff
  main...HEAD -- orchestrator/ tests/ tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/`
  — диф ветки от `main` (исключает шум подтяжек main в промежуточные
  коммиты, три из которых на этой ветке — `7b5aa851`/`959d603f` и один
  WIP), 21 файл, ровно объём PLAN.md.
- `python3 -m unittest discover -s tests -q` — 1356 тестов, `OK`.
- `python3 -m unittest tests.test_branch_freshness_gate
  tests.test_fsm_map_conflict_autoresolve tests.test_gitcmd_branch_reads
  tests.test_merge_gate_ci_wait tests.test_ci_status_kind_gate
  tests.test_invariants tests.test_fsm_merge_gate_done_snapshot -v` —
  92 теста, `OK` (AC-9, целевые файлы поимённо).
- `python3 -m unittest discover -s
  tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests -p "test_ac*.py" -v`
  — 9 тестов (AC-1..AC-9), `OK`.
- `python3 scripts/codebase_map.py` (регенерация) — diff с
  закоммиченным `docs/codebase-map.md` отличается ТОЛЬКО строкой
  `built_at_sha` (`git diff docs/codebase-map.md | grep -v
  '^[+-]built_at_sha'` — пусто, кроме заголовка); карта не устарела по
  содержимому. Рабочее дерево возвращено `git checkout --
  docs/codebase-map.md`.
- `git diff main...HEAD -- orchestrator/doctor.py orchestrator/pin.py`
  — пусто: требование 3/AC-8 (расхождение пина не трогает doctor)
  подтверждено также фактом, что `doctor.py` не задет этим diff'ом
  вовсе.
- `git diff 1974bf5f..HEAD -- tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests/`
  — пусто (кроме pycache): приёмочная планка test_author'а не
  редактировалась после лока.
- Прочитаны точечно (сверх пакета): `orchestrator/fsm.py` (полный
  diff `main...HEAD`, узлы `_origin_main_source`/`_origin_main_sha`/
  `_pull_main_or_escalate`), `orchestrator/fsm_merge_gate.py` (диф
  `_cmd_approve_merge_gate` + нетронутый `_cmd_approve_merge_gate_cycle`
  строк 382-424 — подтверждение, что потолок/цикл ожидания не менялись,
  AC-6), `orchestrator/gitcmd.py` (`commits_behind`, `in_repo`, `git`),
  `orchestrator/targets.py` (`target()`/`check()`/`TargetsError` —
  подтверждение, что неполная запись target'а гарантированно кидает
  `TargetsError`, не `KeyError`), diff всех шести затронутых файлов
  `tests/` (для реестра замечаний и R2-F1), `skills/test-authoring.md`
  и история его коммитов (`ec80cd60`, 2026-09-02 — конвенция
  `Ловит мутацию` действовала до начала этой задачи), прецедент
  `77c823a6` (01M1HNNHDMP2C1AJTH5QF1BTN2) — тот же класс замечания уже
  фигурировал в этом репозитории.

## Предложения системе

(пусто)
