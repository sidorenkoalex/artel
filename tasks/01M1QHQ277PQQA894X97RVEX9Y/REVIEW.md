---
task: 01M1QHQ277PQQA894X97RVEX9Y
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 4
---

# REVIEW: Тесты не выходят в сеть: перехват сетевых git-команд в песочнице, локальные фикстуры, инвариант

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (единая точка перехвата сетевых git-команд) | OK | `tests/sandbox.py:279-341` — `_is_local_git_address`/`_network_git_command_denial`/`network_guarded_real_run`. `TmpRootTest.setUp` (`tests/sandbox.py:560`) заводит `SpyRun(passthrough_unknown=True)`, чей `__call__` (строка 457) в ветке `passthrough_unknown` зовёт `network_guarded_real_run` вместо голого `_REAL_RUN` — перехват действует на ВСЕХ наследников `TmpRootTest`, как требует AC-1. `tests/test_git_fixation.py::_GitFixationTmpRootTest.setUp` (строка 128) патчит `gitcmd.subprocess.run` той же функцией вместо сырого `_REAL_SUBPROCESS_RUN` — это и был фактический источник инцидента 05.09 (реальный git в обход `SpyRun`), проверено чтением `tasks/.../PLAN.md` «Подход» и вживую (см. «Проверено исполнением»). |
| 2 (локальные фикстуры target'ов + doctor/multitarget) | OK | `tests/test_coldstart.py`, `tests/test_git_fixation.py`, `tests/test_branch_freshness_gate.py`, `tests/test_doctor.py`, `tests/test_multitarget.py` — адреса `https://example.invalid/...` заменены на `file:///nonexistent/...` (AC-3/AC-5 «поправить»-путь). Ассерт `test_branch_freshness_gate.py:592` переписан на `http://127.0.0.1:9/acme-target.git`, остальные три ассерта того же метода (origin/trunk/MAIN_BRANCH) не тронуты — AC-4 не ослаблена. Дополнительно найденные `test_ci_status.py`/`test_github_adapter.py` (не названы SPEC, но задеты требованием 3, сканирующим ВЕСЬ `tests/**/*.py`) закрыты вторым легальным путём AC-5 — именованной константой исключений в защищённом диффе (см. ниже), не правкой кода этой ветки. |
| 3 (инвариант + структурный тест, AC-6/AC-7/AC-8/AC-10) | OK | Поставлено НЕ коммитом в ветку, как и требует AC-8, а unified-diff-приложением к `tasks/.../PLAN.md` (доступен только на артефактной ветке `artifact/01M1QHQ277PQQA894X97RVEX9Y`, см. «Проверено исполнением» — PLAN.md на кодовой ветке отсутствует намеренно, конвенция AC-8/прецедент 01M1KVGD18P9H5WR7VM8TGPV1T). Оба диффа (`docs/invariants.md` — строка реестра 34 со ссылкой на `test_invariants.NoNetworkAddressesInTestsTest`; `tests/test_invariants.py` — сам структурный тест) прошли `git apply --check` на чистом дереве этой ветки индивидуально и совместно — перепроверено самостоятельно, не только со слов PLAN. Временно применены и прогнаны: структурный тест зелёный на текущем `tests/` (0 нарушителей) и ловит синтетическую DNS-фикстуру (AC-10) — подтверждает, что фикстуры требования 2 действительно закрывают скан, а не просто выглядят похоже. |
| 4 (тесты перехвата/структурного теста, AC-1/AC-2/AC-9/AC-10/AC-11) | OK | AC-1/AC-2/AC-9 — приёмочные тесты задачи, зелёные (см. «Проверено исполнением»); AC-9 дополнительно подменяет `socket.getaddrinfo` на мгновенный `gaierror`, доказывая отказ решается по форме адреса, а не резолвером. AC-10 — структурный тест ловит синтетическую фикстуру (проверено после временного применения диффа). AC-11 — таргетные модули зелёные (215 тестов, 36 с, без зависаний, ранее евший минуты); полный набор `tests/` — штатный CI-гейт, не дублируется здесь (решение Оператора 05.09). |

AC-5/AC-7/AC-8/AC-11 приёмочной планки помечены `manual`/`skip` — обоснования легальны: AC-5 честно constatирует, что SPEC явно оставляет выбор между двумя равноценными путями закрытия и тест не может решить его заранее без ложного красного на валидном втором пути; AC-7/AC-8 — процессные требования к содержимому/механике диффа-приложения, проверяемые Оператором на гейте PLAN, а не кодом ветки задачи (нет артефакта на диске до применения диффа); AC-11 — класс «ci-covered» (штатный CI-джоб `python`), разрешённый skills/review-checklist.

## Замечания

- minor — `tests/test_sandbox.py:20-103` (все 13 тестовых методов классов `IsLocalGitAddressTest`, `NetworkGitCommandDenialTest`, `NetworkGuardedRealRunTest`) — ни один тестовый метод не несёт обязательную заявку `Ловит мутацию: …` (skills/test-authoring.md, «Чувствительность: у теста — заявленная мутация»; review-checklist требует сверять с ней КАЖДЫЙ новый/изменённый тест, не только приёмочный — тот же класс пробела уже отмечался в прошлых задачах). 10 методов вовсе без докстринга (`test_file_url_is_local:22`, `test_absolute_path_is_local:25`, `test_loopback_http_hosts_are_local:33`, `test_dns_hostname_https_is_not_local:37`, `test_fetch_with_dns_address_is_denied:50`, `test_local_address_is_not_denied:68`, `test_non_network_subcommand_is_not_denied:72`, `test_bytes_mode_stderr_matches_text_flag:76`, `test_dns_address_is_denied_without_touching_real_subprocess:86`, `test_non_network_command_passes_through_to_real_subprocess:96`); 3 — с коротким пояснением, но без claim-строки (`test_bare_remote_name_is_local:28`, `test_host_merely_prefixed_by_loopback_ip_is_not_local:41`, `test_dash_c_prefix_is_skipped_when_locating_the_subcommand:59`). По существу тесты содержательны и правдоподобно ловят реальные мутации (сама логика уже документирована докстрингами `tests/sandbox.py`) — предложение: добавить в каждый метод строку `Ловит мутацию: …` по образцу приёмочных тестов той же задачи (`tasks/.../acceptance_tests/test_ac1_network_command_interception.py` и соседние), которые конвенцию соблюдают. Не блокирует мерж — постоянное юнит-покрытие уже фактически проверяет заявленное поведение, дефект чисто документационный.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_sandbox.py:20-103 | Ни один из 13 тестовых методов нового файла не несёт докстринг-заявку «Ловит мутацию: …» (10 — вовсе без докстринга) | Снижает трассируемость нового юнит-покрытия при будущих правках `tests/sandbox.py` — сложнее понять, какую регрессию ловит каждый тест, не читая его тело | Minor, не блокирует мерж: сами тесты содержательны и покрывают реальные сценарии (перепроверено запуском и чтением кода), заявка — документационное дополнение. Принимаю как есть в этой итерации; желательно поправить в этой или следующей задаче, трогающей `tests/sandbox.py`/`tests/test_sandbox.py`. |

## Вердикт

approved — 0 blocker/major. Единственное замечание (R1-F1) — minor, документационное, не влияет на корректность перехвата или тестового покрытия по существу; принято реестром сразу (см. решение выше), гейт `review -> verifying` не блокируется.

## Проверено исполнением

- `python3 -m unittest tests.test_sandbox tests.test_git_fixation tests.test_coldstart tests.test_doctor tests.test_multitarget tests.test_branch_freshness_gate -v` — 215 тестов, все зелёные, 36.4 с (ранее до фикса `test_git_fixation.py` висел минутами на реальном DNS — регрессия подтверждена устранённой: тот же файл теперь укладывается в общий прогон).
- `python3 -m unittest discover -s tasks/01M1QHQ277PQQA894X97RVEX9Y/acceptance_tests -p "test_*.py" -v` — 8 исполняемых тестов (AC-1, AC-2, AC-3, AC-4, AC-6, AC-9, AC-10), все зелёные, 0.37 с; AC-5/AC-7/AC-8/AC-11 — легальные manual/skip (прочитаны и оценены обоснования, см. «Соответствие SPEC»).
- Извлёк оба unified-diff блока из `tasks/01M1QHQ277PQQA894X97RVEX9Y/PLAN.md` (артефактная ветка `artifact/01M1QHQ277PQQA894X97RVEX9Y`, коммит `c1331c82`) и прогнал `git apply --check` — по отдельности и вместе — на текущем дереве кодовой ветки: оба применяются чисто (`docs/invariants.md`, `tests/test_invariants.py` в этой ветке не менялись, дерево эквивалентно «чистому» из AC-8).
- Временно применил оба диффа (`git apply`), прогнал `python3 -m unittest tests.test_invariants.NoNetworkAddressesInTestsTest -v` — 2 теста зелёные: структурный сканер не находит нарушителей во всём текущем `tests/**/*.py` (подтверждает полноту фикстур требования 2) и ловит синтетическую DNS-фикстуру (AC-10). Откатил диффы (`git apply -R`), `git status` — дерево чистое.
- `python3 scripts/codebase_map.py` и сравнение с закоммиченным `docs/codebase-map.md` (`git diff` без строки `built_at_sha`) — содержимое идентично, регенерация в диффе корректна; откатил локальную регенерацию (`git checkout --`).
- Прочитал `tests/sandbox.py` целиком в релевантных диапазонах (докстринг модуля, `_is_local_git_address`/`_network_git_command_denial`/`network_guarded_real_run`, `SpyRun.__init__`/`__call__`, `TmpRootTest.setUp`) — подтвердил монтаж перехвата на `passthrough_unknown=True` пути, который используют все наследники `TmpRootTest` (AC-1/AC-2).

## Предложения системе

- skills/review-checklist.md, пункт 3 («Тесты») — докстринг-заявка «Ловит мутацию: …» продолжает проседать именно в НОВЫХ обычных `tests/*.py` (не приёмочных), которые пишет developer, а не test_author: приёмочные планки задач это правило соблюдают почти всегда, обычные юнит-тесты — часто нет (см. R1-F1 здесь). Стоит явно перенести формулировку конвенции из skills/test-authoring.md (сейчас озаглавлен под роль test_author) в conventions-core или отдельно адресовать developer'у — сегодня разработчик узнаёт о требовании только из ревью постфактум.
