---
task: 01M4M67SGNEYMN9F1C7XVX24XE
type: plan
author_role: developer
status: escalate
schema_version: 5
---

# PLAN: Этап 4 ADR-0021, часть A — мерж не кладёт в main снимок задачи и RETRO

## Подход

Шаг публикации мержа `fsm_merge_gate._publish_merge_artifacts` перестаёт
накладывать снимок ссылки документов (`_overlay_artifact_snapshot` удаляется)
и коммитить RETRO/долги (`fsm_postmerge._generate_and_commit_retro` и его
помощники удаляются). Вместо наложения первым шагом публикации идёт проверка
документов задачи на дереве `refs/artifacts/<id>` (новый
`_guard_task_docs_or_refuse`): ревизия — зафиксированная голова
(`tasks.fixed_sha`, без фиксации — голова ссылки), файлы читаются git-ом
(`ls-tree`/`show`) в репозитории задачи без выкладки на диск. Правила:
- любой проект — `guard.is_extraneous_task_root_file` (тот же критерий, что у
  `_guard_task_root_or_refuse`, включая подкаталоги);
- артель, в дереве мержа которой есть `scripts/guard.py` (там же, где их
  сегодня применял `guard --all` дерева мержа), — ещё правила `guard --all`
  к каталогу задачи: посторонние файлы
  `acceptance_tests/` (`is_extraneous_acceptance_test_file`, пропуск
  `__pycache__`), маркер AC-n с отступом (`indented_ac_marker_errors_from_files`),
  структура `.md` (`check_content`, паспорт пропускается) — БЕЗ освобождения
  по `docs/retro/<id>.md`: guard в `--all` освобождает закрытую историю, здесь
  проверяется живая мержащаяся задача.
Ссылки нет / ревизия не читается / файл не прочитан — отказ («merge FAILED»,
scratch снят, `sys.exit`, задача на `merge_gate`). Место — то же, где стояло
наложение: после приложений PLAN, до карты, `guard --all`, sha для push и
коммита закрытия. Правила берутся из guard пульта (он уже судил
`_guard_task_root_or_refuse`), не из `scripts/guard.py` дерева мержа: дерево
мержа каталога задачи больше не несёт.

`guard --all` по дереву мержа артели остаётся на месте (после карты, до
`final_sha`), видит приложения.

RETRO закрытия: sha коммита мержа (`gitcmd.head_sha(scratch)` сразу после
приложений, до публикации) и пути применённых приложений доезжают из
`_cmd_approve_merge_gate` до `cleanup._commit_closing(conn, id, merge_sha=,
applied_appendices=)` -> `snapshot.commit_closing(...)` -> текст
`retro.build_done(conn, id, merge_sha, address=ref)` +
`fsm_postmerge._with_appendices_line`. Без `merge_sha` (путь `kill`, прямые
вызовы) — прежний `gitcmd.head_sha()`.

Провал коммита закрытия: каждая ветка отказа `snapshot.commit_closing` (ссылки
нет, расхождение с фиксацией, git не ответил, исключение построения RETRO —
теперь перехватывается) журналируется, как сегодня, и поднимает
incident-алерт `snapshot.closing` с target проекта задачи; переход и уборка
идут дальше.

Читатели: `retro.build_done` без `address` пишет
`refs/artifacts/<id>` (`artifact_branch.branch_name`); `cleanup.artifacts_in_main`
— каталог в main ИЛИ голова ссылки в репозитории задачи (`artifact_branch.ref_head`).
`cleanup.drop_task_dir` остаётся на прежнем признаке «каталог в дереве main»
(вынесен в `_dir_in_main`): он бережёт отслеживаемый main каталог от rmtree, а
неотслеживаемая локальная копия задачи, чьи документы хранит ссылка, — хвост;
перевод его на ссылку оставлял бы каталог каждой убитой задачи и краснил
шесть методов `tests/test_kill_cleanup.py` (см. вопрос 4 эскалации).
`fsm_merge_gate._guard_task_root_or_refuse` сохранён без изменения поведения
(SPEC «Материалы»: его зовёт `test_guard_task_root_subdirectory.py`).

Тесты снятого механизма — по мандату ANSWER-1 п.1: удаляется
`tests/test_fsm_retro.py` и метод
`test_main_ci_line.py::GuardAllLaunchTest::test_task_retro_does_not_hide_snapshot_violation`;
смены ожидания — ровно три строки раздела «Меняемое поведение» SPEC. Замены —
долгоживущий `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`
(test_author, не правится).

## Шаги

1. `fsm_merge_gate.py`: удалить `_overlay_artifact_snapshot`; новый
   `_guard_task_docs_or_refuse` (+ чтение дерева ссылки); переписать
   `_publish_merge_artifacts` (проверка документов -> карта -> `guard --all`
   -> `final_sha`); в `_cmd_approve_merge_gate` — `merge_sha` после
   приложений и передача в `_commit_closing`. Докстринги.
2. `fsm_postmerge.py`: удалить `_generate_and_commit_retro`,
   `_write_and_stage_retro`, `_commit_retro`, `_retro_incident`; оставить
   `APPENDICES_RETRO_PREFIX`/`_with_appendices_line`.
3. `snapshot.py`: `commit_closing(..., merge_sha="", applied_appendices=None)`,
   инцидент на каждом провале, перехват исключения построения RETRO.
4. `cleanup.py`: `_commit_closing` пробрасывает аргументы; `artifacts_in_main`
   — по ссылке документов.
5. `retro.py`: адрес по умолчанию — `refs/artifacts/<id>`.
6. Тесты: удаление по мандату; три смены ожидания из SPEC; регенерация карты.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1, 2 |
| 3 | 1, 3 |
| 4 | 3, 4 |
| 5 | 2, 3 |
| 6 | 1 |
| 7 | 1 |
| 8 | 1 |
| 9 | 4, 5 |
| 10 | 1 |

## Влияние на систему

- Гейт посторонних файлов документов задачи не ослабляется: читает ту же
  голову, что раньше накладывалась, и строже — недоступная ссылка теперь
  отказ (раньше наложение деградировало до пустого каталога), освобождения по
  `docs/retro/<id>.md` нет.
- `guard --all` по дереву мержа артели сохранён на прежнем месте.
- Механизм killed-долгов снят; его заменяет коммит закрытия на пути `kill`
  с инцидентом на провале (требование 5).
- `docs/retro/*.md` в main больше не прирастает; `budget.py` его читает только
  по истории T-серии (SPEC «Не входит»).
- Откат — revert merge-коммита задачи.

## Риски

- Существующие тесты, которые доводят мерж до публикации без ссылки
  документов (прежнее наложение молча деградировало), теперь получат отказ —
  проверяется прогоном затронутых модулей и `suite-run`.
- Новые инциденты на провале коммита закрытия у задач без ссылки (старше
  ADR-0021) на пути `kill` — по требованию 4 это и есть желаемое.

## Проверки

- `python3 -m pytest tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py` —
  15 passed, 20 subtests (долгоживущий файл задачи, AC-1–AC-13).
- Затронутые модули (`test_plan_appendix`, `test_retro_artifact_branch_reads`,
  `test_snapshot_closing_outcome`, `test_main_ci_line`,
  `test_guard_task_root_subdirectory`, `test_merge_gate_ci_wait`,
  `test_full_suite_reuse`, `test_fsm_merge_gate_done_snapshot`,
  `test_kill_cleanup`, `test_artifact_ref_sync`,
  `test_doctor_artifact_branch_sync`, `test_01m41ab…`, `test_01m409…`,
  `test_01m446…`, `test_fsm_map_regen`, `test_01m42pencs…`) — зелёные, кроме
  `test_retro.py` (вопрос 1) и `FixesMainArgTest` (падает только в окружении
  процесса роли: «команда недоступна процессу роли developer»; в `suite-run`
  зелёный).
- `suite-run` №1: новые на ветке — ровно 4 падения, все перечислены в
  эскалации; на базе падений нет.
- `plank-run`: планка задачи — только перечень долгоживущих файлов,
  `test_*.py` нет («pytest не запускался»); долгоживущий файл прогнан напрямую.
- Карта кодовой базы регенерирована (`python3 scripts/codebase_map.py`).

## Предложения системе

- Сверка SPEC «Меняемое поведение» с кодом (аналитик/аудит на передаче)
  пропустила три утверждения, которые требования 1, 7, 9 опрокидывают прямо:
  `test_retro.py:195`, `test_01m3sf7…_main_ci.py:482`, фикстуры
  `test_invariants.py` без ссылки документов. Дешёвая проверка до гейта SPEC:
  grep по `tests/` литералов снимаемого поведения (здесь — «:tasks/{»,
  «снимок артефактной ветки», `origin_tree_has(...tasks/`).

## Эскалация

**Вопросы** (по блокирующести; код и долгоживущий файл задачи готовы, ветка
красна только этими тестами):

1. `tests/test_retro.py::RetroGenerationTest::test_build_done_has_merge_sha_address_and_first_context_line_only`
   — требование 9 / AC-13 (адрес по умолчанию `refs/artifacts/<id>`) прямо
   противоречит утверждению
   `self.assertIn("deadbeef" * 5 + f":tasks/{self.TASK}/", text)`; в разделе
   «Меняемое поведение» метода нет. Предлагаемая смена:
   → `self.assertIn(f"Адрес артефактов: refs/artifacts/{self.TASK}", text)`.
   Варианты: а) мандат на эту смену (строкой «Меняемое поведение» SPEC или
   ANSWER); б) иное решение по требованию 9. Дефолт — а).
2. `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py::MergeGuardAfterSnapshotTest::test_ac1_clean_snapshot_merges_as_before`
   — требование 1 (каталога задачи в main нет) противоречит утверждению
   `self.assertTrue(self.origin_tree_has(f"{task['dir']}/acceptance_tests/test_ac1_fixture.py"), self.msg(out))`.
   Предлагаемая смена: → `self.assertFalse(self.origin_tree_has(f"{task['dir']}/acceptance_tests/test_ac1_fixture.py"), self.msg(out))`
   (прочие утверждения метода — `done`, main сдвинут — остаются). Варианты:
   а) мандат на смену; б) удаление утверждения. Дефолт — а).
3. `tests/test_invariants.py::MergeOnlyFromMergeGateTest::test_merge_gate_approve_is_that_path`
   и `tests/test_invariants.py::MergeNeedsGreenCiTest::test_green_ci_merges` —
   песочница `FsmTest` не исполняет git, ссылки документов у задачи нет, и
   требование 7 / AC-11 («ссылки нет» — отказ мержа) отказывает там, где
   метод ждёт `done` («ссылки документов refs/artifacts/<id> нет в
   репозитории задачи»). Утверждения менять не нужно — фикстуре нужна
   ссылка. `tests/test_invariants.py` — путь «только чтение» SPEC. Варианты:
   а) Оператор правит фикстуру (`amend-tests`/коммит Оператора): в этих двух
   методах подменить `fsm_merge_gate._task_docs_files` на чистое дерево
   (`return ("<sha>", [f"tasks/{TASK}/SPEC.md"], "")`) либо научить шпион
   git отвечать за `refs/artifacts/<id>`; б) мандат разработчику на ту же
   правку фикстуры с расширением зон на `tests/test_invariants.py`;
   в) ослабить требование 7 для задачи без фиксации — не предлагаю: AC-11
   долгоживущего файла это запрещает. Дефолт — б).
4. (не блокирует, подтверждение интерпретации) `cleanup.drop_task_dir`
   оставлен на признаке «каталог в дереве main», а не на новом
   `artifacts_in_main` (см. «Подход»). Варианты: а) так и оставить
   (дефолт); б) перевести на `artifacts_in_main` — тогда нужен мандат на
   смену ожидания шести методов `tests/test_kill_cleanup.py`
   (`KillCleanupTest::test_branch_only_artifacts_and_branch_are_removed`,
   `::test_cleanup_is_listed_in_the_journal`,
   `::test_dir_committed_into_a_foreign_branch_is_left_alone`,
   `::test_dir_staged_on_main_is_left_alone`,
   `::test_repeated_kill_finds_nothing_and_does_not_fail`,
   `CleanupWithoutGitTest::test_unreadable_index_keeps_the_dir`).

**Контекст.** Реализованы требования 1–10: `fsm_merge_gate.py`
(`_guard_task_docs_or_refuse`, `_publish_merge_artifacts`, `merge_sha` в
`_cmd_approve_merge_gate`), `fsm_postmerge.py` (снят коммит RETRO и долгов),
`snapshot.py` (sha мержа, строка приложений, инцидент `snapshot.closing` на
каждом провале), `cleanup.py`, `retro.py`, карта. По мандату ANSWER-1 удалены
`tests/test_fsm_retro.py` и
`tests/test_main_ci_line.py::GuardAllLaunchTest::test_task_retro_does_not_hide_snapshot_violation`;
три смены ожидания из «Меняемое поведение» внесены. Тесты из вопросов 1–3 не
тронуты (красные на ветке). `suite-run` №1 — лог
`.artel/logs/suite-run/01M4M67SGNEYMN9F1C7XVX24XE/01M4M67SGNEYMN9F1C7XVX24XE-suiterun-1.log`.

**Блокирует.** Сдачу `ready`: без мандата по вопросам 1–3 ветка красна на
четырёх существующих тестах, а их правка без мандата откажет рубежом
неослабления.
