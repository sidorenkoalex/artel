---
task: 01M46D5ZZQY7GBEW5TBVQ0P3ZV
type: plan
author_role: developer
status: escalate
schema_version: 5
---

# PLAN: Статус CI называет событие прогона (push / pull_request)

## Подход
Всё в `orchestrator/ci.py`. Событие и номер прогона check-run не несёт —
их отдаёт `gh api repos/{owner}/{repo}/actions/runs?head_sha=<sha>` (тот
же запрос, что у `find_run_id`). Новый помощник `_commit_workflow_runs(sha)`
читает прогоны коммита и строит индекс: `check_suite_id` → прогон и `id`
прогона → прогон. Check-run сопоставляется со своим прогоном по
`check_suite.id`, запасной путь — id прогона из `details_url`/`html_url`
(`…/actions/runs/<id>/job/<id>`). Подпись проверки — «(<событие>, прогон
<id прогона>)»; не сопоставилась или запрос прогонов не удался —
«(событие не определено)» (с «прогон <id>», если id известен из ссылки).

Ключевые решения:
- Прогоны спрашиваются только на не-зелёном исходе (зелёный текст и число
  запросов на нём — «Не входит» SPEC) и только если хоть один check-run
  коммита несёт связку с прогоном (`check_suite.id` или ссылку на прогон):
  без связки сопоставлять нечего, исход «событие не определено» тот же, а
  существующие тесты, подменяющие `check_runs` без `gh`, не уходят в
  настоящий `gh`.
- Сбой запроса прогонов не меняет исход (fail-closed, как сегодня): текст
  тот же, у проверок пометка «событие не определено».
- Фраза о расхождении (AC-6): по каждому имени проверки — события, в
  прогонах которых она исполнилась зелёной (`GREEN` без `skipped`), и
  события, где красная; есть пара различных — фраза «исход по событиям
  расходится: <имя> — зелёная в <события>, красная в <события>». Ставится
  в первой строке после перечня (её показывают все потребители), в
  тексте нет подстрок, на которых стоят разборщики («не зелёный:», «ещё
  идёт», «неизвестен», «check-run id»).
- `main_line_status`: поля `failed`/`running` `MainLineStatus` не
  меняются; подписи строятся отдельно для каждого коммита линии, где
  проверка упала или идёт (запрос прогонов — по этому коммиту, с кэшем на
  коммит), только после обхода линии.
- Форма текстов: красный — «<имя>=<заключение> (<событие>, прогон <id>)»
  по каждому check-run'у; идущий — «<имя> (<событие>, прогон <id>)»;
  зависший — «<имя> (check-run id N, status=S; <событие>, прогон <id>)
  висит …» (номер прогона не в форме «check-run id», `stuck_check_ids`
  его не возьмёт); main — «<имя>=<заключение> на <sha> (<событие>, прогон
  <id>)» / «<имя> на <sha> (…)». Префиксы «CI коммита <sha> не зелёный:» /
  «ещё идёт:» / «main красный с» не меняются — `red_status_sha`,
  `verifying_is_red`, `status_kind` работают как прежде.

Бюджет SPEC ($40) не пересматривается.

## Шаги
1. `orchestrator/ci.py`: `_commit_workflow_runs`, сопоставление
   check-run → прогон, подпись, фраза расхождения; подключение в
   `verifying_status` (красный, «ещё идёт», «зависла»), `branch_status`
   (красный, «ещё идёт»), `main_line_status`/`_main_line_note` (красный,
   «проверки ещё идут»). Юнит-тесты в `tests/test_ci_status.py`
   (недостающие свойства: запасной путь по `details_url`, отсутствие
   запроса прогонов на зелёном исходе и без связки). Регенерация карты
   `python3 scripts/codebase_map.py`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (событие и номер у упавших/идущих: verifying/branch/main) | 1 |
| 2 (фраза о расхождении исхода по событиям) | 1 |
| 3 (сбой запроса прогонов — «событие не определено», исход тот же) | 1 |
| 4 (разборщики текста работают с новым текстом) | 1 |
| 5 (тесты с заявками «Ловит мутацию») | 1 (долгоживущий `tests/test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py` + свои тесты) |

## Влияние на систему
- Потребители текста статуса (гейт мержа, `auto`, `ci-rerun`, `watch`,
  `pin-update`, `doctor`) не правятся: исходы (`VERIFYING_*`, `bool`,
  `kind`, поля `MainLineStatus`) те же, префиксы, на которых стоят
  разборщики, те же.
- Инвариант 19 (неизвестное не зелёное) не затронут: событие — только
  подпись; зелёность решается check-run'ами, как раньше.
- На не-зелёном исходе — плюс один запрос `gh api …/actions/runs` на
  коммит (на main — на каждый коммит с упавшей/идущей проверкой).
  Зелёный путь запросов не прибавляет.
- Существующие тесты не ослабляются и не меняются: прежние проверки —
  `assertIn` по подстрокам, которые остаются.
- Откат — revert одного коммита задачи.

## Риски
- Подписи на main при нескольких одноимённых прогонах на одном коммите —
  перечисляются все упавшие/идущие прогоны этой проверки через «; » в
  одних скобках.
- `CI_RUNS_PER_PAGE` = 10: прогонов на коммите больше (много workflow) —
  часть проверок останется «событие не определено» (с номером прогона из
  ссылки), исход тот же.

## Проверка
- `tests/test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py` (долгоживущий,
  не правился): 8 passed, 29 subtests.
- `tests/test_ci_status.py` (с новым классом `RunEventLabelTest`, 4
  метода): 77 passed; каждый из 4 новых методов краснеет на своей
  заявленной мутации (временная правка `ci.py`, возвращена).
- `tests/test_ci_stuck_check_run.py`, `test_main_ci_line.py`,
  `test_main_ci_fetched_repo.py`, `test_01m3y75c9ty76083cg1pk00em4_stuck_check.py`,
  `test_ci_status_kind_gate.py`, `test_merge_gate_ci_wait.py`,
  `test_ci_rerun_command.py`, `test_verifying_ceiling.py`,
  `test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`, `test_github_adapter.py`
  — зелёные, кроме 19 методов `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`
  и `tests/test_main_ci_line.py::FixesMainArgTest`: они падают отказом
  «artel.py approve/pin-update: команда недоступна процессу роли
  developer» и падают так же на базе (`ci.py` HEAD) — окружение шага
  роли, не правка; в CI они идут вне окружения роли.
- `plank-run 01M46D5ZZQY7GBEW5TBVQ0P3ZV` — «планки нет … нет файлов
  test_*.py»: вся планка задачи — долгоживущий файл в `tests/`, он
  прогнан напрямую (выше).
- Карта регенерирована: `python3 scripts/codebase_map.py`.

## Возврат из verifying: адреса DNS в tests/
- `tests/test_ci_status.py:1036` (мой тест `RunEventLabelTest.linked`):
  `https://github.com/o/r/actions/runs/` → `http://127.0.0.1/o/r/actions/runs/`.
  Только строковый литерал; `orchestrator/ci.py::_RUN_URL_RE` (`ci.py:319`)
  хост не разбирает. После правки файл в нарушителях инварианта не значится;
  `tests/test_ci_status.py` + долгоживущий — 85 passed, 60 subtests.
- `tests/test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py` — долгоживущий файл
  задачи под суммой `acceptance_tests/long_lived.sha256.txt` (70267394…):
  его правка разработчиком отказывается гейтом лока, канал — `amend-tests`.
  Не правлен, см. «Эскалация». Правка проверена временно (возвращена
  `git checkout`): с ней `test_no_dns_hostname_addresses_in_tests_tree` —
  passed, долгоживущий файл — 8 passed, 29 subtests.

## Предложения системе
- Причина возврата из `verifying` предписала разработчику править
  долгоживущий файл задачи, хотя он под локом сумм — возврат с такой
  правкой стоит сразу направлять в `amend-tests`, а не разработчику.
- Автор тестов написал фикстуру с `https://github.com/…` в `tests/`:
  инвариант адресов не проверяется на выходе `tests_writing`, и нарушение
  всплыло только в CI на `verifying`.
- `orchestrator/plank_run.py`: при планке только из долгоживущей группы
  (`tests/test_<id>_*.py`) `plank-run` отказывает «планки нет», хотя
  планка есть — разумно прогонять долгоживущие файлы перечня
  `long_lived.sha256.txt`.
- Тесты, гоняющие CLI пульта (`tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`,
  `FixesMainArgTest`), в шаге роли падают на отказе команд процессу роли —
  разработчик не может прогнать затронутый модуль целиком; их стоит
  изолировать от признака шага роли в песочнице.

## Эскалация
**Вопросы**
1. (блокирует) Долгоживущий файл `tests/test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py`
   нарушает инвариант `tests/test_invariants.py::NoNetworkAddressesInTestsTest::test_no_dns_hostname_addresses_in_tests_tree`
   тремя адресами фикстуры (строки 152, 176, 197). Файл под суммой лока —
   разработчик его не правит. Варианты: (а) Оператор применяет правку ниже
   командой `amend-tests` (меняются только строковые литералы адресов, ни
   одного assert и ожидаемого значения); (б) разрешить разработчику правку
   с перефиксацией суммы иным путём. Дефолт — (а).

Правка для `amend-tests` (проверена: 8 passed, 29 subtests; инвариант — passed):

```diff
--- a/tests/test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py
+++ b/tests/test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py
@@ -149,7 +149,7 @@ class FakeGitHub:
                 conclusion, age = None, config.CI_STUCK_CHECK_MINUTES + 30
             else:
                 status, conclusion, age = "completed", state, 3
-            url = (f"https://github.com/{OWNER_REPO}/actions/runs/{run_id}"
+            url = (f"http://127.0.0.1/{OWNER_REPO}/actions/runs/{run_id}"
                    f"/job/{check_id}")
             created.append({
                 "id": check_id, "name": name, "status": status,
@@ -173,7 +173,7 @@ class FakeGitHub:
             "head_branch": "main", "run_number": self.rng.randint(1, 9999),
             "run_attempt": 1, "check_suite_id": suite,
             "status": run_status, "conclusion": run_conclusion,
-            "html_url": f"https://github.com/{OWNER_REPO}/actions/runs/{run_id}",
+            "html_url": f"http://127.0.0.1/{OWNER_REPO}/actions/runs/{run_id}",
             "_checks": created,
         }
         self.runs.append(run)
@@ -194,7 +194,7 @@ class FakeGitHub:
                 "started_at": check["started_at"],
                 "completed_at": check["completed_at"],
                 "html_url": check["html_url"],
-                "check_run_url": (f"https://api.github.com/repos/{OWNER_REPO}"
+                "check_run_url": (f"http://127.0.0.1/repos/{OWNER_REPO}"
                                   f"/check-runs/{check['id']}")}
 
     def cli_run(self, run: dict) -> dict:
```

**Контекст**
- Свой нарушитель `tests/test_ci_status.py:1036` исправлен (см. «Возврат из
  verifying»); после этого единственный нарушитель инварианта — долгоживущий
  файл задачи.
- Причина возврата прямо просит заменить хост в долгоживущем файле, но
  `skills/coding-standards.md` («Долгоживущие файлы задачи … не правь их,
  расхождение с ними эскалируй (правка — amend-tests)») и лок сумм
  (`long_lived.sha256.txt`) этого разработчику не дают: правка откажется
  гейтом лока на `in_dev -> verifying`.

**Блокирует**
- Зелёный CI ветки (инвариант адресов) и переход в `verifying`.
