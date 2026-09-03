---
task: 01M1H224X5A8W159MKF1Q24R5Y
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 3
---

# REVIEW: A7 — артель как внешний target: пин версии, шаг обновления, внешний флоу

## Фаза A — проверка плана

Пакет ревью нёс инкрементальный diff «от sha предыдущего вердикта
(`00bd2fa`) до HEAD» — это не коммит вердикта итерации 1: сам
`00bd2fa` («подтяжка main») лежит на 46+ коммитов ПОЗЖЕ настоящего
коммита вердикта. Реальный коммит вердикта итерации 1 найден вручную
(`git log --oneline -- tasks/01M1H224X5A8W159MKF1Q24R5Y/REVIEW.md`):
`8f1350a` («ревью итерация 1 — changes_requested»). Пересчитан полный
diff `8f1350a...HEAD` — именно он лежит в основе этой Фазы A и Фазы B
ниже (см. «Предложения системе» — стоит доложить о классе).

PLAN.md с прошлой итерации не менялся по существу подхода/шагов —
только раздел «Эскалация» пополнился тремя циклами разрешения
(role_cwd, checkpoint-источник, опечатка в test_ac7) и их сжатием
ради потолка ёмкости diff (без потери содержания — commit hash-и
каждой сессии сохранены). Покрытие требований и структура шагов не
изменились относительно оценки итерации 1 (полна, шаги крупные, но
это уже разрешено Оператором отдельно, коммит `e34d048`) — повторно
не переоцениваю.

Главный вопрос Фазы A этой итерации — закрыт ли blocker R1-F1 по
существу (не только по заявлению разработчика). Ответ — да, см. Фазу B
и реестр ниже: правка `role_cwd` возвращает self-ветку buквально к
виду ДО генерализации (сверено построчно с `git show
<merge-base>:orchestrator/runner.py`, совпадает), это не новая
конструкция, а откат уже проверенного временем кода — риск регрессии
минимален.

**Независимая переверка (новая сессия ревьювера).** Ревью-пакет этой
сессии нёс инкрементальный diff «от sha предыдущего вердикта
(`7451fa2`) до HEAD» — на этот раз sha в пакете корректен (это и есть
настоящий коммит текущего вердикта, `git log --oneline -- .../REVIEW.md`
подтверждает: `7451fa2` — верхний), а сам diff пуст: ветка не менялась
ни на байт с момента предыдущего `approved`. В отличие от прежних
прецедентов (T082, T087, и запись «Предложения системе» ниже про
`00bd2fa`), здесь генератор пакета сработал верно — стоит иметь в виду
как контрпример при разборе логики выбора базового sha. Пустой
инкрементальный diff не принят на веру (review-checklist:
«пустой не значит без изменений») — самостоятельно проверено: `git
rev-parse HEAD` == `7451fa2e649dfdd6569bddcf801962c14e502671` (ровно та
же sha, что и база пакета), `git status --short` пусто. Раз дифа нет,
Фаза A/Фаза B этой сессии — не переоценка нового кода (его нет), а
самостоятельное, с нуля, воспроизведение всех проверок предыдущей
итерации на неизменном коде: результаты см. «Проверено исполнением»
ниже, они byte-for-byte согласуются с зафиксированными прошлой сессией
(другие тайминги, тот же исход). Выводы Фазы A/Фазы B/реестра/вердикта
ниже не переписаны заново — они уже верны и независимо
переподтверждены.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (targets.yaml обычная запись) | OK | без изменений с итерации 1 |
| 2 (generic-логика вместо догфуд-веток) | OK | `role_cwd` для self/артели восстановлен на `workspace.ensure` (пересмотр планки Оператором 03.09, ADR-0012, коммит `ac9ee11`) — это НЕ откат генерализации требования 2 целиком: требование 2 признано относящимся к АРТЕФАКТАМ (M1/Б₃), не к коду; для кода self структурно нет отдельного клона (тот же класс исключения, что уже сделан PLAN'ом для гейта ёмкости/`_pull_main_or_escalate`, теперь явно распространён и на `role_cwd`). Все 5 остальных generic-подсистем (doctor/catalog/fixation/cleanup/`checkpoint` для внешнего target) не тронуты этим откатом |
| 3 (новые задачи артели — M1/Б₃) | OK | без изменений с итерации 1 |
| 4 (Stage0 — пин) | OK | без изменений с итерации 1 |
| 5 (Stage1 — шаг обновления) | OK | без изменений с итерации 1 |
| 6 (журнал обновления пина) | OK | без изменений с итерации 1 |
| 7 (защищённые пути в MR) | OK | `_touched_protected_paths` снова видит ветку задачи — восстановленный `role_cwd` даёт ей общую объектную базу с `config.ROOT` (git worktree всегда делит `.git`); `github_adapter.py` не менялся в диффе с итерации 1 — фикс целиком в `role_cwd`, downstream починился транзитивно |
| 8 (полный внешний флоу без записи в кодовые ветки/main) | OK | подтверждено сквозным регресс-тестом `tests/test_step_autocommit.py::RoleCwdVsCommitSourceGapTest`, который пишет артефакт через НАСТОЯЩИЙ `runner.role_cwd()` (не хардкод пути, как остальные тесты того же файла) — раньше был `@unittest.skip` с доказанным расхождением, теперь расскипан и зелёный (`checkpoint.py` девятый потребитель `role_cwd` синхронизирован, коммит по мандату `9a984c3`); залоченный `test_ac7_full_scenario_no_pult_writes.py` дочитывает тот же адрес (`workspace.path(task_id)`, коммит `6859d12`) |

## Замечания

Пусто — 0 blocker/major. Замечания R1-F1 (blocker) и R1-F2 (major)
итерации 1 закрыты по существу, см. реестр.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/runner.py:379-401 | `role_cwd` для target==DEFAULT_TARGET (артель) возвращал `.artel/projects/artel/workspace` вместо ветки задачи внутри `config.ROOT`, разрывая связь с гейтами/merge/Draft-MR | реальная (не тестовая) новая задача артели не проходила дальше первого агентного шага | Подтверждаю закрытие. Правка (коммит на HEAD, PLAN.md «Разрешение эскалации: role_cwd generic-путь») возвращает self-ветку: `branch = store.task_branch(...)`, `workspace.ensure(task_id, branch)` — byte-for-byte совпадает с кодом до A7 (сверено `git show <merge-base>:orchestrator/runner.py`). Проверил все 8 пунктов исходного замечания по коду и/или тестам: (1-2) push/ensure_head_in_origin — worktree делит объектную базу с `config.ROOT`, ветка снова видна `gitcmd.git()`; (3) `_touched_protected_paths` — то же; (4) плотницкий merge (`fsm_merge_gate.py`) — `git -C <scratch> merge --no-ff <branch>` резолвит ветку в общей объектной базе; (5) `_capacity_gate_refuses` — прогон `tests/` этой сессией не воспроизводит прежний класс отказа (`fatal: bad revision`), полный набор зелёный; (6) `_pull_main_or_escalate` — `workspace.ensure` снова заводит worktree из `config.ROOT`; (7) три WIP-чекпоинта `checkpoint.py` — коммитят `workspace.path(task_id)`, тот же адрес, что теперь возвращает `role_cwd`; (8) осиротевшая проверка `runner.py:158-168` (`on_task_branch`) — комментарий и код над ней (строки 152-168) снова описывают действительное поведение, не расходятся. Ни один из 8 пунктов не остался открытым. Независимо: `python3 -m unittest discover -s tests -q` — `Ran 1306 tests in 137.075s`, `OK`; `python3 -m unittest tests.test_invariants -v` — `Ran 40 tests`, `OK` (инварианты 12/19 не задеты откатом) |
| R1-F2 | accepted | tasks/01M1H224X5A8W159MKF1Q24R5Y/acceptance_tests/test_ac7_full_scenario_no_pult_writes.py и соседние AC-6/8/9/12/15 | приёмочные тесты полного флоу заводили кодовую ветку задачи вручную, в обход `runner.cmd_run -> role_cwd` — не ловили R1-F1 | AC-7/AC-8/AC-9/AC-12/AC-15 давали ложную уверенность | Подтверждаю закрытие. Регресс-тест `tests/test_step_autocommit.py::RoleCwdVsCommitSourceGapTest` добавлен и сделал ровно то, что от него требовалось: поймал НОВОЕ расхождение (`checkpoint._commit_external_step_artifacts` для self остался захардкожен на старый адрес после восстановления `role_cwd`) — не формальная галочка, а реально сработавшая находка. Расхождение закрыто (`checkpoint.py` строка ~231: `if target == config.DEFAULT_TARGET: workspace_root = workspace.path(task_id)`), тест расскипан и зелёный (проверено — `grep -rn "unittest.skip" tasks/.../acceptance_tests tests/test_step_autocommit.py` пусто). Залоченный `test_ac7...` и `CheckpointCommitsToArtifactBranchForArtelTest` синхронизированы с тем же адресом (коммиты `9a984c3`, `6859d12`, оба по каналу ADR-0012) — проверил построчно оба диффа, суть теста (АС-7/АС-6: `tasks/<id>/` не попадает в кодовую ветку/main) не изменилась, менялся только адрес каталога-источника |

## Вердикт

`approved`. Обе записи реестра итерации 1 закрыты по существу (не
только по заявлению — проверено построчным чтением диффа `role_cwd`/
`checkpoint.py`, чтением диффов обоих залоченных тестов и живым
прогоном полного `tests/`/`acceptance_tests/`). Новых blocker/major не
найдено. Требования SPEC 1-8 (AC-1..AC-17) реализованы, инварианты
12/19/T056 не ослаблены (проверено отдельным прогоном
`tests.test_invariants`, T056-тест не тронут диффом с итерации 1).

Независимо переподтверждено новой сессией ревьювера (ветка не менялась
с момента этого вердикта — инкрементальный diff пуст, см. Фазу A):
тот же вывод, та же нулевая полка blocker/major, тот же реестр —
изменений в вердикт эта переверка не вносит.

## Проверено исполнением

- `git log --oneline -- tasks/01M1H224X5A8W159MKF1Q24R5Y/REVIEW.md` —
  нашёл настоящий коммит вердикта итерации 1 (`8f1350a`), т.к. sha в
  пакете (`00bd2fa`) оказался поздней «подтяжкой main», не вердиктом
  (см. Фазу A).
- `git diff --stat 8f1350a...HEAD` (без PLAN.md/REVIEW.md) — 8 файлов,
  +194/-95: `orchestrator/runner.py`, `orchestrator/checkpoint.py`,
  залоченные `test_ac6_artifacts_via_m1_mechanics.py`/
  `test_ac7_full_scenario_no_pult_writes.py`,
  `tests/test_multitarget_invariants.py`,
  `tests/test_step_autocommit.py`, `docs/codebase-map.md`,
  `docs/roadmap.md` (последний — не задачи, чужой коммит `7fd63ef`).
  Прочитаны все диффы целиком, не только hunk-заголовки.
- `python3 -m unittest discover -s tests -q` — `Ran 1306 tests in
  137.075s`, `OK` (exit code 0, 0 skipped) — совпадает с заявленным
  разработчиком.
- `python3 -m unittest discover -s tasks/01M1H224X5A8W159MKF1Q24R5Y/acceptance_tests -p 'test_*.py' -q`
  — `Ran 44 tests in 18.708s`, `OK` — включая починенный
  `test_ac7_full_lifecycle_never_writes_task_dir_to_code_or_main` и
  `CheckpointCommitsToArtifactBranchForArtelTest`.
- `python3 -m unittest tests.test_invariants -v` — `Ran 40 tests`,
  `OK` — отдельная точечная проверка AC-15 (инварианты 12/19), т.к.
  R1-F1 менял self-путь, соседний с механикой merge_gate.
- `python3 scripts/guard.py tasks/01M1H224X5A8W159MKF1Q24R5Y/{SPEC,PLAN,REVIEW,ANSWER-1}.md`
  — `GUARD: ок (4 файлов)`.
- `python3 scripts/codebase_map.py` (контрольный прогон) — содержимое
  карты не изменилось (сравнение без строки `built_at_sha`), откатил
  правку (`git checkout -- docs/codebase-map.md`) — регенерация не
  нужна, `*.py` с последнего коммита карты не менялся.
- `git status --short` — рабочее дерево чистое до и после проверки.
- `git diff main...HEAD --stat -- .github/ gates.yaml roles.yaml
  skills/ templates/ scripts/guard.py docs/adr/` — пусто: ни один
  защищённый путь не задет всей веткой целиком.
- Прочитаны диффы построчно: `orchestrator/runner.py::role_cwd` (сверен
  byte-for-byte с версией до A7 через `git show <merge-base>:...`),
  `orchestrator/checkpoint.py::_commit_external_step_artifacts`,
  `test_ac6_artifacts_via_m1_mechanics.py`,
  `test_ac7_full_scenario_no_pult_writes.py`,
  `tests/test_multitarget_invariants.py`,
  `tests/test_step_autocommit.py` (включая новый
  `RoleCwdVsCommitSourceGapTest`).
- Точечно прочитаны `orchestrator/runner.py:140-179` (окружение вызова
  `role_cwd` в `_cmd_run`) и `orchestrator/checkpoint.py:1-152` (три
  WIP-чекпоинта) — проверить, что осиротевшая проверка `on_task_branch`
  и WIP-чекпоинты (пункты 7-8 исходного R1-F1) снова согласованы с
  восстановленным `role_cwd`, не только сам факт возврата пути.

**Независимая переверка этой сессии (новый ревьювер, тот же HEAD
`7451fa2`, инкрементальный diff пуст):**
- `git rev-parse HEAD` — `7451fa2e649dfdd6569bddcf801962c14e502671`,
  совпадает с базой пакета; `git status --short` — рабочее дерево
  чистое до и после проверки.
- `git diff --stat 8f1350a...HEAD` (без PLAN.md/REVIEW.md) — те же 8
  файлов, +194/-95, что и в предыдущей сессии; прочитаны целиком
  диффы `orchestrator/runner.py::role_cwd`,
  `orchestrator/checkpoint.py::_commit_external_step_artifacts`,
  обоих залоченных приёмочных тестов
  (`test_ac6_artifacts_via_m1_mechanics.py`,
  `test_ac7_full_scenario_no_pult_writes.py`) и
  `tests/test_multitarget_invariants.py`/`tests/test_step_autocommit.py`
  — подтверждаю построчно то же самое, что зафиксировано в реестре
  ниже (self-ветка `role_cwd` byte-for-byte как до A7; источник
  `_commit_external_step_artifacts` синхронизирован на
  `workspace.path(task_id)`; регресс-тест
  `RoleCwdVsCommitSourceGapTest` зелёный без skip).
- `python3 -m unittest discover -s tests -q` — `Ran 1306 tests in
  132.518s`, `OK` (exit code 0, 0 skipped).
- `python3 -m unittest discover -s tasks/01M1H224X5A8W159MKF1Q24R5Y/acceptance_tests -p 'test_*.py' -q`
  — `Ran 44 tests in 18.754s`, `OK` (44/44).
- `python3 scripts/guard.py` на SPEC.md/PLAN.md/REVIEW.md/ANSWER-1.md
  — `GUARD: ок (4 файлов)`.
- `python3 scripts/codebase_map.py` (контрольный прогон) — diff
  содержимого без строки `built_at_sha` пуст, регенерация не нужна;
  правка отменена (`git checkout -- docs/codebase-map.md`), т.к. `*.py`
  этой сессией не менялся.
- `git diff main...HEAD --stat -- .github/ gates.yaml roles.yaml
  skills/ templates/ scripts/guard.py docs/adr/` — пусто: защищённые
  пути не задеты.
- `git diff main...HEAD | wc -c` — 603638 байт, в пределах потолка
  `REVIEW_SNAPSHOT_DIFF_MAX_BYTES = 614_400` (запас ~10.7 КБ).
- `grep -n "Ловит мутацию" tasks/.../acceptance_tests/test_ac6_....py`
  — заявки на месте у изменённых методов теста (T023-конвенция);
  developer-тесты в `tests/` заявку не несут, что ожидаемо: конвенция
  `skills/test-authoring.md` адресована test_author/`acceptance_tests/`,
  для `tests/` действует `skills/coding-standards.md` (докстринг —
  сценарий и наблюдаемое свойство, без обязательной заявки о мутации);
  докстринги изменённых developer-тестов (`test_dogfood_cwd_is_its_worktree`,
  `RoleCwdVsCommitSourceGapTest`) содержательны, не пересказ имени.

## Предложения системе

- Инкрементальный diff пакета ревью снова указал на устаревший sha
  (Фаза A) — та же механика, что уже дважды подтверждена (T082, T087,
  см. review-checklist). Здесь новый вариант причины: sha в пакете
  оказался коммитом, лежащим ПОЗЖЕ настоящего вердикта на 46+
  коммитов (не «раньше», как в описанных прецедентах) — видимо,
  инструмент сборки пакета берёт sha по какому-то другому маркеру
  (возможно, «последний коммит, где статус PLAN.md стал ready», а не
  «коммит, где REVIEW.md получил свой предыдущий status»). Стоит
  проверить логику выбора базового sha в генераторе ревью-пакета.
- `orchestrator/checkpoint.py:62-64` (докстринг `commit_timeout_checkpoint`)
  несёт устаревшее утверждение «Пока `targets.yaml` объявляет только
  догфуд ... эта ветка не задета вживую» — ложно с момента AC-1 этой
  же задачи (`targets.yaml` объявляет `artel` обычным target). Не
  влияет на поведение (сам код self-ветки корректен и восстановлен),
  чисто документационный долг — не блокирую approved этим (severity
  ниже minor: ни один тест, ни одна проверка на него не опирается), но
  стоит поправить при следующей точечной правке этого файла, чтобы не
  вводить будущего читателя в заблуждение о «мёртвости» этой ветки.
- `orchestrator/config.py::REVIEW_SNAPSHOT_DIFF_MAX_BYTES` временно
  поднят Оператором (614400, коммит `e34d048`) под объём именно этой
  задачи — PLAN.md сам напоминает вернуть потолок после мержа
  («Примечание для мержа»); дублирую здесь для видимости на
  merge_gate/T042-регене, чтобы напоминание не потерялось в объёмном
  PLAN.md. Запас на HEAD этой сессии — ~10.7 КБ (`git diff main...HEAD`
  603638 байт из 614400) — почти исчерпан; любая новая правка в ветке
  до мержа рискует снова упереться в потолок.
- Контрпример к предыдущей записи о неверном sha инкрементального
  diff (T082/T087 и запись выше про `00bd2fa`): в пакете ЭТОЙ сессии
  sha базы (`7451fa2`) оказался верным — совпал с настоящим коммитом
  вердикта. Стоит учитывать оба случая (иногда база верна, иногда нет)
  при разборе логики генератора пакета — она не сломана постоянно,
  скорее нестабильна в конкретных сценариях (возможно, зависит от того,
  менялось ли что-то в ветке между вердиктом и следующим запуском
  ревью).
