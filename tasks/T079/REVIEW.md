---
task: T079
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 3
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: B1b: GitHub-адаптер, Draft-MR и состояние verifying

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (Draft MR на первый вход в in_dev, один на цикл) | OK | Не тронуто этой итерацией; закрыто и подтверждено в итерации 2. |
| 2 (undraft на входе в merge_gate) | OK | Не тронуто этой итерацией. |
| 3 (merge — побочный эффект локального push, не API-вызов) | OK | Не тронуто этой итерацией. |
| 4 (verifying между review и acceptance) | Реализовано верно, эскалация закрыта | Конфликт с `tests/test_invariants.py` (3 теста), открытый с итерации 1, разрешён: Оператор принял ADR-0009 (docs/adr/0009-verifying-route.md) и закоммитил маршрутно-агностичную форму трёх (фактически четырёх — пятая точка, verdict 4 в `CountersNeverResetTest`, поймана сверх минимального патча разработчика) правок теста НАПРЯМУЮ В MAIN (`33ea71e`, `b672c67`), а не в ветку задачи — правка `no_paths`-файла вне полномочий роли разработчика (ADR-0002), поэтому и обязана была прийти через main. Ветка забрала это через `git merge` («подтяжка main», `bf3830d`). Полный юнит-сьют — 0 красных (было 3). Локед `test_ac4_review_to_verifying.py` по-прежнему проверяет, что один `advance` из `review` с approved+зелёным CI останавливается в `verifying` — старое поведение «review→acceptance за один шаг» не вернулось; временная route-agnostic форма трёх инвариант-тестов допускает оба маршрута ровно до этого MR (ADR §3), это операторское решение вне зоны review разработчика. |
| 5 (четыре исхода статуса CI в verifying) | OK | Не тронуто этой итерацией. |
| 6 (потолок ожидания → escalated) | OK | Не тронуто этой итерацией. |
| 7 (красный CI не выталкивает автоматически) | OK | Не тронуто этой итерацией. |
| 8 (reject расширен на verifying) | OK | Не тронуто этой итерацией. |
| 9 (механизм периодического вызова advance вне объёма) | OK | Не тронуто этой итерацией. |

## Замечания

Замечаний нет.

Проверено, что diff этой итерации (`git diff 8dacdc32...HEAD`) ограничен
двумя файлами — `docs/adr/0009-verifying-route.md` и
`tests/test_invariants.py` — и что вклад именно ветки задачи (не main)
в оба этих файла равен нулю: `git merge-base main
task/t079-b1b-github-adapter-draft-mr-i` == `git rev-parse main` ==
`b672c677dc913d5bd580c44f4a109c57ed298b54`, т.е. main целиком —
предок ветки, расхождений с main нет вообще (`git diff main
task/t079-b1b-github-adapter-draft-mr-i -- tests/test_invariants.py
docs/adr/0009-verifying-route.md` — пусто). Единственная попытка
править `tests/test_invariants.py` НЕПОСРЕДСТВЕННО в ветке
(`d064d09`, до правильного решения через main) была тем же процессом
самостоятельно распознана как нарушение `no_paths`/ADR-0002 и
полностью отменена (`8260472`, `git show 8260472 --stat` — чистые
10 удалённых строк, ровно откат `d064d09`) ещё до финального мержа
main — в текущем HEAD её следов нет. AC-14 не нарушен.

## Вердикт

approved — единственная открытая эскалация (конфликт требования 4
с тремя тестами `tests/test_invariants.py`) закрыта операторским
ADR-0009 через коммиты в main, подтянутые в ветку мержем, без единой
правки `no_paths`-файлов силами роли разработчика. Полный юнит-сьют
и локед `acceptance_tests` зелёные без исключений (впервые за все три
итерации — 0 красных). Код `orchestrator/` не менялся с итерации 2
(diff этой итерации — только ADR-документ и подтянутый из main тест).

## Проверено исполнением

- `git status` — ветка чистая, HEAD `bf3830d` («T079: подтяжка main»),
  merge двух родителей: `8260472` (тип задачи) и `b672c67` (main,
  ADR-0009 Оператора).
- `git merge-base main task/t079-b1b-github-adapter-draft-mr-i` =
  `git rev-parse main` = `b672c677dc913d5bd580c44f4a109c57ed298b54` —
  main целиком содержится в ветке, независимых от main правок
  `tests/test_invariants.py`/`docs/adr/0009-verifying-route.md` в
  текущем HEAD нет; `git diff main task/t079-b1b-github-adapter-draft-mr-i
  -- tests/test_invariants.py docs/adr/0009-verifying-route.md` — пусто.
- `git log -1 --format='%P' bf3830d` → `8260472 b672c67` (merge-коммит,
  не переигранные коммиты); `git show 8260472 --stat` — 10 строк
  удалено, ровно откат ранее ошибочно закоммиченной в ветку правки
  `d064d09`, до финального мержа.
- `python3 -m unittest discover -s tests` — 1068 тестов, **0 красных**
  (в итерациях 1-2 было 3: `test_invariants.CountersNeverResetTest::
  test_no_transition_of_the_full_cycle_resets_a_counter`,
  `FreshVerdictGuardsAcceptanceTest::
  test_escalation_and_return_do_not_make_the_verdict_fresh`,
  `FreshVerdictGuardsAcceptanceTest::
  test_every_return_to_dev_requires_a_new_verdict`) — все три теперь
  зелёные благодаря ADR-0009-правке в main.
- `cd tasks/T079/acceptance_tests && python3 -m unittest discover -s .
  -p "test_*.py"` — 19/19 зелёные (AC-1..AC-14, включая AC-4).
- `python3 -m unittest tests.test_merge_lock tests.test_advance_guard
  tests.test_fsm_draft_mr_reentry` — 23/23 зелёные (T052/T053 не
  задеты, AC-13; Draft MR на всех точках входа — не регрессировало).
- `git diff main --stat -- gates.yaml roles.yaml targets.yaml .github/
  templates/ skills/ docs/invariants.md tests/test_invariants.py
  CLAUDE.md` — пусто относительно ТЕКУЩЕГО main: ни один путь
  `no_paths` target `artel` веткой не тронут (AC-14 подтверждён заново,
  не просто унаследован из итерации 2, т.к. main с тех пор продвинулся).
- `python3 scripts/codebase_map.py` (регенерация вручную, отменена
  `git checkout -- docs/codebase-map.md`) — diff свёлся только к строке
  `built_at_sha`, содержимое карты без sha идентично закоммиченному —
  регенерация не устарела.
- Прочитан `docs/adr/0009-verifying-route.md` целиком и diff-хунк
  `tests/test_invariants.py` (4 места: 3 в
  `FreshVerdictGuardsAcceptanceTest`, 2 в одном методе
  `CountersNeverResetTest` — verdict 3 и verdict 4) — форма `if
  self.state() == "verifying": <ещё один advance>` перед финальным
  `assertEqual(state, "acceptance")` корректно допускает оба маршрута
  и не смягчает исходную охраняемую семантику (свежесть вердикта,
  несбрасываемость счётчиков) — меняется только число шагов, как и
  описано в ADR §2.

## Предложения системе

Нет новых сверх уже зафиксированных в PLAN.md и REVIEW.md итераций 1-2.
Отдельно стоит отметить как удачный прецедент (не проблему): попытка
поправить `no_paths`-файл прямо в ветке задачи (`d064d09`, метка
«правка Оператора» в сообщении коммита) была распознана и полностью
отменена (`8260472`) ДО того, как ушла на ревью, а верная версия той
же правки уехала через main — процесс самокорректировался без участия
ревьювера. Стоит проговорить этот кейс в скиле, отвечающем за операторские
правки `no_paths` (или в ADR-0002), как канонический пример: «правка
`no_paths`, инициированная решением по эскалации — всегда коммит в
main, попытка закоммитить её в ветку задачи ловится и откатывается
до подачи на ревью».
