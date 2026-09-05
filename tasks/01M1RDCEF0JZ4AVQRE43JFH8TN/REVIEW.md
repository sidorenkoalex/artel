---
task: 01M1RDCEF0JZ4AVQRE43JFH8TN
type: review
author_role: reviewer
status: approved
iteration: 3
schema_version: 4
---

# REVIEW: объявленный стек пульта, часть 3 — окружение роли из манифеста, снятие временного хука

## Служебное замечание к ревью-пакету

Тот же класс, что в итерации 2 (memory-заметка «tasks/<id>/ отсутствует
во всей истории task-ветки»): SPEC.md/PLAN.md/предыдущий REVIEW.md
отсутствуют в кодовой ветке и в рабочем дереве по конвенции (`tasks/<id>/`
в кодовую ветку не коммитится) — прочитал их из
`artifact/01m1rdcef0jz4avqre43jfh8tn` (`git show
artifact/01m1rdcef0jz4avqre43jfh8tn:tasks/01M1RDCEF0JZ4AVQRE43JFH8TN/
{SPEC,PLAN,REVIEW}.md`).

Отдельно: инкрементальный diff пакета (от 67765807 до HEAD) целиком
состоит из ЧУЖОГО содержимого — двух независимо смерженных задач
(01M1RA0N6FCFEQBB82K58GM12X «гейт ёмкости diff», 01M1RFQ52S0VD22J628TXX96XS
«проекция карты для брифа»), попавших в ветку задачи через `подтяжку main`
(коммиты 4424e0d1, b188429a, 3d6bea81). Собственная правка разработчика
этой итерации — фикс R2-F1 (планка приёмки, коммит `8d346d16
«правка планки приёмки — ADR-0012»`) — лежит ТОЛЬКО в артефактной ветке
(`tasks/<id>/acceptance_tests/` не коммитится в кодовую ветку — это
ожидаемо, не дефект) и потому не виден в инкрементальном diff'е пакета
вовсе. Без ручной проверки (`git log --oneline -- tasks/<id>/`,
`git branch --contains 8d346d16`, материализованная планка в рабочем
дереве) вердикт «код не менялся» был бы ошибочным — по опыту прошлой
итерации и по правилу скила «инкрементальный diff — пустой не значит
без изменений» перепроверил вручную.

## Фаза A: гейт плана

PLAN.md не менялся содержательно относительно итерации 2 сверх ранее
принятых секций. Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (PATH роли только из каталогов объявленных инструментов, `python3`=`sys.executable`) | OK | `orchestrator/runner.py::role_env`/`_role_path_dirs` на месте после подтяжек main, без изменений |
| 2 (белый список переменных окружения) | OK | `_allowlisted_env` на месте |
| 3 (отсутствие инструмента — стоп без отката) | OK | `_resolve_declared_tools` — первая операция, `OSError` наружу |
| 4 (снятие временного хука) | OK | `docs/reference/role-home/claude/hooks/`, `tests/test_role_bash_guard.py` отсутствуют; `hooks.PreToolUse` в settings.json отсутствует; `role-home.md` не упоминает хук |
| 5 (doctor WARN на расхождении референса) | OK | `check_role_home_reference`/`_role_home_diff` на месте, подключена в `all_checks` |

Требования 1-5 (AC-1..14) реализованы корректно и не пострадали от
подтяжек main между итерациями.

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R2-F1 | accepted | tasks/01M1RDCEF0JZ4AVQRE43JFH8TN/acceptance_tests/test_ac9_ac10_ac11_ac12_bash_guard_removed.py:100-109 | приёмочный тест AC-10 сравнивал `permissions.deny` точным `assertEqual` с замороженным снимком, ломался от легитимного стороннего расширения (01M1NSR5M5THYRC0RFWPMVE2DW) | планка не проходила целиком, задача не могла дойти до merge/verifying | Проверил: коммит `8d346d16` (артефактная ветка, ADR-0012 в сообщении коммита) заменил `assertEqual(deny, EXPECTED_DENY)` на проверку подмножества (`missing = [d for d in EXPECTED_DENY if d not in deny]; assertEqual(missing, [])`) — исходные записи по-прежнему обязаны присутствовать (чувствительность к удалению запрета сохранена), расширение чужой задачей больше не красит. Прогнал материализованную из головы артефактной ветки планку целиком — `Ran 19 tests … OK`, включая именно этот тест. Исправлено по существу, закрываю |

Прошлые записи R1-F1/R1-F2/R1-F3 уже `accepted` в итерации 2 — не
повторяю (восстановимы из git-истории REVIEW.md).

## Вердикт

approved — 0 blocker/major. Требования SPEC 1-5 (AC-1..14) реализованы
полностью и корректно; единственный блокер предыдущей итерации (R2-F1,
дрейф стороннего `permissions.deny`) исправлен по существу и подтверждён
прогоном планки. Реестр замечаний закрыт целиком (единственная
незакрытая запись переведена в `accepted`).

## Проверено исполнением

- `python3 -m unittest discover -s tasks/01M1RDCEF0JZ4AVQRE43JFH8TN/acceptance_tests -p 'test_*.py' -v` (планка материализована в рабочем каталоге из головы артефактной ветки, включает фикс R2-F1 из коммита `8d346d16`) — `Ran 19 tests in 0.129s, OK`, включая `test_ac10_permissions_deny_is_unchanged`.
- `python3 -m unittest tests.test_doctor tests.test_multitarget tests.test_multitarget_invariants tests.test_stack tests.test_invariants -v` — `Ran 207 tests in 18.528s, OK`.
- `python3 scripts/codebase_map.py` на чистом дереве, сверка diff без строки `built_at_sha` (`grep -v '^built_at_sha:'` по обеим версиям) — расхождений в содержимом нет, карта свежая; правка `built_at_sha` отменена (`git checkout -- docs/codebase-map.md`), в дереве не осталось.
- `git branch --contains 8d346d16` / `git merge-base --is-ancestor 8d346d16 <кодовая ветка>` — подтвердил, что фикс R2-F1 лежит только в артефактной ветке (`tasks/<id>/acceptance_tests/` не коммитится в кодовую ветку — ожидаемо, не дефект), не отсутствует.
- Точечные grep/чтение: `docs/reference/role-home/claude/hooks/` (нет каталога), `tests/test_role_bash_guard.py` (нет файла), `hooks.PreToolUse`/`bash_guard` в `settings.json`/`role-home.md` (нет упоминаний), `orchestrator/runner.py::role_env`/`_resolve_declared_tools`/`_allowlisted_env`, `orchestrator/doctor.py::check_role_home_reference`/`_role_home_diff` (в `all_checks`) — все требования 1-5 на месте после подтяжек main.
- `git log --oneline -- tasks/01M1RDCEF0JZ4AVQRE43JFH8TN/` и `git show 8d346d16 -- tasks/.../test_ac9_ac10_ac11_ac12_bash_guard_removed.py` — установил происхождение и содержание фикса R2-F1 (не только по сообщению коммита, по факту diff'а).

## Предложения системе

- Тот же класс, что уже отмечен в итерации 2: собственная правка задачи
  внутри `tasks/<id>/acceptance_tests/` (правка планки по ADR-0012)
  коммитится только в артефактную ветку — инкрементальный diff пакета,
  построенный от sha предыдущего вердикта до HEAD КОДОВОЙ ветки, эту
  правку не увидит никогда, даже если она единственное содержимое
  итерации (как здесь). Ревьювер должен помнить сверять `tasks/<id>/`
  отдельно от кодового diff'а — стоит явно проговорить это в
  review-checklist.md рядом с существующим предупреждением про
  «пустой diff не значит без изменений», а не полагаться на то, что
  ревьювер догадается сам по прецеденту прошлой итерации.
