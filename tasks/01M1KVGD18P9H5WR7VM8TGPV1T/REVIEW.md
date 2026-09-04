---
task: 01M1KVGD18P9H5WR7VM8TGPV1T
type: review
author_role: reviewer
status: changes_requested
iteration: 3
schema_version: 3
---

# REVIEW: Изоляция тестов от настоящего репозитория: артефактная ветка из песочницы

## Соответствие SPEC

`SPEC.md`/`PLAN.md` на диске совпадают байт-в-байт с пакетом (sha256
пересчитан локально и сверен). В отличие от итерации 2, на этот раз
developer фактически ответил на `ANSWER-2`: `git diff b3654b84 HEAD
--stat` (`b3654b84` — коммит вердикта итерации 2) показывает правки в
8 файлах — `orchestrator/doctor.py`, `PLAN.md`, `_util.py`,
`tests/sandbox.py`, `tests/test_doctor.py`,
`tests/test_fsm_branch_correct_status_reads.py`,
`tests/test_gitcmd_carpentry.py` (плюс `docs/operator-session.md` —
пришло подтяжкой main, не работа developer). Реестр закрывается ниже
пункт за пунктом; сверх шести замечаний итерации 1 нашёл один
регрессионный дефект (сценарий «сирота найден, но не удалён» в
CLI-выводе `doctor --fix`) и одно новое замечание (карта кодовой базы
не перегенерирована после правки `*.py`), плюс подтверждённый
эмпирически риск в реализации требования 1 (см. «Замечания»).

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (инвариант-тест: sandbox + CI) | реализовано, но с дефектом | `tests/sandbox.py::TmpRootTest.setUp`/`tearDown` (строки 478-552) реализуют рантайм-рубеж по ANSWER-2 п.2 — код есть, структурно верен, `real_repo_refs`/`_REAL_ROOT`/`_REAL_RUN` на месте. Но при прогоне полного `tests/` в этом рабочем дереве (которое, по признанию самого PLAN «Риски», делит `refs/heads/*` с главной копией пульта) рубеж СЛОЖИЛ ложный красный на тесте, не имеющем отношения к git-изоляции — см. «Замечания» ниже, empирически воспроизведено в этой же ревью-итерации. |
| 2 (единая точка подмены) | OK | `gitcmd.carpentry` и перевод `write_commit`/`commit_files` — без изменений с итерации 1, повторно подтверждено. |
| 3 (миграция `PreviousVerdictShaTest`) | OK | Без изменений — подтверждено прогоном `tests.test_review_package` (см. «Проверено исполнением»). |
| 4 (уборка сирот) | реализовано не так | `git branch -D` возврат теперь проверяется (R1-F3 закрыт по существу для `sweep_orphan_artifact_branches` и incident-алерта), но `cmd_doctor` (строки 1153-1164) печатает «Осиротевших артефактных веток не найдено» и в сценарии «сироты найдены, но НИ ОДНО удаление не удалось» — тот же класс ложного вывода, который R1-F3 просил закрыть целиком, закрыт только наполовину. |
| 5 (защищённые пути — диффом) | OK | Три unified-диффа перепроверены `git apply --check` заново на свежем `git worktree add --detach` от текущего `main` — применяются без конфликтов. |

## Замечания

- major — `tests/sandbox.py:478-552` (`TmpRootTest.setUp`/`tearDown`,
  ANSWER-2 п.2/R1-F2) — рантайм-рубеж сравнивает ПОЛНЫЙ снимок
  `refs/heads/`+`refs/artifacts/` НАСТОЯЩЕГО репозитория пульта до и
  после КАЖДОГО теста-наследника (таких классов — 40+ файлов, у
  большинства базового `tests/`). В этом рабочем дереве `config.ROOT`
  разделяет эти refs с главной копией пульта, где параллельно работают
  другие роли/сессии (тот же факт, который PLAN «Риски» уже признаёт
  для AC-1) — но раньше этому риску был подвержен только один
  специфический acceptance-тест, а после этой правки риску подвержен
  ЛЮБОЙ из 1425+ тестов пакета `tests/`, включая тесты, вообще не
  трогающие git. Воспроизведено прямо в этой ревью-итерации:
  `python3 -m unittest discover -s tests -v` (1425 тестов, 227.7с) упал
  с единственным провалом —
  `test_step_refixation.OwnStepCommitRefixesWithoutIncidentTest.
  test_ordinary_refusal_reason_is_kept` (тест не про git-изоляцию и не
  тронутый этой задачей) — `tearDown` сообщил: ссылка
  `refs/heads/task/01m1nktf173wv5cpdz1c3ww69k-artefakty-roli-iz-
  artefaktnoy` сдвинула sha
  (`9a2d75950e2fe6ccf29a8f027367063753a265a4` →
  `e828202341790575becdc8ebaeefbe72694b4dd2`) между `setUp` и
  `tearDown` ЭТОГО теста — явно чужой коммит другой активной задачи
  (`01M1NKTF173WV5CPDZ1C3WW69K`), не утечка кода этой задачи. Изолированный
  повторный прогон того же теста в одиночку — `ok` (1.7с), что
  подтверждает: дефект не в самом тесте, а в ширине рубежа. Сценарий
  поломки: любой будущий прогон полного набора тестов в рабочем
  дереве, разделяющем `config.ROOT` с главной копией (штатный режим
  этой системы, судя по интенсивности параллельных задач, видной в
  `git log` за время этой ревью), может упасть на случайном
  неотношимом тесте из-за чужого коммита в чужую ветку задачи —
  ложноположительный `changes_requested`/красный CI для будущих
  разработчиков и ревьюверов, не имеющих отношения к этой задаче.
  Предложение: сузить рубеж (например, сравнивать не весь снимок
  `refs/heads/`+`refs/artifacts/`, а только те ссылки, которые реально
  затронуты подмененными `SpyRun`/`gitcmd`-вызовами ЭТОГО теста, раз
  `sandbox.py` их и так перехватывает), либо ограничить дорогой рубеж
  только специализированными acceptance-тестами этой задачи
  (`test_ac1_full_suite_ref_isolation.py`) и CI-сторожем, как исходно
  и предполагал `PLAN.md` «Подход» до ANSWER-2 (тогда «дорогая
  половина» инварианта явно называлась прерогативой CI-чекаута, не
  общего рабочего дерева). Раз мандат ANSWER-2 п.2 буквально требовал
  именно рубеж на уровне базового класса — если сузить его без потери
  сути невозможно, вопрос стоит вернуть Оператору отдельным пунктом
  (эмпирическое доказательство приложено выше), а не просто повторять
  как открытое замечание из итерации в итерацию.

- major — `orchestrator/doctor.py:1153-1164` (`cmd_doctor`) — при
  `fix=True` вывод строится по `if removed:` , где `removed =
  sweep_orphan_artifact_branches(conn)` теперь возвращает ТОЛЬКО
  фактически удалённые ветки (после правки R1-F3). Если сироты
  НАЙДЕНЫ, но ВСЕ попытки `git branch -D` провалились (например ветка
  где-то checked out), `sweep_orphan_artifact_branches` честно заводит
  incident-алерт с текстом «НЕ удалены (ошибка git branch -D): …», но
  `removed` при этом пуст — и `cmd_doctor` печатает
  «Осиротевших артефактных веток не найдено.», хотя они найдены и не
  убраны. Оператор, вызвавший `doctor --fix` вручную (SPEC требование
  4: «служебное действие... по явному вызову Оператора»), увидит в
  консоли обнадёживающее «не найдено», в то время как журнал алертов
  говорит обратное — расхождение CLI-вывода и журнала для одного и
  того же события. Ни `tests/test_doctor.py::
  OrphanArtifactBranchSweepTest::test_failed_deletion_is_not_reported_
  as_deleted` (проверяет только возврат функции и текст алерта), ни
  `test_cmd_doctor_fix_sweeps_once_and_lists_output` (мокает
  `sweep_orphan_artifact_branches` c `return_value=["artifact/t777"]`
  — всегда «успех»), ни приёмочный
  `tasks/01M1KVGD18P9H5WR7VM8TGPV1T/acceptance_tests/
  test_ac4_orphan_artifact_branch_cleanup.py` не покрывают сценарий
  «найдены, но ни одна не удалена» на уровне `cmd_doctor`. Это тот же
  класс дефекта, который R1-F3 просил закрыть целиком («ложное
  ...в выводе... алерте») — закрыта только алертная половина.
  Предложение: `cmd_doctor` должен различать «сирот не найдено» и
  «сироты найдены, но не удалены» — печатать отдельную честную строку
  для второго случая (симметрично тому, что уже сделано в
  `sweep_orphan_artifact_branches` для алерта), плюс тест на этот
  сценарий на уровне `cmd_doctor`.

- major — `docs/codebase-map.md` не перегенерирована в этой итерации:
  `git diff b3654b84 HEAD` меняет `*.py` в `orchestrator/doctor.py`,
  `tests/sandbox.py`, `tests/test_doctor.py`,
  `tests/test_fsm_branch_correct_status_reads.py`,
  `tests/test_gitcmd_carpentry.py` (conventions-core: «Правишь `*.py`
  ... — регенерируй карту тем же коммитом»). Проверено запуском
  `python3 scripts/codebase_map.py` — диф не пуст СОДЕРЖИМО (не только
  `built_at_sha`): в `tests/sandbox.py` появилась новая публичная
  функция `real_repo_refs`, которой нет в закоммиченной карте (правку
  отменил локально `git checkout -- docs/codebase-map.md` — ревьювер
  код не правит). Класс дефекта уже дважды подтверждён в этом же скиле
  (T079/T087) — здесь третий случай: подтяжка main регенерацию не
  затрагивала, а прямая правка `*.py` шагом developer — затрагивает.
  CI job `codebase-map` (`.github/workflows/ci.yml:92`, `if:
  github.ref == 'refs/heads/main'`) красит именно содержимое (сверка
  без строки `built_at_sha`), т.е. смержить эту ветку в текущем виде —
  значит покрасить main. Предложение: `python3 scripts/
  codebase_map.py` тем же коммитом, что и остальные правки этой
  итерации.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_gitcmd_carpentry.py, tests/test_doctor.py::OrphanArtifactBranchSweepTest | было: 9 тестов без заявки «Ловит мутацию: …» | — | закрыто: все 5 методов `CarpentryTest` и все 5 методов `OrphanArtifactBranchSweepTest` (включая новый `test_failed_deletion_is_not_reported_as_deleted`) несут заявку — `grep -c "Ловит мутацию" tests/test_gitcmd_carpentry.py tests/test_doctor.py` = 10 |
| R1-F2 | fixed | tests/sandbox.py (`TmpRootTest.setUp`/`tearDown`) | реализовано по ANSWER-2 п.2, но эмпирически воспроизведён ложный красный на неотносящемся тесте при прогоне полного `tests/` в этом рабочем дереве (см. «Замечания») | ложноположительные провалы всего пакета `tests/` из-за чужой параллельной активности в общем `config.ROOT`, не только у этой задачи | по ANSWER-3: рантайм-рубеж снят из общего базового класса — `real_repo_refs`/`_REAL_ROOT` и сверка снимков убраны из `tests/sandbox.py` целиком; `RealGitSandbox.setUp` и `tests/test_fsm_branch_correct_status_reads.py::RealGitBranchTest.setUp` больше не заводят `_real_refs_before`. Рубеж требования 1 остаётся на приёмочных тестах этой задачи (`test_ac1_full_suite_ref_isolation.py` — «Инвариант-тест из AC-1» по формулировке самого SPEC AC-2; `test_ac2_previous_verdict_sha_test_migration.py` — узкий вариант для `PreviousVerdictShaTest`) и на CI-стороже вокруг всего прогона `tests/` — не на каждом из 1425+ тестов пакета |
| R1-F3 | fixed | orchestrator/doctor.py (`cmd_doctor`, `_orphan_artifact_branches`) | возврат `git branch -D` в `sweep_orphan_artifact_branches` теперь проверяется и алерт честен, но `cmd_doctor`'s CLI-вывод по-прежнему говорит «не найдено» в сценарии «найдены, все удаления провалились» | Оператор при ручном `doctor --fix` видит противоречащий журналу алертов вывод | новая `doctor._orphan_artifact_branches(conn)` (детект без удаления, не меняет залоченную приёмочным тестом сигнатуру `sweep_orphan_artifact_branches(conn) -> list[str]`) — `cmd_doctor` зовёт её ДО `sweep_orphan_artifact_branches` и печатает отдельную честную строку «найдены, но не удалены — см. журнал алертов» в этом сценарии, не «не найдено»; новый тест `tests/test_doctor.py::OrphanArtifactBranchSweepTest::test_cmd_doctor_fix_reports_found_but_not_removed_honestly` на уровне `cmd_doctor` (не только `sweep_orphan_artifact_branches`) |
| R1-F4 | accepted | orchestrator/doctor.py | не было пустой строки перед следующим разделом | — | закрыто — `return deleted` теперь отделена пустой строкой от `# --- уборка игнорируемых файлов ...` |
| R1-F5 | accepted | tasks/01M1KVGD18P9H5WR7VM8TGPV1T/acceptance_tests/_util.py:64-80 (`cleanup_new_refs`) | не восстанавливались сдвинутые ссылки | — | закрыто по ANSWER-2 п.1 (ADR-0012): добавлен блок, откатывающий `shifted`-ссылки на `before[refname]`; утверждения существующих тестов не менялись (сверено — правка только в `_util.py`) |
| R1-F6 | accepted | tasks/01M1KVGD18P9H5WR7VM8TGPV1T/PLAN.md, шаг 4 | PLAN заявлял правку artel.py, которой нет в диффе | — | закрыто — формулировка шага 4 поправлена, `git diff main HEAD -- orchestrator/artel.py` пуст, подтверждено повторно |
| R3-F1 | fixed | docs/codebase-map.md | карта не перегенерирована после правки `*.py` этой итерации (новая функция `real_repo_refs` в `tests/sandbox.py` отсутствует в закоммиченной карте) | CI job `codebase-map` покрасит main при мерже этой ветки в текущем виде | `python3 scripts/codebase_map.py` прогнан после всех правок `*.py` этой итерации (в т.ч. после удаления `real_repo_refs` по R1-F2) и закоммичен тем же коммитом; диф с предыдущей закоммиченной картой — только `built_at_sha` |

## Вердикт

changes_requested — три пункта требуют доработки: R1-F2 (needs_work,
подтверждённый эмпирически риск ложных провалов всего `tests/` из-за
расширения рантайм-рубежа на весь пакет, не только на acceptance-тесты
этой задачи), R1-F3 (needs_work, закрыта только половина исходного
замечания — incident-алерт честен, CLI `doctor --fix` по-прежнему
может соврать «не найдено»), R3-F1 (open, карта кодовой базы не
перегенерирована — покрасит `codebase-map` на main). Четыре пункта
итерации 1 (R1-F1, R1-F4, R1-F5, R1-F6) закрыты по существу —
проверено чтением и прогоном. Требования 2/3/5 SPEC — без изменений и
без замечаний, OK.

## Проверено исполнением

- `python3 -c "hashlib.sha256(...)"` для `SPEC.md`/`PLAN.md` — оба
  sha256 совпадают с указанными в ревью-пакете.
- `git diff b3654b84 HEAD --stat` — 8 изменённых файлов (`b3654b84` —
  коммит вердикта итерации 2); построчно прочитан diff каждого файла
  из этого списка (`git diff b3654b84 HEAD -- <файл>`).
- `python3 -m unittest tests.test_gitcmd_carpentry tests.test_doctor
  tests.test_review_package tests.test_fsm_branch_correct_status_reads
  -v` — 192 теста, все `ok`.
- `git -C <чистый worktree на main> apply --check` для всех трёх
  unified-диффов PLAN.md по отдельности — все три без вывода (успех).
- `python3 -m unittest discover -s tests -v` (полный пакет, снимок
  `git for-each-ref` до/после прогона в этом рабочем дереве совпал —
  сам прогон настоящих ссылок не менял) — 1425 тестов, 227.7с,
  `FAILED (failures=1)`: `test_step_refixation.
  OwnStepCommitRefixesWithoutIncidentTest.
  test_ordinary_refusal_reason_is_kept` упал в `tearDown` из-за
  стороннего коммита в чужую ветку задачи (см. «Замечания», R1-F2).
  Повторный изолированный прогон того же теста в одиночку — `ok`
  (1.7с), подтверждает: причина внешняя, не регрессия кода этой
  задачи, но сам рубеж реализации R1-F2 — источник ложного красного.
- `python3 scripts/codebase_map.py` в рабочем дереве — диф с
  закоммиченной картой содержателен (не только `built_at_sha`):
  `tests/sandbox.py`'s `real_repo_refs` отсутствует в закоммиченной
  версии; откачено `git checkout -- docs/codebase-map.md` немедленно
  после проверки (R3-F1).
- `git diff main HEAD -- orchestrator/artel.py` — пусто, подтверждает
  закрытие R1-F6.
- `grep -c "Ловит мутацию" tests/test_gitcmd_carpentry.py
  tests/test_doctor.py` — 10, подтверждает закрытие R1-F1 (5+5 методов).
- Read `orchestrator/doctor.py:1029-1164` целиком — подтверждает
  частичное закрытие R1-F3 (возврат `git branch -D` проверяется,
  incident-алерт честен, но `cmd_doctor` CLI-печать — нет) и
  закрытие R1-F4 (пустая строка на месте).
- Read `tasks/01M1KVGD18P9H5WR7VM8TGPV1T/acceptance_tests/_util.py`
  целиком — подтверждает закрытие R1-F5.
- Поиск по AST (`ast.walk` по всем классам-наследникам `TmpRootTest` в
  `tests/`) — ровно два класса переопределяют `setUp` без
  `super().setUp()` (`RealGitSandbox`, `RealGitBranchTest`), оба
  заводят собственный `_real_refs_before` первой строкой — заявление
  PLAN «Подход» о репозиторном grep’е подтверждено независимо.

## Предложения системе

- Рубеж «сравнить снимок ссылок настоящего репозитория до/после» на
  уровне общего базового тестового класса (не отдельного
  специализированного acceptance-теста) — предсказуемо ловушка для
  ЛЮБОГО инвариант-теста такой формы, применённого к общему
  `config.ROOT`, разделяемому параллельными сессиями: расширяет старое
  наблюдение той же PLAN «Предложения системе» этой задачи («Надёжен
  только в изолированном чекауте») с «одного acceptance-теста» на
  «весь пакет `tests/`, если общий базовый класс несёт такую проверку
  по умолчанию» — стоит явно предупредить об этом в `test-authoring`
  ДО того, как подобный рубеж предложат вносить в общий `sandbox.py`
  снова.
