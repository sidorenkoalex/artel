---
task: 01M46C776SZEMYPBQGPNJN1TXY
type: plan
author_role: developer
status: escalate
schema_version: 5
---

# PLAN: Полный прогон tests/ пульта на дереве «ветка плюс приложения PLAN»

## Подход

Общий узел — новый модуль `orchestrator/appendix_tree.py`; в него вынесено
наложение приложений из гейта мержа, и им же пользуются три полных
прогона ветки.

- `apply_in_order(tree, appendices, already_applied)` накладывает
  приложения подряд, в порядке PLAN, тем же `advance_gates/plan_appendix.py::git_apply`.
  Возвращает пути наложенных и первое неприменимое (`Inapplicable`: номер,
  приложение, ответ git). Гейт мержа (`fsm_merge_gate._apply_plan_appendices`)
  теперь вызывает его, а не свой цикл, и передаёт
  `already_applied=_appendix_already_in_main`. Отказ, коммит, прогон по
  `_FULL_SUITE_APPENDIX_PREFIXES` и тексты журнала не меняются (требование 7).
- `read_plan(conn, id)` читает PLAN.md из ссылки документов
  (`artifact_source.resolve` + `artifact_branch.show`) и разбирает его
  `guard.plan_appendices`. Это источник гейта мержа, и
  `_plan_appendices_or_refuse` читает PLAN через него с прежним текстом
  записи «приложения PLAN не прочитаны».
- Контекстный менеджер `suite_tree(conn, id, wt, branch=None)` отдаёт
  `SuiteTree(root, note, refusal, warning)`:
  - задача не артели (`repo_context.is_artel`) или в PLAN нет
    приложений → `root = wt`, прогон идёт как раньше (требование 3);
  - ошибки разбора PLAN → `root=None`, отказ;
  - иначе `git worktree add --detach` во временный каталог
    (`tempfile.mkdtemp`). Если задан `branch`, дерево ставится на голову
    ветки задачи (автогейт, approve). Если нет — на HEAD рабочей копии, и в
    дерево копируются её незакоммиченные правки: изменённые, удалённые и
    неотслеживаемые неигнорируемые файлы (`git diff --name-only
    --no-renames HEAD` + `ls-files --others --exclude-standard`). Это вход
    `suite-run`. Рабочая копия при этом только читается. Затем
    `apply_in_order`; приложение, уже наложенное в дереве (`git apply
    --reverse --check`), пропускается тем же правилом, что на гейте мержа,
    и называется в признаке;
  - если не ответил git (`rev-parse`, `worktree add`, листинг правок),
    упало копирование или приложение неприменимо → `root=None` и отказ
    без прогона (fail-closed, требование 4). Отказ наложения называет
    номер и пути: «приложение N PLAN (пути) не накладывается на дерево
    прогона: <git>»;
  - в `finally` выполняются `git worktree remove --force`, `rmtree` и
    `git worktree prune`, на любом исходе, включая исключение внутри
    `with` (требование 2).
  - `SuiteTree.mark(detail)` дописывает к detail признак
    «[с приложениями PLAN: <пути>]» (требование 5). Если PLAN не прочитан,
    в detail пишется причина «[без приложений PLAN: …]», и прогон идёт без
    приложений, как на гейте мержа. Журнал для этого случая не пишется:
    `_autogate_conditions` не получает соединения с БД, юнит-тесты
    передают `object()`.
- Подключение:
  - `fsm_autogate._autogate_conditions`: при отказе узла — «автогейт:
    <причина>»; условие «полный набор зелёный» и отказ по красному набору
    помечаются через `mark`;
  - `fsm._acceptance_full_suite_ok`: при отказе узла — «approve
    отклонён», и `--accept-red` его не снимает (принимается краснота
    прогона, а прогона не было); записи зелёного, красного и
    `--accept-red` помечаются через `mark`;
  - `suite_run._run`: прогон ветки идёт на `suite_tree(conn, id, wt)`, при
    отказе — отчёт «отказ — …» с `green: False`, так что `--wait`
    завершается кодом 1. В отчёт добавлена строка «прогон ветки
    [с приложениями PLAN: …]». Прогон базы `_base` не менялся: дерево базы
    строится без приложений задачи (требование 6).

Оценку бюджета не меняю.

## Шаги

1. `orchestrator/appendix_tree.py`: `apply_in_order`, `read_plan`,
   `suite_tree`, `SuiteTree.mark`, перенос незакоммиченных правок.
2. `orchestrator/fsm_merge_gate.py`: наложение и чтение PLAN переведены на
   общий узел без изменения поведения.
3. `orchestrator/fsm_autogate.py`, `orchestrator/fsm.py`,
   `orchestrator/suite_run.py`: прогоны на `suite_tree`.
4. `tests/test_appendix_tree.py`: юнит-тесты свойств, которых нет в
   долгоживущих файлах (перенос удалённого и неотслеживаемого файла;
   приложение, уже наложенное в дереве). Регенерация
   `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 3 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1, 3 |
| 5 | 1, 3 |
| 6 | 3 (база `suite-run` не тронута) |
| 7 | 2 |

## Влияние на систему

- Гейт мержа: порядок, условия, тексты отказов и прогон по
  `_FULL_SUITE_APPENDIX_PREFIXES` прежние. Цикл перенесён в
  `apply_in_order` без изменения логики. Зелёные:
  `tests/test_plan_appendix.py`,
  `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`,
  `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`,
  `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`.
- Автогейт и approve без приложений и вне артели гоняют набор, как
  раньше, в `workspace.path`. Проверки по-прежнему зелёные:
  `tests/test_fsm_autogate.py`, `tests/test_fsm_autogate_long_lived.py`,
  `tests/test_approve_acceptance_full_suite.py`,
  `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py`, `test_model_sets`,
  `test_long_lived_transitions`, `test_suite_run`,
  `test_01m462qaceh29rprd2rzhghqfm_suite_run`.
- Ни один гейт не ослаблен. Новый отказ (приложение неприменимо, git не
  ответил) стоит раньше прогона и закрыт по умолчанию. `--accept-red`
  отказа узла не снимает.
- Итог гейта по sha (`acceptance._remember_gate_failures`) с дерева с
  приложениями не сохраняется, потому что дерево грязное
  (`clean_tree_sha` → `None`). Итог базы `suite-run` не загрязняется
  итогом ветки с приложениями.
- Откат — revert merge-коммита задачи.

### Проверено исполнением
- `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py`: 9 passed.
- `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`: на ветке
  5 passed, 9 failed, причина — в эскалации. Временная копия этого файла с
  `test_profile` в фикстуре `TARGETS_YAML` (дифф ниже; копия удалена,
  зафиксированный файл не правился): 14 passed.
- Мутация «приложения в обратном порядке» в `apply_in_order` даёт красные
  `AppendixOrderTest`, `MergeGateUnchangedTest` (временная копия) и
  `suite_run_appendix::OrderTest`. Мутации «без `ls-files --others`» и
  «без `already_applied`» дают красный `tests/test_appendix_tree.py`.
- `suite-run` №1/№2 (полный набор, пульт): упало 10 — 9 из них в
  `test_01m46c776…_appendix_gates.py` (эскалация) и
  `tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`.
  Последний к диффу не относится: в PATH роли нет `/bin`
  (`shutil.which('ps')` → `None`), и `liveness._group_member_count`
  возвращает 0.

## Риски

- `suite-run` копирует незакоммиченные правки файлами. Игнорируемые
  файлы (`.gitignore`) в дерево не попадают, при прогоне в рабочей копии
  они были бы видны. Для кода задачи это верно, но кэш, сгенерированный
  ролью, в прогоне не участвует.
- Временное дерево разворачивается на каждом прогоне с приложениями:
  checkout дерева пульта, это секунды.

## Предложения системе

- Долгоживущие тесты пишутся на пине до подтяжки main и становятся
  неисполнимыми, когда main меняет предусловия (здесь —
  01M45FJVGQT1K0P8HDEXZX6HS7: у артели без `test_profile` автогейт и
  гейт мержа отказывают). Нужна проверка планки после подтяжки main в
  `tests_writing`/`in_dev` до шага developer: сейчас это всплывает только
  у разработчика, лок не даёт ему починить фикстуру, и цена — цикл
  эскалации.
- В PATH процесса роли нет `/bin`: `ps`, `ls`, `cat` не находятся. Из-за
  этого `tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`
  красен в любом прогоне роли, включая `suite-run`, фон которого
  наследует окружение роли (`orchestrator/runner.role_env`).

## Эскалация

Код причины: долгоживущий тест расходится с main после подтяжки (фикстура,
а не устройство кода).

**Вопросы**

1. (блокирующий) Фикстура
   `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py::TARGETS_YAML`
   описывает артель без `test_profile`. После подтяжки main (8aa3ba90,
   приходит с 01M45FJVGQT1K0P8HDEXZX6HS7) `project_profile.decide` даёт
   артели без профиля отказ (ADR-0002). Поэтому автогейт пишет «автогейт
   приёмки пропущен: у проекта «artel» нет поля test_profile», а гейт
   мержа останавливается на `_profile_refusal_exit`. Тесты писались на пине
   7934bf2a, где этого правила ещё не было. На ветке красны 9 методов:
   `AutogateAppendixTest::test_ac1_…`, `AppendixOrderTest::test_ac4_…`,
   `WorkingCopyIntactTest::test_ac5_autogate_…`,
   `InapplicableAppendixTest::test_ac6_autogate_…`,
   `GitFailureTest::test_ac7_…`, `TempTreeRemovedTest::test_ac8_…`,
   `NoAppendixTest::test_ac9_plan_without_appendices_…`,
   `JournalMarkTest::test_ac10_autogate_…`, `MergeGateUnchangedTest::test_ac12_…`.
   Все методы approve зелёные. Предлагаю `amend-tests`: дописать профиль
   артели в фикстуру. Утверждения не меняются, меняются только тестовые
   данные. С этой правкой все 14 методов файла зелёные на коде ветки.
   Патч применяется (`git apply --check` на чистом дереве ветки — OK):

   ```
   diff --git a/tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py b/tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py
   index 780818f7..9a81b4c3 100644
   --- a/tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py
   +++ b/tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py
   @@ -60,6 +60,12 @@ TARGETS_YAML = """targets:
        no_paths: []
        project_skills: []
        merge_gate: operator
   +    test_profile:
   +      command: [python3, -m, pytest]
   +      long_lived_dir: tests
   +      long_lived_name: test_<id>_<name>.py
   +      weakening_scope: [tests/**/*.py]
   +      mutation_claim_scope: [tests/test_*.py]
    """

    GATES_YAML = "gates:\n  acceptance: auto\n"
   ```

   Варианты: (а) `amend-tests` с этим патчем; (б) иной текст профиля на
   усмотрение Оператора/test_author. Дефолт при молчании — (а).

**Контекст.** Реализация готова (раздел «Подход»). Файл `suite_run_appendix`
зелёный, все гейты по approve зелёные, гейт мержа проверен на временной
копии файла с профилем. Код в worktree не закоммичен, его коммитит пульт.

**Блокирует.** Выход из `in_dev`: зафиксированный долгоживущий файл на
ветке красный не из-за кода задачи, а из-за фикстуры, которую разработчик
править не вправе.
