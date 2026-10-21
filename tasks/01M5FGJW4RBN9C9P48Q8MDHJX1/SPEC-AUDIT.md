---
task: 01M5FGJW4RBN9C9P48Q8MDHJX1
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/, tests/sandbox.py, tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py; в) пути-признаки (гейты): orchestrator/fsm_merge_gate.py"
spec_sha: 31ad09b75bfe6137469af66948353d4b7caa2dc3
schema_version: 5
---

# SPEC-AUDIT: Ветка задачи task/… удаляется из origin после мержа

Круг 2: SPEC после возврата с гейта SPEC (решения Оператора О-1…О-4 и
фраза о PR).

## ТЗ и SPEC
- ТЗ п.1–7 отражены в SPEC п.1–8; ограничение зон по смыслу — SPEC п.7;
  «Не входит» перенесено полностью.
- Решения Оператора круга 1 отражены: О-1 — SPEC п.2 (`gitcmd.in_repo`
  с пределом, gitcmd.py не меняется); О-2 — AC-1 (аргументы обоих
  вызовов); О-3 — AC-6(а)/(б)/(в); О-4 — SPEC п.3 (подсказка при `None`
  на push, без подсказки при исключении); фраза о PR — SPEC п.6, AC-9.
- Требований сверх ТЗ и решений нет. Отступление от ТЗ п.2 («читается
  `remote_ref_state`») снято решением О-1 — не отклонение.
- Мелочь формулировки: ТЗ п.5 и SPEC п.5 / AC-8 «после мержа пульт не
  вызывает … других команд `gh`» — буквально ложно для существующего
  поведения (см. «Проверяемость», AC-8); по смыслу ТЗ — «новая уборка
  не вызывает `gh`».

## Факты против кода
Подтверждено:
- `_push_merged_main` — orchestrator/fsm_merge_gate.py:1284, `"moved"`
  возвращается до `_finalize_done_state` (fsm_merge_gate.py:1524–1525).
- Порядок после push — fsm_merge_gate.py:1526–1531: `_finalize_done_state`,
  `cleanup._commit_closing`, `_cleanup_merged_task(conn, task_id, branch)`,
  `_await_main_ci`, `_rebuild_core_reference`; `final_sha` в области
  видимости (fsm_merge_gate.py:1521).
- `_cleanup_merged_task` — fsm_merge_gate.py:1352, подпись
  `(conn, task_id, branch)`; единственная подмена в тестах —
  tests/test_merge_gate_ci_wait.py:415 `lambda *a, **k: None`.
- Приём перехвата — `_rebuild_core_reference` fsm_merge_gate.py:1535
  (`except Exception` + `contextlib.suppress`).
- `_left_reason` cleanup.py:229, `_delete_origin_branch` cleanup.py:253
  (`push origin --delete <branch>` короткой ссылкой, `res.returncode` без
  проверки `None` — `AttributeError` подтверждён), `cleanup_project_remote`
  cleanup.py:266 (одна запись «уборка», исходы через «; », печать
  `f"  {note}"`).
- `remote_ref_state` gitcmd.py:673 — три исхода ровно как в SPEC п.2.
- `is_ancestor` gitcmd.py:260 — несуществующий sha → `False`.
- Токен внешнего проекта для `ls-remote`: `HOSTING_SUBCOMMANDS`
  (gitcmd.py:35) включает `ls-remote`, `_hosting_project`
  (gitcmd.py:92) пропускает пары `-C`/`-c` — чтение головы через
  `gitcmd.in_repo(<клон>, "-c", …, "ls-remote", …)` получит слот, как
  push у kill.
- Предпосылка «голова в origin — предок `final_sha`» держится: мерж —
  `git merge --no-ff <branch>` (fsm_merge_gate.py:803), `final_sha` —
  потомок коммита мержа (карта/приложения поверх, fsm_merge_gate.py:1520–1521).
- Канарейка до `done` не доходит — `_kill_at_merge_gate` canary.py:1387.
Неточность (не блокирует): AC-1 ссылается «по образцу»
tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py:581 — там
предел проверяется временем исполнения против молчащего хостинга, а не
разбором аргументов вызова; AC-1 же прямо требует проверки аргументов.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | вызов уборки не добавлен в `_cleanup_merged_task`; удаляется не `refs/heads/<branch>`; снят `-c http.lowSpeed*` с `ls-remote` или push; исход не напечатан/не записан; удалена `refs/artifacts/<id>` |
| AC-2 | да | push удаления выполняется и при пустом выводе `ls-remote` |
| AC-3 | да | нет проверки `is_ancestor` — ветка с чужим коммитом удаляется; подсказка удаления печатается или пишется в журнал |
| AC-4 | да | исключение/`sys.exit` при отказе push; подсказка пишется в журнал; `_await_main_ci` не вызывается |
| AC-5 | да | push без `--force-with-lease=…:<sha>` — сдвинутая ветка удаляется |
| AC-6 | частично | (а) `None` на чтении роняет `AttributeError`; (в) `None` на push; (г) исключение не перехвачено. Не ловится: подсказка `ls-remote` + удаление не печатается при ненулевом коде `ls-remote` (б) — AC-6(б) подсказок не проверяет, хотя SPEC п.3 требует её для «origin не ответил на чтение» |
| AC-7 | да | уборка зовётся до проверки `"moved"` или на отказе гейта; пустая ветка пишет журнал |
| AC-8 | частично | kill артели начинает удалять ветку — ловится; «после мержа пульт не вызывает команд `gh`» буквально не проверяем: `_await_main_ci` (fsm_merge_gate.py:635, 652) зовёт `ci.main_line_status` → `gh` после мержа у артели |
| AC-9 | да | абзац/фраза о PR в docs/retention.md отсутствует |

Отклонения:
1. **Форма подсказки удаления при несчитанной голове не задана.** SPEC
   п.3 (вторая подпозиция) и AC-6(а): «затем та же команда удаления с
   прочитанной головой», `--force-with-lease=refs/heads/<branch>:<sha>`,
   — но голова не прочитана, `<sha>` подставить нечем. Литерал `<sha>`
   (заглушка для Оператора), пустая аренда, `$(…)`? Автор планки и
   разработчик разойдутся; планка, требующая конкретную строку, — повод
   эскалации «тест-навязывает-устройство».
2. **AC-8 «после мержа пульт не вызывает команд `gh`»** противоречит
   существующему `_await_main_ci` (fsm_merge_gate.py:652) у артели;
   проверяемо только как «новая уборка не вызывает `gh`».
3. **AC-6(б) без подсказок** — SPEC п.3 требует подсказку `ls-remote` +
   удаление для любого «origin не ответил на чтение», AC проверяет её
   только для `None` (AC-6(а)).

## Зоны
- Код: orchestrator/cleanup.py (новая функция, расширение
  `_delete_origin_branch`), orchestrator/fsm_merge_gate.py
  (`_cleanup_merged_task` и её вызов на :1529), docs/retention.md
  (раздел :29), tests/ — всё в зонах.
- docs/codebase-map.md регенерируется — общая зона (`config.COMMON_ZONES`).
- Защищённые пути (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`,
  `.github/`) не затрагиваются; песочница ролей не расширяется.
- gitcmd.py, workspace.py, repo_context.py — только чтение; новых
  помощников там не требуется (О-1).

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `_delete_origin_branch` разбирает `None` | kill внешнего проекта удаляет ветку с пределом lowSpeed — tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py:572–605 | да, вызов kill прежний | тот же тест + AC-6(в) | остаётся |
| kill артели | не удаляет ветку в origin — tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py:609 | да | тот же тест + AC-8 | остаётся |
| `_cleanup_merged_task` получает `final_sha` | уборка worktree/локальной ветки — tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py:424; подмена tests/test_merge_gate_ci_wait.py:415 | да (`*a, **k`) | те же тесты | остаётся |
| шаги после push | `"moved"` до done, `_await_main_ci`/`_rebuild_core_reference` после уборки — tests/test_merge_gate_ci_wait.py, tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py:491 | да, сбой уборки перехвачен | AC-4, AC-6(г), AC-7 | остаётся |

Раздела «Меняемое поведение» в SPEC нет; ожиданий существующих тестов
задача не меняет (теста на `AttributeError` при `None` в kill нет) —
раздел не нужен.

## Пути обхода гейтов
- AC-5 можно «выполнить» подменой: тест подменяет `in_repo` на чтении и
  проверяет лишь, что в аргументах есть `--force-with-lease` — без
  сдвига ветки в настоящем bare-origin. SPEC прямо требует, что ветка
  в origin сдвинута потомком и остаётся — обход закрыт формулировкой.
- `is_ancestor` в клоне: разработчик мог бы сравнивать голову с
  `merge_sha`, а не `final_sha` — для предка разницы нет (merge_sha —
  предок final_sha), обхода нет.
- Перехват «любого исключения» мог бы скрыть исключение в самой записи
  журнала, и исход не попал бы никуда; AC-6(г) требует исход в журнале —
  достаточно. Новых путей обхода не найдено.

## Вердикт
concerns — SPEC ведётся дальше, Оператору на гейте решить:
1. SPEC.md п.3 (подпозиция «origin не ответил на чтение») и AC-6(а):
   форма `<sha>` в подсказке удаления, когда голова не прочитана, не
   задана (литерал-заглушка или иное).
2. SPEC.md п.5 и AC-8 «после мержа пульт не вызывает команд `gh`» —
   против orchestrator/fsm_merge_gate.py:652 (`_await_main_ci` →
   `ci.main_line_status` → `gh`); уточнить «новая уборка не вызывает `gh`».
3. AC-6(б) не проверяет подсказки, требуемые SPEC п.3 для ненулевого
   кода `ls-remote`.
4. Мелочь: ссылка «по образцу» на
   tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py:581 —
   там предел проверяется временем, не аргументами.
