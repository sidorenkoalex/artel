---
task: 01M4S24EBVB72B8WYJ3JY96Y0E
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Справочник ядра в брифе и пересборка после мержа (К-3б)

## Подход

Тонкие потребители интерфейса К-3а `reference_cache.get_reference` (модуль
уже в main ветки задачи):

- `orchestrator/brief.py::_core_reference_part(conn, task_id, role, run_id)`
  — один помощник на обе роли. Зовёт `reference_cache.get_reference(conn,
  task_id, reason="brief")` (через атрибут модуля, `sha` не передаётся).
  `off` → пустая строка: вызывающий кусок не добавляет, бриф байт в байт
  прежний. Непустая `note` → `"<note>\n\n"` перед компонентом вне
  хэшируемого текста (приём `map_note`). `absent` или пустой текст → только
  пометка. Иначе размер в байтах UTF-8 сверяется с
  `config.CORE_REFERENCE_MAX_BYTES`: крупнее — строка «справочник ядра:
  <размер> байт > <предел> — не включён, решение за Оператором (…)» без пути
  кэша; в пределе — `_manifest_component` с меткой
  `.artel/projects/<проект>/knowledge/derived/core-reference.md`
  (`CORE_REFERENCE_LABEL`, из `reference_cache.CACHE_REL`): опись, запись
  «бриф: компонент», граница.
- Алерты (`_set_alert`, образец `_handle_map_size_alert`): `incident`
  `brief.core_reference_oversized` при размере > предела; `warning`
  `brief.core_reference_near_limit` при `size*10 > limit*9` и не крупнее
  предела (целочисленно, без округления 90%); в остальных случаях открытый
  алерт того же источника и ТОГО ЖЕ проекта снимается `alerts.auto_ack`.
  Тексты алертов — константы без размеров и sha (дедуп `raise_alert`).
- `developer_brief`: кусок справочника — между проекцией карты и
  `CLAUDE.md`. `test_author_answer_component`: куски (причина, ANSWER,
  справочник) склеиваются `"\n".join` — при пустом справочнике это тот же
  текст, что прежняя склейка `sep`; `None` — только когда пусты все три.
- `orchestrator/fsm_merge_gate.py::_rebuild_core_reference(conn, task_id,
  final_sha)` — последний шаг `_cmd_approve_merge_gate` после
  `_await_main_ci`, перед `return ("done",)`; на `"moved"` до него не
  доходит. Под `try/except Exception`: исход не `off` — запись «справочник
  ядра после мержа» (состояние, sha, пометка); сбой — запись «…: сбой» и
  алерт `incident` источника К-3а `fsm.core_reference_regen` по проекту, каждое
  под своим `contextlib.suppress(Exception)` (сбой журнала не отменяет
  алерт). `sys.exit`-помощников шаг не зовёт, ничего не коммитит.
- `config.CORE_REFERENCE_MAX_BYTES = 32_768`.

Бюджет SPEC ($45) не переоцениваю: объём совпал с оценкой.

## Шаги

1. Константа предела в `orchestrator/config.py`; `_core_reference_part`,
   `_set_alert`, встраивание в `developer_brief` и
   `test_author_answer_component` (`orchestrator/brief.py`).
2. Шаг `_rebuild_core_reference` в `orchestrator/fsm_merge_gate.py`.
3. Свой тест `tests/test_merge_reference_step.py` (запись исхода шага с
   пометкой, запись и алерт сбоя по проекту) — свойства, которых нет в
   долгоживущих файлах задачи; проверен временной мутацией (убраны алерт
   обработчика и пометка в записи — оба метода покраснели, код возвращён).
4. Карта `python3 scripts/codebase_map.py`; приложение к `targets.yaml` —
   раздел «Приложение» ниже.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 (справочник зовут только `developer_brief` и `test_author_answer_component`) |
| 4 | 1, 2 |
| 5 | 1 |
| 6 | 1 |
| 7 | 1 |
| 8 | 1 |
| 9 | 2 |
| 10 | 4 (Приложение) |
| 11 | 3 + долгоживущие `tests/test_01m4s24ebvb72b8wyj3jy96y0e_*.py` |
| 12 | 4 |

Прогоны в шаге: `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py`
и `…_merge_reference.py` — 16 passed, 53 subtests; `tests/test_brief.py`,
`test_review_package.py`, `test_advance_refusal_history.py`,
`test_core_reference.py` — 183 passed; тесты гейта мержа
(`test_fsm_merge_gate_done_snapshot.py`,
`test_fsm_merge_gate_scratch_worktree_cleanup.py`,
`test_merge_gate_ci_wait.py`, `test_merge_gate_clock_isolation.py`,
`test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`,
`test_fsm_merge_conflict_note.py`, `test_role_prompt_test_author_mission.py`)
— 52 passed; `tests/test_merge_reference_step.py` — 2 passed.
Планка (`plank-run`) — 2 passed. Полный набор (`suite-run` №1, коммит
9da36d47, без приложения — PLAN ещё не в ссылке документов) — 5382 прошло,
0 упало, 2 пропущено. С наложенным приложением: `tests/test_multitarget.py::TargetsFileTest::test_repository_file_is_valid`
— passed, `targets.core_reference("artel")` разбирает поле.

## Влияние на систему

- Проект без поля `core_reference`: `get_reference` → `off`, бриф developer и
  test_author байт в байт прежние (кусок не добавляется, склейка та же),
  шаг после мержа ничего не пишет. Существующие тесты брифа и ревью-пакета
  не менялись и зелёные.
- Гейт мержа: шаг стоит после всего критического пути (push, `done`,
  коммит закрытия, уборка, ожидание CI main) и не бросает; держит мьютекс
  мержа до общего срока сборки К-3а (60 с) — принятая SPEC цена.
- Ни гейты, ни лимиты, ни тесты не ослабляются; новый лимит
  `CORE_REFERENCE_MAX_BYTES` добавлен.
- Откат: revert merge-коммита задачи; приложение к `targets.yaml` —
  отдельным revert или удалением поля (без поля механизм выключен).

## Приложение

Поле `core_reference` в конец записи `artel` (`git apply --check` на чистом
дереве ветки проверен: дифф снят `git diff` с реальной правки файла,
`targets.core_reference("artel")` его разбирает).

```diff
diff --git a/targets.yaml b/targets.yaml
index ee9bc156..7302f8a7 100644
--- a/targets.yaml
+++ b/targets.yaml
@@ -46,3 +46,11 @@ targets:
       report: junit-xml
       install: []
       full_suite_timeout_sec: 1500
+    # Справочник ядра в брифе developer/test_author (SPEC
+    # 01M4S24963R9H18AN2XDP6R15B, 01M4S24EBVB72B8WYJ3JY96Y0E): модули ядра и
+    # константы, которые роль получает коротким ответом «как пользоваться»;
+    # кэш — .artel/projects/artel/knowledge/derived/core-reference.md.
+    core_reference:
+      modules: [orchestrator/store.py, orchestrator/config.py, tests/sandbox.py, orchestrator/fsm.py, orchestrator/runner.py, orchestrator/gitcmd.py]
+      constants_module: orchestrator/config.py
+      constants: [PROTECTED_PATHS, COMMON_ZONES, STATE_ROLE, DEFAULT_TARGET, PROJECT_DIRS, MAIN_BRANCH, ROOT, TASKS, PROJECTS, TARGETS, DB, LOGS]
```

## Риски

- Размер справочника артели на голове ветки — 30 386 байт (замер
  `python3 scripts/core_reference.py . <модули настройки> --constants-module
  … --constants …` по дереву диска): в пределе 32 768, но выше порога 90%
  (29 491). После `pin-update` первый бриф поднимет `warning`
  `brief.core_reference_near_limit` по `artel` сразу; SPEC мерил 26,7–26,8 КБ
  на b13c9e87 — дерево с тех пор выросло. Решение (сузить настройку или
  поднять предел) — за Оператором; при дальнейшем росте справочник
  перестанет включаться с алертом `incident`.
- Процесс роли может переписать файл кэша — принятый в SPEC риск: текст
  идёт как данные внутри границы.

## Предложения системе

- `scripts/core_reference.py` / SPEC К-3б: замер размера справочника в SPEC
  устаревает к разработке (26,7 КБ → 30,4 КБ за несколько мержей); порог
  предупреждения 90% артель пересекает уже на включении — стоило бы
  выбирать настройку с запасом под рост или замерять на голове main при
  гейте SPEC.
