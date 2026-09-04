---
task: 01M1NBWPKNBXP9ZXXQDJM7AXPJ
type: review
author_role: reviewer
status: changes_requested
iteration: 3
schema_version: 3
---

# REVIEW: Сверка свежести ветки против main артели на origin

## Фаза A: гейт плана

PLAN.md на ветке задачи (16472 байт, sha256=c15156d5…36ea19 — совпадает
с ревью-пакетом байт-в-байт) не менялся с итерации 2: шаг 5 (описание
правок R1-F1/R1-F2) остаётся поверх шагов 1-4 итерации 1. Таблица
покрытия требований 1-5 → шаги 1-3 (плюс дробление 5 на шаги 1+3)
по-прежнему полна. Шаги — единицы размера MR (три независимых узла),
не микрооперации. Подход не конфликтует с архитектурой — переиспользует
`commits_behind(base=...)`, `confirmed_ci_note`, `_wait_for_branch_ci_green`,
поле `url`/`base` записи target'а. Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (сверка/подтяжка против origin, не пина) | OK | `fsm._origin_main_sha`/`_pull_main_or_escalate` (fsm.py:128-313); AC-1/AC-4 зелёные (см. «Проверено исполнением»). |
| 2 (гейт `merge_gate` ждёт CI циклом на пути "fresh" после push) | OK | `fsm_merge_gate.py:284-296` — `("wait", branch)` вместо разового опроса; AC-5/AC-7 зелёные. |
| 3 (расхождение пина не влияет ни на что, кроме `doctor`) | OK | R1-F1 закрыт: `_origin_main_sha() is None` → ранний `return "fresh"` (fsm.py:265-269) ДО `commits_behind`/`merge`; литерал `"FETCH_HEAD"` в сверке/merge отсутствует (`grep -n '"FETCH_HEAD"' orchestrator/fsm.py` — единственное вхождение вне докстрингов/комментариев это fsm.py:194, чтение результата ТОЛЬКО ЧТО сделанного fetch внутри `_origin_main_sha`, не подстановка в `base`). `doctor.py`/`pin.py` diff'ом не задеты. |
| 4 (существующие тесты зелёные, расширены не переписаны) | Реализовано не полностью | 1391/1391 `tests/`, 92/92 целевых, 9/9 приёмочных — зелёные (см. «Проверено исполнением»). Но новые/изменённые тестовые методы этой ветки не несут докстринг-заявку `Ловит мутацию: …`, обязательную конвенцией `skills/test-authoring.md` с 2026-09-02 (раньше SPEC этой задачи) — см. R2-F1 ниже, статус не изменился со времени, когда замечание было заведено. |
| 5 (remote/репозиторий из конфигурации target'а) | OK (minor) | `_origin_main_source` (fsm.py:128-160); AC-10 (`TargetSourcedRemoteTest`) зелёный. R1-F2 закрыт для основного пути merge (fsm.py:282-285, `source_branch`), но три соседних сообщения в той же функции и `_auto_resolve_map_conflict` всё ещё несут литерал `config.MAIN_BRANCH` — см. новое замечание R3-F1 (minor, тот же класс, что и закрытый R1-F2, другие места). |

## Замечания

- major (carried, R2-F1, без изменений со времени заведения) — `tests/
  test_branch_freshness_gate.py`, `tests/test_merge_gate_ci_wait.py`,
  `tests/test_ci_status_kind_gate.py`, `tests/test_invariants.py`,
  `tests/test_fsm_merge_gate_done_snapshot.py` — ни один новый/изменённый
  в этой ветке тестовый метод не несёт докстринг-заявку `Ловит мутацию:
  …` (`skills/test-authoring.md`, конвенция с коммита `ec80cd60`,
  2026-09-02 — раньше SPEC этой задачи, `fdf31466`, 2026-09-04; проверено
  повторно: `grep -rn "Ловит мутацию" <эти 5 файлов>` — пусто). Без
  заявки ревьювер не может сверить чувствительность теста с конкретной
  правдоподобной поломкой (review-checklist, Фаза B п.3). Полный список
  задетых методов (имена и текущие строки подтверждены в рабочем
  дереве):
  - `tests/test_branch_freshness_gate.py:254` `BranchFreshnessGateTest::test_advance_pulls_main_and_advances_when_acceptance_green` (изменён)
  - `tests/test_branch_freshness_gate.py:305` `BranchFreshnessGateTest::test_freshness_check_never_defaults_base_to_local_pin` (новый, AC-4)
  - `tests/test_branch_freshness_gate.py:342` `BranchFreshnessGateTest::test_advance_treats_origin_fetch_failure_as_fresh` (новый, R1-F1)
  - `tests/test_branch_freshness_gate.py:541` `TargetSourcedRemoteTest::test_pull_freshness_fetches_target_url_not_pult_origin` (новый, AC-10)
  - `tests/test_merge_gate_ci_wait.py:256` `FreshPathDefersToWaitLoopTest::test_fresh_with_no_confirmed_note_returns_wait_without_polling_ci` (новый, AC-7)
  - `tests/test_ci_status_kind_gate.py:90` `NonRedStatusSkipsRerunTest::test_still_running_does_not_trigger_a_rerun` (изменён)
  - `tests/test_ci_status_kind_gate.py:101` `NonRedStatusSkipsRerunTest::test_unknown_status_does_not_trigger_a_rerun` (изменён)
  - `tests/test_invariants.py:597` `MergeNeedsGreenCiTest::test_no_merge_without_a_green_ci` (изменён)
  - `tests/test_invariants.py:636` `MergeNeedsGreenCiTest::test_the_refusal_names_the_reason_in_the_journal` (изменён)
  - `tests/test_fsm_merge_gate_done_snapshot.py:132` `DonePathSnapshotTest::test_done_transition_publishes_a_snapshot_like_killed_does` (изменён)
  - `tests/test_fsm_merge_gate_done_snapshot.py:174` `DonePathSnapshotTest::test_done_snapshot_removes_the_pult_artifact_branch` (изменён)

  Предложение (без изменений): добавить строку `Ловит мутацию: …` в
  докстринг каждого перечисленного метода — по образцу ретрофита
  `77c823a6` (`tests/test_amend.py`).

- minor (новое, R3-F1) — `orchestrator/fsm.py:116` (`_auto_resolve_map_conflict`,
  commit-сообщение авторазрешённого merge-конфликта карты),
  `orchestrator/fsm.py:278` (детейл эскалации «worktree не создан»),
  `orchestrator/fsm.py:300` (детейл эскалации «конфликт подтяжки»),
  `orchestrator/fsm.py:308-309` (детейл эскалации «приёмка красная после
  подтяжки») — все четыре места жёстко называют `config.MAIN_BRANCH` в
  пользовательском/журнальном тексте, хотя реальный источник подтяжки
  для не-self target'а — `source_branch` (например, `trunk`). R1-F2
  (итерация 1) закрыл ровно ЭТУ ЖЕ проблему только для одного места —
  сообщения успешного merge-коммита (fsm.py:283-285, `source_branch`
  уже вычислен и используется там) — но не применил тот же приём к
  соседним сообщениям в той же функции и к `_auto_resolve_map_conflict`,
  куда `source_branch`/`target_name` вовсе не передаётся параметром.
  Не влияет ни на один AC (SPEC «Не входит»: полный контур внешнего
  target'а — отдельная задача; сегодня единственный target — self, для
  которого `source_branch == config.MAIN_BRANCH` байт-в-байт, разницы в
  выводе нет). Вводит в заблуждение при чтении эскалаций/журнала для
  гипотетического внешнего target'а — тот же риск, что и у R1-F2.
  Предложение: `_auto_resolve_map_conflict` принимает `source_branch`
  параметром (вызывающий код на fsm.py:291 уже имеет `source_branch` в
  области видимости к моменту вызова); в fsm.py:278 вычислить
  `source = _origin_main_source(target_name)` до этой точки (сейчас
  считается только строкой ниже, на fsm.py:282) и использовать тот же
  `source_branch` во всех трёх местах вместо `config.MAIN_BRANCH`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R2-F1 | open | tests/test_branch_freshness_gate.py и ещё 4 файла (список выше) | Ни один новый/изменённый тест этой ветки не несёт докстринг-заявку `Ловит мутацию: …` | Ревьювер не может сверить чувствительность теста с конкретной заявленной мутацией (Фаза B п.3) | Добавить строку `Ловит мутацию: …` в докстринг каждого из 11 перечисленных методов |
| R3-F1 | open | orchestrator/fsm.py:116,278,300,308-309 | Тот же класс, что и закрытый R1-F2 (жёсткий литерал `config.MAIN_BRANCH` в тексте вместо `source_branch`), но в трёх эскалационных сообщениях и `_auto_resolve_map_conflict` — R1-F2 закрыл только сообщение успешного merge-коммита | Вводящий в заблуждение текст эскалации/журнала для гипотетического внешнего target'а (не влияет ни на один AC, self-target не затронут байт-в-байт) | Передать `source_branch` в `_auto_resolve_map_conflict` параметром; поднять вычисление `source`/`source_branch` в fsm.py выше первой точки использования (перед строкой 278); заменить литерал `config.MAIN_BRANCH` на `source_branch` во всех четырёх местах |

R1-F1 и R1-F2 (итерация 1) уже `accepted` — подтверждено повторно в
этом заходе прямым чтением кода (см. «Проверено исполнением»), в
таблицу не повторяю (кумулятивное правило: `accepted` записи
восстановимы из git-истории файла). R1-F2 закрыт для того ОДНОГО места,
которое он называл явно (merge-сообщение) — R3-F1 не переоткрывает
R1-F2, а заводит новую запись на соседние места того же класса, не
охваченные его формулировкой.

## Вердикт

changes_requested — один major (R2-F1, перенесён без изменений): нет
докстринг-заявки `Ловит мутацию: …` в 11 тестовых методах этой ветки.
Один minor (R3-F1, новый): три эскалационных сообщения и коммит
авторазрешения конфликта карты не подхватили `source_branch`,
введённый R1-F2 для соседнего места. Minor не блокирует, но входит в
тот же MR — по возможности исправить в этой же итерации.

## Проверено исполнением

- Обнаружено на входе: рабочее дерево несло непроиндексированные
  удаления всего `tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/` — восстановлено
  `git checkout -- tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/` (прецедент
  памяти), `git status` после — чисто.
- Ревью-пакет назвал sha `00e32aaf2c15059ffb72260275b29b9d2b53e8fe`
  «предыдущим вердиктом» — этот sha не существует в репозитории
  (`git cat-file -t` — fatal). Найдена фактическая история:
  `git log --oneline --all -- tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/REVIEW.md`
  показал 5 коммитов, включая `43d05b4e` с `iteration: 2` (реестр:
  R1-F1/R1-F2 → `accepted`, новый R2-F1 → `open`) — итерацию, которой НЕ
  было ни в ревью-пакете (там дан только iteration:1 как «предыдущая»),
  ни в истории текущей ветки задачи (`git merge-base --is-ancestor
  43d05b4e HEAD` → не предок). `git branch --all --contains 43d05b4e` →
  только `artifact/01m1nbwpknbxp9zxxqdjm7axpj` — коммит живёт на
  артефактной ветке, задачная ветка её не подтянула (тот же класс, что
  в памяти «tasks/<id>/ отсутствует во всей истории task-ветки», здесь —
  не файл целиком, а конкретная итерация REVIEW.md). Дальнейшее
  расследование (`git show 3b95c5a9 --name-status`, `git show
  7034d453 --name-status`, оба на артефактной ветке) показало: коммит
  `3b95c5a9` («артефакты шага developer») ИЗМЕНИЛ ТОЛЬКО REVIEW.md —
  откатил его текст обратно к содержимому итерации 1 (`iteration: 1` во
  фронтматтере), без единой правки кода/тестов; следующий `7034d453`
  («артефакты шага developer») — пустой коммит (0 файлов). То есть шаг
  developer после итерации 2 НЕ внёс правку R2-F1 в код и ПОТЕРЯЛ текст
  итерации 2 в REVIEW.md — регрессия того же класса, что и «регрессия
  №9» (роадмап, `9b4f4f09`), но на этот раз откату подвергся сам
  REVIEW.md шагом developer, а не правка Оператора. Вынесено в
  «Предложения системе». Итерация 3 этого REVIEW.md построена на
  восстановленном реестре итерации 2 (R1-F1/R1-F2 accepted, R2-F1 open,
  без изменений содержания) — не на стале-содержимом, которое лежало в
  рабочем дереве задачной ветки на входе.
- Независимая повторная проверка R1-F1/R1-F2 (не только доверие
  реестру итерации 2): прочитан `orchestrator/fsm.py:128-313`
  целиком — `_origin_main_source`, `_origin_main_sha`,
  `_pull_main_or_escalate`. Литерал `"FETCH_HEAD"` в сверке/merge
  отсутствует (`grep -n '"FETCH_HEAD"' orchestrator/fsm.py` — только
  строка 194, легитимное чтение результата собственного fetch).
  Merge-сообщение на fsm.py:285 использует `source_branch`, не литерал.
  Прочитан `orchestrator/fsm_merge_gate.py:255-313` — путь `"fresh"`
  возвращает `("wait", branch)` при `confirmed_ci_note is None`
  (строки 295-296), не опрашивает `ci.branch_status` сама; строки
  382-424 (внешний цикл `_cmd_approve_merge_gate_cycle`) не менялись —
  `MERGE_GATE_CI_WAIT_CEILING_SEC` читается тем же циклом, что и путь
  "pulled" (AC-6).
- Новое замечание R3-F1 найдено этим же чтением `fsm.py` целиком —
  `grep -n "MAIN_BRANCH" orchestrator/fsm.py orchestrator/fsm_merge_gate.py`
  показал все вхождения; строки 116/278/300/308-309 в `fsm.py`
  сверены построчно (`Read fsm.py` офсеты 85-130 и 263-315) — все три
  используют литерал там, где строкой ниже/выше уже есть готовый
  `source_branch`.
- `python3 -m unittest discover -s tests -q` — 1391 тест, `OK` (полный
  прогон, лог `Ran 1391 tests in 170.709s / OK`).
- `python3 -m unittest tests.test_branch_freshness_gate
  tests.test_fsm_map_conflict_autoresolve tests.test_gitcmd_branch_reads
  tests.test_merge_gate_ci_wait tests.test_ci_status_kind_gate
  tests.test_invariants tests.test_fsm_merge_gate_done_snapshot -v` — 92
  теста, `OK`.
- `python3 -m unittest discover -s
  tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests -p "test_ac*.py" -v`
  — 9 тестов (AC-1..AC-9), `OK`.
- `python3 scripts/codebase_map.py` (регенерация) — diff с
  закоммиченным `docs/codebase-map.md` отличается ТОЛЬКО строкой
  `built_at_sha`; карта не устарела по содержимому. Рабочее дерево
  возвращено `git checkout -- docs/codebase-map.md`.
- `python3 -c "sha256(...)"` над локальными `PLAN.md`/`SPEC.md` — байт-в-
  байт совпадают с описью ревью-пакета (16472/8838 байт, те же sha256):
  расхождение регрессии затронуло только REVIEW.md, не эти два файла.
- `git diff 58f1a582 HEAD -- orchestrator/fsm.py orchestrator/
  fsm_merge_gate.py orchestrator/gitcmd.py orchestrator/github_adapter.py
  orchestrator/targets.py <5 тестовых файлов из R2-F1>
  tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/ --stat` — пусто по задачным файлам
  (единственная неотносящаяся к задаче правка — `gitcmd.check_ignore`/
  `diff_names`, из другой задачи 01M1KVG3KSCY47HWXWF5HM0E76, влитой
  через «подтяжку main»): реализация этой задачи не менялась с коммита
  `58f1a582`, который закрыл R1-F1/R1-F2 в коде.

## Предложения системе

- Автокоммит шага `developer` (артефактная ветка
  `artifact/01m1nbwpknbxp9zxxqdjm7axpj`, коммит `3b95c5a9`) откатил
  REVIEW.md итерации 2 (реестр с `accepted`/`open`) обратно к тексту
  итерации 1, не внеся при этом ни одной правки кода — тот же класс
  бага, что и «регрессия №9» (роадмап `9b4f4f09`, откат правок
  Оператора автокоммитом роли), но здесь жертва — не операторская
  правка, а собственный артефакт роли reviewer предыдущего шага.
  Дополнительно эта же итерация ни разу не попала в задачную ветку
  (`task/01m1nbwpknbxp9zxxqdjm7axpj-...`) — ревью-пакет для итерации 3
  был собран так, будто итерации 2 не существовало вовсе (описал sha
  `00e32aaf...`, не существующий в репозитории, как «предыдущий
  вердикт»). Если бы ревьювер этого захода не сверил `git log --all`,
  замечание R2-F1 (major) было бы молча потеряно, а вердикт мог уйти в
  `approved` на основании самого свежего файла в рабочем дереве. Стоит
  завести отдельную задачу по сборке ревью-пакета: sha «предыдущего
  вердикта» обязан проверяться на существование в репозитории перед
  использованием, а не только в истории задачной ветки — сверка нужна
  и против артефактной ветки.
