---
task: 01M1P9QCHPHSCEA6TK13PV85SP
type: review
author_role: reviewer
status: changes_requested
iteration: 2
schema_version: 4
---

# REVIEW: Механика зон, часть 3: сверка диффа с зонами при переходе в ревью

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 / AC-1 | OK | `_zones_gate_refuses` (orchestrator/fsm_advance.py:525-591) реализует отказ, включая объединение `zones`/`zones_extension`/`COMMON_ZONES`; R1-F1 (код-ветка отставала от acceptance_tests артефактной ветки) закрыт — код-ветка теперь несёт все 6 файлов `acceptance_tests/`, `Ac1PreviouslyRecordedExtensionCountsAsZoneTest` зелёный. |
| 2 / AC-3 | НЕ ТАК | Формат PLAN/парсинг реализованы корректно (fsm_advance.py:471-522, 566-583), но `_answer_zones_mandate` (fsm_advance.py:505-522) не проверяет, что ANSWER-файл с маркером мандата реально пришёл от Оператора (`artel.py answer`) — см. R2-F1 (blocker), требование 2 SPEC фактически не гарантировано. |
| 3 / AC-4 | OK | Отказ — простой `return False`/`True`, `state()` остаётся `in_dev`, нового состояния FSM нет (`test_ac4_refusal_leaves_the_task_in_the_existing_in_dev_state` зелёный). |
| 4 / AC-7 | OK | Диф `tests/` этой итерации — только добавление `tests/test_zones_gate.py`, ни один существующий файл `tests/*.py` не тронут (сверено `git diff main...HEAD -- tests/`); докстринги «Ловит мутацию» — R1-F2 закрыт. |
| AC-2 | OK | `detail` перечисляет конкретные файлы; `test_ac2_refusal_names_the_exact_out_of_zone_files` зелёный. |
| AC-5 | OK | Отказ журналируется действием `"переход отклонён: гейт зон"` (тот же префикс, что и остальные отказы `advance`); `test_ac5_refusal_detail_surfaces_via_advance_refusal_history` зелёный. |
| AC-6 | OK | `zones = declared + list(config.COMMON_ZONES)`; `test_ac6_diff_touching_only_a_common_zone_path_passes_the_gate` зелёный. |

Реализация AC-1/AC-2/AC-4/AC-5/AC-6/AC-7 корректна и подтверждена тестами. AC-3 реализован НЕ ТАК, как сформулирован в SPEC/ANSWER-1: критерий требует, чтобы исключение открывалось «мандатом Оператора с явным согласием», а код принимает любой файл `tasks/<id>/ANSWER-*.md` на артефактной ветке с нужной строкой — независимо от того, кто и как его туда записал (R2-F1).

## Замечания

- **blocker** — `orchestrator/fsm_advance.py:505-522` (`_answer_zones_mandate`) — мандат Оператора на расширение зон (AC-3) проверяется ТОЛЬКО совпадением имени файла (`ANSWER-*.md` под `tasks/<id>/` на артефактной ветке) и наличием строки `Расширение зон разрешено: <пути>` в его тексте — без единой проверки, что этот КОНКРЕТНЫЙ файл действительно пришёл от команды Оператора `artel.py answer` (orchestrator/answer.py:60-93, `cmd_answer` пишет коммитом `"<id>: ANSWER-{n} — ответ Оператора"`, доступна только когда задача в состоянии `escalated`), а не от самой роли developer.

  Механизм автокоммита артефактов шага (`orchestrator/checkpoint.py:391-581`, `_commit_external_step_artifacts`) переносит в артефактную ветку ЛЮБЫЕ файлы, которые роль оставила в своём материализованном `tasks/<id>/` на диске (`files = {rel: content for rel, content in raw_files.items() if rel not in ignored}`, checkpoint.py:513-514 — без фильтрации по типу/автору на добавление, фильтр по типу есть только для УДАЛЕНИЯ, checkpoint.py:551) — коммитом с сообщением `"<id>: артефакты шага developer (автокоммит оркестратора)"`. Ничто в коде не мешает роли developer в своём собственном шаге `in_dev` (том самом, что вызывает `_zones_gate_refuses`) создать на диске `tasks/<id>/ANSWER-99.md` с текстом `Расширение зон разрешено: <любой путь>` — файл уйдёт в артефактную ветку тем же автокоммитом шага и будет неотличим от настоящего ответа Оператора для `_answer_zones_mandate` (сверка идёт по имени файла и тексту, `author_role` в frontmatter ANSWER не проверяется, а даже если бы проверялся — его тоже пишет тот же поддельный файл).

  Последствие: единственная функция AC-3 — потребовать РЕАЛЬНОГО согласия Оператора на расширение зоны — не работает как заявлено: разработчик может сам себе выписать «мандат» и провести любой дифф мимо гейта AC-1, целиком обесценивая задачу (SPEC, «Контекст»: «единственная страховка от выхода задачи за свои границы в коде»). Дополнительно опасно тем, что успешное расширение пишется в `tasks.zones_extension` (fsm_advance.py:579-581) и, по ANSWER-1 п.4/`Ac1PreviouslyRecordedExtensionCountsAsZoneTest`, навсегда засчитывается зоной для ВСЕХ последующих переходов задачи — один поддельный ANSWER даёт постоянное расширение, не разовое.

  Ни один из существующих тестов эту дыру не ловит: приёмочная песочница (`_sandbox.py::write_answer_mandate`) и юнит-тесты пишут/читают ANSWER-файл напрямую с диска через моки `disk_backed_show`/`disk_backed_ls_tree_files`, не моделируя, ЧЕЙ коммит его принёс — сценарий «ANSWER с маркером, но не от `cmd_answer`» не описан ни в одном тесте.

  Предложение: сверять происхождение конкретного ANSWER-файла тем же приёмом, что уже применяет `checkpoint._commit_external_step_artifacts` для распознавания «свой автокоммит» (`gitcmd.git("log", "-1", "--format=%s", branch, "--", rel)` + проверка префикса сообщения коммита) — засчитывать маркер `Расширение зон разрешено:` только из ANSWER-файла, последний коммит которого на артефактной ветке несёт сообщение по образцу `cmd_answer` (`f"{task_id}: ANSWER-{n} — ответ Оператора"`), а не любой автокоммит роли; добавить приёмочный/юнит-тест на отказ, когда маркер лежит в ANSWER-файле, коммит которого — автокоммит шага developer, а не `cmd_answer`.

- **minor** — `tasks/01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests/test_ac3_ac7_markers.py` и `test_ac7_existing_suite_marker.py` — оба файла несут одну и ту же пометку `# AC-7: skip` с почти идентичным обоснованием; `test_ac3_ac7_markers.py` после снятия эскалации AC-3 (ANSWER-2) остался пустым файлом-дублем разметки, не неся ничего, чего не несёт `test_ac7_existing_suite_marker.py`. Не влияет на гейт (guard берёт первую по алфавиту пометку, обе идентичны по смыслу), но лишний файл — предложение: удалить `test_ac3_ac7_markers.py`, оставив пометку AC-7 только в `test_ac7_existing_suite_marker.py`.

- **minor** — SPEC «Материалы» указывает разработчику «держать в уме» docs/invariants.md при PLAN («отказ по AC-1 добавляет новое ПРЕДУСЛОВИЕ... по образцу `budget_block`/`parallel_limit.refusal`») — соседние гейты того же перехода (лок `acceptance_tests/`, гейт ёмкости, потолок параллельности) заведены в таблице `docs/invariants.md` отдельными пронумерованными строками со ссылкой на покрывающий тест (см. строки 27, 32 таблицы). Гейт зон такой строки не получил, а `tests/test_invariants.py` не тронут. Не AC и не блокер (материалы — не критерий приёмки), но выбивается из установленной конвенции документирования предусловий перехода — предложение: добавить строку в таблицу инвариантов при следующей правке.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tasks/01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests/ | код-ветка несла устаревший снимок приёмочных тестов (отсутствовал тест AC-3 и др.) | — | подтверждено: код-ветка теперь несёт все 6 файлов `acceptance_tests/` идентично артефактной ветке (сверено `git show` code-branch байт в байт), 11/11 зелёных запуском ИЗ код-ветки |
| R1-F2 | accepted | tests/test_zones_gate.py | ряд unit-тестов без докстринга «Ловит мутацию:» | — | подтверждено: все перечисленные методы несут докстринг с формулировкой «Ловит мутацию:», переименование `test_file_zone_matches_as_prefix_of_unrelated_file` соответствует `assertTrue`; 14/14 зелёных |
| R2-F1 | open | orchestrator/fsm_advance.py:505-522 (`_answer_zones_mandate`) | мандат Оператора на расширение зон (AC-3) принимается по ЛЮБОМУ файлу `ANSWER-*.md`, попавшему в артефактную ветку, без проверки, что его коммит — реально `cmd_answer`, а не автокоммит шага developer | AC-3 не гарантирует то, что заявляет («мандат Оператора») — developer может подделать себе расширение зоны, которое к тому же навсегда осядет в `zones_extension` | — |

## Вердикт

changes_requested — один blocker (R2-F1: исключение AC-3 не проверяет происхождение мандата, developer может подделать «ответ Оператора» и обойти гейт зон целиком). R1-F1 и R1-F2 из прошлой итерации закрыты. Реализация AC-1/AC-2/AC-4/AC-5/AC-6/AC-7 корректна.

## Проверено исполнением

- `python3 -m unittest tests.test_zones_gate -v` — 14 тестов, все зелёные.
- `python3 -m unittest discover -s tasks/01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests -p "test_*.py" -v` — 11 тестов, все зелёные (запуск из код-ветки, HEAD совпадает с материализацией — R1-F1 больше не расхождение).
- `python3 -m unittest tests.test_advance_guard tests.test_advance_refusal_history tests.test_capacity_gate tests.test_store_schema_migration_parity tests.test_store_journal -v` — 26 тестов, все зелёные (соседние гейты того же перехода `in_dev -> review` и миграция схемы БД не задеты).
- `python3 scripts/codebase_map.py --check` — без вывода/ошибки, карта актуальна.
- `git diff main...task/01m1p9qchphscea6tk13pv85sp-mekhanika-zon-chast-3-sverka-d --stat` и постатейно по `orchestrator/fsm_advance.py`, `orchestrator/store.py` — полный дифф прочитан целиком (не только инкремент от прошлого вердикта): реализация `_zones_gate_refuses`/`_split_zone_paths`/`_touches_zone`/`_plan_zones_extension_paths`/`_answer_zones_mandate` и миграция `zones_extension` в `orchestrator/store.py`.
- `git diff main...HEAD -- tests/` — подтверждено: единственное изменение `tests/` этой веткой — новый файл `tests/test_zones_gate.py`, ни один существующий тест не изменён/удалён (AC-7).
- Прочитаны `orchestrator/checkpoint.py::_commit_external_step_artifacts`, `orchestrator/answer.py::cmd_answer`, `orchestrator/runner.py::role_cwd` целиком — подтверждён путь эксплуатации R2-F1: материализованный `tasks/<id>/` роли developer — обычная директория на диске, автокоммит шага переносит в артефактную ветку любые файлы без фильтра по типу на добавление, легитимный `cmd_answer` использует отдельное коммит-сообщение, но `_answer_zones_mandate` его не сверяет.
- Все 6 файлов `tasks/01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests/` в код-ветке прочитаны целиком и сверены логически с требованиями AC-1..AC-7 и ANSWER-1/ANSWER-2.

## Предложения системе

- Автокоммит артефактов шага (`checkpoint._commit_external_step_artifacts`) переносит в артефактную ветку любой файл, оставленный ролью в `tasks/<id>/`, без фильтра по типу на добавление (фильтр есть только для удаления, `_DELETABLE_ARTIFACT_TYPES`) — это уже отмеченное самим модулем историческое свойство («`author_role` лгал о происхождении», REVIEW T052), и эта задача показывает конкретный эксплуатируемый случай (R2-F1): любой код, который в будущем захочет опереться на «файл ANSWER-*.md = слово Оператора» (как уже делает `fsm._answer_file_count` для возврата из эскалации), наследует ту же дыру. Стоит рассмотреть общий примитив «этот путь последним коммитом был записан именно `cmd_answer`/`cmd_approve`», а не оставлять каждому потребителю изобретать свою проверку.
