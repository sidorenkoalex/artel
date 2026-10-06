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
   долгоживущими файлами). Карта `docs/codebase-map.md` регенерирована.
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
| 8 | 7; смена ожиданий двух существующих тестов — «Эскалация» ниже |

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

## Эскалация

**Вопросы** (по блокирующести):

1. **Мандат на смену ожиданий двух существующих тестов** (требование 8
   SPEC). Они закрепляют пропуск проверки для внешнего проекта и на ветке
   красны по построению: развилку сняли требования 3 и 1.
   - `tests/test_plan_appendix.py::PlanAppendixGateTest::test_external_target_skips_the_gate`.
     Задача проекта `other`: записи в `targets.yaml` нет, контекст не
     разрешён. PLAN несёт приложение.
     - Было: `self.assertFalse(refuses)` — гейт пропускает молча, git не
       зовётся.
     - Стало: `self.assertTrue(refuses)` и `self.assertEqual(self.actions(),
       [plan_appendix.PLAN_APPENDIX_GATE_FAILURE_ACTION])`. Подмена
       `gitcmd.diff_base` → `boom` остаётся: git по-прежнему не зовётся.
     - Требования SPEC 3 (столбец «неразрешённый контекст» — отказ
       перехода) и AC-12.
   - `tests/test_protected_paths_gate.py::MergeGateProtectedPathDiffGateTest::test_external_target_never_calls_diff_base`.
     Внешний `RepoContext` без `target` и без `no_paths`.
     - Было: `diff_base.assert_not_called()` и `self.assertFalse(escalated)`.
     - Стало: `diff_base.assert_called_once_with("task/t001-x",
       repo=ext_ctx.path)` при подменённом `gitcmd.diff_names`, отдающем
       путь пульта (например, `skills/x.md`). Утверждение
       `self.assertFalse(escalated)` остаётся: пустой перечень проекта не
       эскалирует путь, защищённый только у артели.
     - Требования SPEC 1, 3 и AC-5.

   Варианты:
   - (а) мандат на обе правки как описано, имена методов сохраняются;
   - (б) то же, но с переименованием методов: имена «skips»/«never_calls»
     после правки лгут, например `test_unresolved_external_target_refuses_without_git`
     и `test_external_target_checks_diff_by_project_perimeter`;
   - (в) раздел SPEC «Меняемое поведение» — если Оператор сочтёт смену
     выразимой парами литералов. Смена здесь не литеральная
     (`assertFalse` → `assertTrue`, `assert_not_called` →
     `assert_called_once_with`), поэтому раздел её, скорее всего, не
     опишет.

   Дефолт при молчании: (а).

2. **Сверка защищённых зон на гейте SPEC у артели.** Сегодня гейт SPEC зоны
   с защищёнными путями не сверяет ни у какого проекта. Сделано правило без
   развилки: сверка у любого проекта, у артели — по `config.PROTECTED_PATHS`.
   Варианты:
   - (а) оставить для всех проектов;
   - (б) только для внешних проектов: строгое прочтение AC-10 «для
     артели — прежний перечень», а прежнего поведения на гейте SPEC у
     артели не было.

   Дефолт при молчании: (а).

**Контекст.** Реализация готова целиком:
- `merge_gate.py` — 6/6 зелёные;
- `in_dev_gates.py`, `draft_mr.py`, `spec_zones.py` — зелёные;
- сторож AC-13 зелёный с наложенным приложением 1;
- `tests/test_project_protected_paths.py` — 4/4 зелёные.

В тестах затронутых модулей красны только два метода из вопроса 1
(прогон `test_zones_gate.py`, `test_plan_appendix.py`,
`test_protected_paths_gate.py`, `test_protected_test_settings.py`,
`test_github_adapter.py`, `test_catalog_tz_path_check.py`,
`test_fsm_spec_gate_path_check.py`, `test_repo_context.py`,
`test_project_profile*.py`, `test_fsm_map_regen.py`,
`test_appendix_tree.py`, `test_multitarget.py` и др.: 2 failed, 255
passed). `tests/test_zones_gate.py:210` из «Фактов» ТЗ остаётся зелёным
без правки: у задачи нет заявленных зон, и гейт выходит до проверки
проекта.

Полный набор — `suite-run` №1: 4487 прошло, 4 упало, 2 пропущено. Прогон
шёл без приложений PLAN: PLAN.md ещё не в ссылке документов. Повтор
упавших (№2) — те же 4:
- два метода вопроса 1;
- сторож AC-13 — красен без приложения 1 по построению;
- `tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`
  («0 not greater than or equal to 1»). Ни `orchestrator/liveness.py`, ни
  этот тест диффом задачи не тронуты. Вероятно, это окружение шага: в PATH
  оболочки роли нет даже `ls`/`cat`. База посчитана не была (прогон базы
  тоже красный), поэтому сравнить с ней не удалось.

**Блокирует.** Сдачу `ready`: рубеж неослабления тестов откажет правке
утверждений двух методов без мандата, а без правки они красны.
