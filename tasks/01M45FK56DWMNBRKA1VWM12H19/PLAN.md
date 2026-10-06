---
task: 01M45FK56DWMNBRKA1VWM12H19
type: plan
author_role: developer
status: escalate
schema_version: 5
---

# PLAN: Этап 3 ADR-0021, часть 2 из 3: защищённые пути проекта, зоны, приложения к PLAN и карта на repo_context

## Подход
Перечень защищённых путей проекта — одна функция
`orchestrator/repo_context.py::protected_paths(ctx)`: у артели —
`tuple(config.PROTECTED_PATHS)`, прочитанный в момент вызова; у внешнего
проекта — поле `no_paths` его записи `targets.yaml`. Поле попадает в
контекст при разрешении: `RepoContext` получил поле `no_paths`
(по умолчанию `()`), `resolve` заполняет его для внешнего проекта; у артели
`resolve` по-прежнему не читает `targets.yaml`. Отсюда же новая
`repo_context.unresolved_reason(target)` — общий текст «контекст проекта
«X» не разрешён: …». `project_profile.unresolved_reason` собран из него и
по тексту не изменился.

Формула сверки одна: `config.is_protected_path(путь, перечень проекта)`.
Функции `scripts/guard.py` (`plan_appendices`, `protected_zones`,
`_appendix_path_is_protected`) принимают перечень параметром `protected`.
`None` означает `config.PROTECTED_PATHS`, так работает и самостоятельный
запуск guard. Вызовы пульта передают перечень проекта задачи.

Развилки «не артель — не проверяется» сняты:
- гейт зон — `orchestrator/advance_gates/zones.py::_zones_gate`;
- гейт применимости приложений — `advance_gates/plan_appendix.py::_plan_appendix_gate`;
- гейт мержа — `fsm_merge_gate.py::_protected_path_diff_gate` и
  `_apply_plan_appendices`;
- шаг карты — `_publish_merge_artifacts`.

Если контекст проекта не разрешён:
- гейт зон отказывает действием «переход отклонён: гейт зон» с причиной,
  называющей проект. Задача без заявленных зон гейт по-прежнему не зовёт
  (AC-7 прежней задачи).
- гейт приложений отказывает действием `PLAN_APPENDIX_GATE_FAILURE_ACTION`
  («переход отклонён: гейт приложений PLAN», класс Оператора: чинится
  `targets.yaml`, не PLAN), но только если PLAN несёт хоть один блок
  приложения. Признак — разбор PLAN с пустым перечнем: пустой перечень
  отвергает любой путь, поэтому пустой разбор означает, что блоков нет.
  PLAN без приложений по-прежнему не трогается.
- гейт ёмкости не тронут: переход не держит.

Общие зоны вне конфликта на гейте зон есть только у артели. У внешнего
проекта общих зон нет — пустой перечень.

Гейт мержа, полный прогон после приложений
(`fsm_merge_gate.py::_full_suite_command`):
- артель — прежние классы `_FULL_SUITE_APPENDIX_PREFIXES` и команда пульта;
- внешний проект с профилем — прогон после любого приложения командой
  профиля (`acceptance.full_suite(..., command=...)`, параметр
  проброшен в `run_full_suite`). При `command=None` вызов
  `run_full_suite(root)` прежний, байт в байт.
- внешний проект без профиля — прогона нет, запись журнала
  «полный прогон приложений не выполнен» с причиной «нет профиля тестов».

Шаг карты (`fsm_merge_gate.py::_map_step`) зависит от наличия
`scripts/codebase_map.py` в дереве мержа, а не от проекта. Генератора нет —
запись «карта кодовой базы не строится», без коммита и без инцидента.
`guard --all` и RETRO остались под признаком артели.

Подсветка черновика MR (`github_adapter.py`) — по перечню проекта. В тексте
комментария назван источник перечня: `config.PROTECTED_PATHS` у артели,
`no_paths проекта X в targets.yaml` у внешнего проекта. Зоны ТЗ на `new`
(`catalog._tz_path_refusal(..., target)`) сверяются по перечню проекта.
Если контекст не разрешён, `new` отказывает с причиной, называющей
проект.

Гейт SPEC сверку защищённых зон не делал вовсе. Новая
`fsm._spec_protected_zones_refusal` сверяет элементы `zones:` SPEC с
перечнем проекта для любого проекта, в том числе для артели: правило
одно, без развилки. Если контекст не разрешён, гейт отказывает с
причиной, называющей проект. Текст отказа — тот же
`guard.PROTECTED_ZONE_REFUSAL`, что на `new`.

Конфликт мержа (`_handle_merge_conflict`) тоже размечает защищённые пути
по перечню проекта: функция `_touches_protected_path` общая с местом ~51
из «Фактов».

`python3 scripts/guard.py <PLAN.md>` (запуск по файлам, не `--all`)
теперь разбирает разделы «## Приложение» по перечню артели
(`guard.plan_appendix_errors`), как `spec_path_errors` для SPEC.

Бюджет SPEC ($50) не переоценивался.

## Шаги
1. `orchestrator/repo_context.py`: поле `RepoContext.no_paths`,
   `protected_paths(ctx)`, `unresolved_reason(target)`.
   `orchestrator/project_profile.py`: `unresolved_reason` собирается из
   общего текста, сам текст прежний.
2. `scripts/guard.py`: параметр `protected` у `plan_appendices`,
   `_appendix_path_is_protected`, `protected_zones`; новая
   `plan_appendix_errors` в запуске по файлам.
3. Гейты выхода из `in_dev`: `advance_gates/zones.py` (развилка снята,
   перечень проекта, общие зоны только у артели, отказ при неразрешённом
   контексте), `advance_gates/plan_appendix.py` (развилка снята, перечень
   проекта, отказ при неразрешённом контексте и наличии приложений),
   `appendix_tree.read_plan(conn, task_id, protected)`.
4. `orchestrator/catalog.py` (зоны ТЗ на `new`) и `orchestrator/fsm.py`
   (`_spec_protected_zones_refusal` на гейте SPEC).
5. `orchestrator/github_adapter.py`: подсветка по перечню проекта.
6. `orchestrator/fsm_merge_gate.py` и `orchestrator/acceptance.py`:
   защищённые пути диффа и конфликта по перечню проекта, приложения у
   любого проекта, `_full_suite_command`, параметр `command` у
   `acceptance.full_suite`, `_map_step`.
7. Тесты: `tests/test_project_protected_paths.py` (свойства, не покрытые
   долгоживущими файлами). Смена ожиданий двух существующих тестов по
   мандату ANSWER-2 (вариант «б», с переименованием) — раздел «Смена
   ожиданий существующих тестов» ниже. Карта `docs/codebase-map.md`
   регенерирована.
8. Приложение 1 к `targets.yaml` (ниже): зеркало `no_paths` записи
   `artel` и новый комментарий.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2, 3, 4, 5, 6 |
| 3 | 3, 4, 6 |
| 4 | 8 |
| 5 | 3 |
| 6 | 6 |
| 7 | 6 |
| 8 | 7; смена ожиданий двух существующих тестов — по мандату ANSWER-2 |

Критерии приёмки:
- AC-1..AC-11 и AC-13 — долгоживущие файлы
  `tests/test_01m45fk56dwmnbrka1vwm12h19_*.py`;
- AC-12 — `test_ac12_unresolved_context.py`;
- AC-14 — `test_ac14_targets_appendix.py`.

Прогоны в этом шаге:
- `merge_gate.py` — 6 passed;
- `in_dev_gates.py`, `draft_mr.py`, `spec_zones.py`, `no_paths_mirror.py` —
  11 passed, 1 failed: сторож AC-13 на дереве без приложения, красен по
  построению (SPEC, «Не входит»);
- сторож AC-13 с временно наложенным приложением 1 — 2 passed;
- `tests/test_project_protected_paths.py` — 4 passed. Каждый метод
  покраснел на своей заявленной мутации: мутации временные, откачены.

Дополнение фикстур `targets.yaml` в существующих тестах: не потребовалось.

## Влияние на систему
- Артель не ослаблена ни в одном месте. Перечень у неё прежний
  (`config.PROTECTED_PATHS`, читается в момент вызова), общие зоны
  прежние, классы полного прогона прежние. Добавлена сверка защищённых
  зон на гейте SPEC (усиление). Защита путей пульта не зависит от
  `targets.yaml`: у артели `resolve` его не читает.
- Внешние проекты получают гейт зон, гейт приложений, сверку диффа на
  мерже, применение приложений и карту. Неразрешённый контекст означает
  отказ, а не пропуск (fail-closed, ADR-0002); исключение — гейт ёмкости,
  как сегодня.
- `docs/invariants.md` не меняется: единственный источник защищённых путей
  пульта по-прежнему `config.PROTECTED_PATHS`.
- Не тронуты: `scripts/ci_protected_paths.py`, `scripts/plan_appendix_ci.py`
  (зовёт `guard.plan_appendices(text)`, перечень по умолчанию — артели,
  поведение прежнее), `checkpoint.py:1475` (фильтр защищённых путей
  чекпоинта — вне перечня «Фактов», часть 3).
- Откат — revert merge-коммита задачи. Приложение к `targets.yaml`
  откатывается вместе с ним, коммитом приложений Оператора.

## Риски
- Новая сверка защищённых зон на гейте SPEC у артели: SPEC, чьё `zones:`
  называет защищённый путь (например, `skills/`), теперь получает отказ
  `approve`. Это и есть требуемое поведение для зон ТЗ на `new`, но у SPEC
  артели его раньше не было.
- У внешнего проекта с профилем, но без каталога `tests/`, полный прогон
  после приложений даст исход «tests/ нет» (`run_full_suite`), а не зелёный
  прогон. Корень набора у профиля не задан (часть 1); это вне этой части.
- Сторож AC-13 красен на дереве ветки без приложения (SPEC, «Не входит») —
  в том числе в полном наборе `suite-run`/автогейта, пока PLAN с
  приложением не попал в ссылку документов.

## Предложения системе
- `tests/test_zones_gate.py::ZonesGateExternalTargetSkipsTest` остаётся
  зелёным только потому, что у задачи нет заявленных зон. Его докстринг
  («внешний target — гейт не проверяется») после этой задачи неверен.
  Правка докстринга — правка существующего теста, поэтому не сделана.
- Сценарий «временно правлю защищённый файл, снимаю `git diff`, откатываю»
  для подготовки приложения к PLAN опасен: исключение посреди сценария
  оставило `targets.yaml` правленым, пока я не откатил его руками. Нужна
  команда пульта, которая строит unified-дифф приложения из файла-образца,
  не трогая рабочую копию.
- Рубежи прогона тестов по-разному обходятся с приложениями PLAN.
  `suite-run`, автогейт и `approve` их накладывают
  (`appendix_tree.suite_tree`), а `_acceptance_run_body` на
  `in_dev -> verifying` — нет. Задача, чей сторож проверяет результат
  приложения, на этом рубеже застревает по построению.
- Приложение, внесённое Оператором в `main` раньше кода, гейт мержа
  признаёт (`_appendix_already_in_main`), а приёмочная проверка
  применимости в планке (`_pult.apply_check`) — нет. Помощнику планки
  нужен такой же исход «уже наложено», как у гейта мержа
  (`orchestrator/plank_helper.py`).
- Механики «приложение Оператора наложено в `main` раньше кода» расходятся
  по рубежам. Гейт мержа и планка (после amend) признают такое
  приложение, а гейт выхода `in_dev` (`advance_gates/plan_appendix.py`) —
  нет. На этой задаче тупик всплыл третьим рубежом подряд (AC-13 → AC-14
  → гейт приложений). Признание «уже наложено» стоит держать в одной
  функции, общей для всех мест.

## Приложение 1: targets.yaml — зеркало `no_paths` записи artel

Применимость проверена: `git apply --check` на чистом дереве ветки
(`targets.yaml` в ветке равен `main`) проходит. После наложения
`targets.load()` проходит, `no_paths` записи `artel` — 18 записей,
множество равно `config.PROTECTED_PATHS`.

```diff
diff --git a/targets.yaml b/targets.yaml
index 9de23282..f161d0cd 100644
--- a/targets.yaml
+++ b/targets.yaml
@@ -23,10 +23,12 @@ targets:
     url: https://github.com/sidorenkoalex/artel
     base: main
     token_slot: artel-token
-    # Пути, которые меняет только Оператор (CLAUDE.md, ADR-0001). Пока это
-    # декларация: исполнитель no_paths — проверка до merge (A2/A3);
-    # действующий enforcement — job protected-paths в .github/workflows/ci.yml.
-    no_paths: [gates.yaml, roles.yaml, targets.yaml, CLAUDE.md, .github/, templates/, skills/, docs/invariants.md, tests/test_invariants.py]
+    # Пути, которые меняет только Оператор (CLAUDE.md, ADR-0001). У внешнего
+    # проекта no_paths — перечень его защищённых путей, по нему сверяют
+    # гейты пульта (orchestrator/repo_context.py::protected_paths). У artel
+    # перечень пульта — config.PROTECTED_PATHS, а это поле — его зеркало:
+    # совпадение держит сторож tests/test_01m45fk56dwmnbrka1vwm12h19_no_paths_mirror.py.
+    no_paths: [gates.yaml, roles.yaml, .github/, templates/, skills/, docs/invariants.md, tests/test_invariants.py, docs/adr/, CLAUDE.md, AGENTS.md, targets.yaml, models.yaml, model_sets.yaml, **/conftest.py, pyproject.toml, pytest.ini, setup.cfg, tox.ini]
     project_skills: []
     merge_gate: operator
     test_profile:
```

## Смена ожиданий существующих тестов (мандат ANSWER-2)

Ответ Оператора ANSWER-2 на эскалацию: вопрос 1 — вариант «б» (обе
правки с переименованием), вопрос 2 — вариант «а» (сверка защищённых зон
на гейте SPEC у любого проекта, у артели — по `config.PROTECTED_PATHS`;
реализация не менялась). Строки мандата «Ослабление тестов разрешено: …»
называют оба прежних имени методов.

1. `tests/test_plan_appendix.py::PlanAppendixGateTest::test_external_target_skips_the_gate`
   → `test_unresolved_external_target_refuses_without_git`.
   - Было: `self.assertFalse(refuses)`.
   - Стало: `self.assertTrue(refuses)` и `self.assertEqual(self.actions(),
     [plan_appendix.PLAN_APPENDIX_GATE_FAILURE_ACTION])`. Подмена
     `gitcmd.diff_base` → `boom` сохранена.
   - Основание: требование 3 SPEC, AC-12.
2. `tests/test_protected_paths_gate.py::MergeGateProtectedPathDiffGateTest::test_external_target_never_calls_diff_base`
   → `test_external_target_checks_diff_by_project_perimeter`.
   - Было: `diff_base.assert_not_called()`, `self.assertFalse(escalated)`.
   - Стало: `diff_base` отвечает `"deadbeef"`, `gitcmd.diff_names` —
     `["skills/x.md"]`; `diff_base.assert_called_once_with("task/t001-x",
     repo=ext_ctx.path)`; `self.assertFalse(escalated)` сохранено.
   - Основание: требования 1, 3 SPEC, AC-5.

Докстринги обоих методов переписаны под новую проверку, заявки «Ловит
мутацию» обновлены. Проверка мутацией: развилка возвращена временно
(`plan_appendix.py` — пропуск при неразрешённом контексте;
`fsm_merge_gate._protected_path_diff_gate` — `if not
repo_context.is_artel(ctx): return False`). Оба метода покраснели, код
возвращён без изменений.

Прогоны в шаге после правки: `test_plan_appendix.py`,
`test_protected_paths_gate.py`, `test_zones_gate.py`,
`test_project_protected_paths.py` — 80 passed; `test_plan_appendix.py`,
`test_protected_paths_gate.py`, `test_test_integrity_gate.py`,
`test_mutation_claim_gate.py` — 109 passed.

Полный набор — `suite-run` №3 (прогон ветки с наложенным приложением 1 к
`targets.yaml`): 4490 прошло, 1 упало, 2 пропущено. Сторож AC-13 зелёный.
Единственный упавший —
`tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`:
по ANSWER-2 это окружение роли (в PATH роли нет `/bin`, `ps` недоступен),
к задаче не относится. База не посчитана: прогон базы тоже красный.

## Сверка после ANSWER-3 (подтяжка main с 09256315)

- Ветка подтянута коммитом 701c9ad5: `targets.yaml` в HEAD уже несёт
  приложение 1 (строка 31, 18 записей, новый комментарий). Подтяжка не
  меняла `*.py`; карта `docs/codebase-map.md` всё равно регенерирована.
- Код задачи не менялся (ANSWER-3).
- `python3 -m pytest tests/test_01m45fk56dwmnbrka1vwm12h19_*.py
  tests/test_project_protected_paths.py tests/test_plan_appendix.py
  tests/test_protected_paths_gate.py tests/test_zones_gate.py` —
  98 passed. Сторож AC-13 зелёный.
- `artel.py plank-run 01M45FK56DWMNBRKA1VWM12H19` — 1 failed, 1 passed.
  Упал
  `acceptance_tests/test_ac14_targets_appendix.py::TargetsAppendixTest::test_ac14_targets_appendix_applies_and_mirrors_protected_paths`
  на первом утверждении (строка 111): `git apply --check --cached` вернул
  «error: patch failed: targets.yaml:23». Тест накладывает приложение
  к HEAD, а там оно уже есть. Остальные утверждения теста (множество
  `no_paths`, комментарий, прочие поля) этим состоянием HEAD выполнены.

## Сверка после ANSWER-4 (планка AC-14 исправлена `amend-tests`, лок bbdf2bae)

- Код задачи и приложение 1 не менялись (ANSWER-4).
- `artel.py plank-run 01M45FK56DWMNBRKA1VWM12H19` — 2 passed
  (`test_ac12_unresolved_context.py`, `test_ac14_targets_appendix.py`),
  код выхода pytest 0.
- `python3 -m pytest tests/test_01m45fk56dwmnbrka1vwm12h19_*.py
  tests/test_project_protected_paths.py` — 22 passed, 26 subtests passed.
  Сторож AC-13 зелёный.
- Вопрос эскалации ANSWER-4 закрыт: Оператор исполнил вариант «а».

## Эскалация

**Вопросы** (по блокирующести):

1. **Сдача `ready` по ANSWER-4 отклонена гейтом применимости приложений
   на выходе `in_dev`.** Отказ: «переход отклонён: приложение PLAN
   неприменимо: приложение PLAN targets.yaml не применяется к базе
   сравнения 09256315…: error: patch failed: targets.yaml:23».
   `orchestrator/advance_gates/plan_appendix.py::_plan_appendix_gate`
   (строки 182-193) накладывает каждое приложение прямо на дерево базы
   `gitcmd.diff_base`. Исхода «уже наложено» у него нет, в отличие от
   гейта мержа (`fsm_merge_gate.py::_appendix_already_in_main`, ~847) и
   исправленной планки AC-14. База ветки — 09256315, там приложение 1
   уже наложено. Проверено в этом шаге: прямой
   `git apply --check --cached` отказывает, с `-R` проходит, `merge-base
   HEAD main` = 09256315. Получается тупик:
   - если оставить приложение (так велит ANSWER-4), откажет этот гейт;
   - если убрать приложение, планка AC-14 упадёт на «приложений к
     targets.yaml не одно» (`test_ac14_targets_appendix.py:67-70`);
   - если поправить гейт, это правка кода, которую ANSWER-4 запрещает
     («код задачи не меняй»). Кроме того, правится механика гейта из
     чужой SPEC (01M2YSHDKWFJN3XSJ618Z74FNF).

   Варианты:
   - (а) Мандат на правку `_plan_appendix_gate`: приложение, которое не
     применяется прямо, но проходит `git_apply(repo, appendix,
     "--reverse", "--check")` на дереве базы, гейт признаёт «уже
     наложенным». Это то же признание, что у гейта мержа, и тот же
     `git_apply`. Для этого нужны запись в журнал и юнит-тест с заявкой
     мутации. Неприменимое в обе стороны приложение по-прежнему получает
     отказ, так что гейт не ослабляется. Правка — несколько строк в
     `plan_appendix.py` и тест в `tests/test_plan_appendix.py` (новый
     метод).
   - (б) Оператор проводит задачу через `in_dev -> review` своим решением
     в обход этого гейта. Применимость уже доказана наложением в `main`
     коммитом 09256315.
   - (в) Убрать приложение 1 из PLAN и исправить планку AC-14 через
     `amend-tests`: при отсутствии приложения проверять результат прямо
     на HEAD. Не рекомендую: из ссылки документов пропадает след
     приложения.

   Дефолт при молчании: (а).

**Контекст.** Код задачи после ANSWER-4 не менялся. `plank-run` — 2
passed. Долгоживущие файлы задачи и `tests/test_project_protected_paths.py`
— 22 passed. Сторож AC-13 зелёный. Отказ гейта получен на первой сдаче
`ready` после ANSWER-4.

**Блокирует.** Переход `in_dev -> review`: гейт применимости приложений
откажет при любой сдаче `ready`, пока приложение 1 в PLAN, а `main` уже
несёт его результат.
