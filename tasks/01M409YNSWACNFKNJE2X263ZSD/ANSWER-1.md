---
task: 01M409YNSWACNFKNJE2X263ZSD
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

---
task: 01M409YNSWACNFKNJE2X263ZSD
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

1. **Читатели документов внешней задачи — вариант (а).** Все читатели
   (бриф, ревью-пакет, гейты `advance`/`approve`, автокоммит шага,
   `amend-tests`, `answer`, ретро и прочие) переводятся на репозиторий
   задачи одним узлом чтения в `artifact_branch`; для артели — git
   главной копии, как сейчас. Вариант (б) не принят: он оставляет внешний
   поток сломанным и удаляет его тесты (принцип целостности). Вариант (в)
   не принят: второй источник истины против ADR-0021 п.1. Существующие
   тесты внешнего потока (группа Б) меняются только подготовкой данных
   (клон проекта со своим `origin` в песочнице), утверждения и имена
   методов не меняются. Если по оценке шага diff подходит к потолку гейта
   ёмкости (262144 байт) — эскалируй до сдачи, не обходи.

2. **Мандат на группу А — по перечню PLAN.** Основание: тесты проверяют
   упразднённый репозиторий фиксации (ADR-0021 п.3, ТЗ требование 1);
   замены — долгоживущие тесты AC-1 и AC-2 задачи. Каждый изменённый
   метод несёт в докстринге строку «Ловит мутацию: …» (гейт заявки
   мутации на выходе in_dev).

Ослабление тестов разрешено: tests/test_git_fixation.py::ArtifactRepoInitTest::test_init_creates_a_git_repo_without_a_remote, tests/test_git_fixation.py::ArtifactRepoInitTest::test_gitignore_excludes_workspace_and_logs, tests/test_git_fixation.py::ArtifactRepoInitTest::test_second_init_does_not_change_state_or_fail, tests/test_git_fixation.py::NoRemoteCheckTest::test_freshly_initialized_repo_has_no_remote, tests/test_git_fixation.py::NoRemoteCheckTest::test_repo_with_a_remote_is_detected, tests/test_git_fixation.py::ExternalTransitionCommitsTest::test_second_transition_without_changes_reuses_the_head, tests/test_doctor.py::RecoveryCheckTest::test_dirty_working_copy_raises_an_incident_alert, tests/test_doctor.py::RecoveryCheckTest::test_healthy_repo_recovery_is_ok, tests/test_doctor.py::RecoveryCheckTest::test_artel_gets_the_same_recovery_sverka_as_any_target, tests/test_doctor_artifact_branch_sync.py::SyncExcludesTerminalAndForeignTargetTest::test_excludes_done_and_external_target

3. **Проверки `doctor` `remote-empty`, `recovery-clean`, `recovery-fsck`
   — вариант (а), снять.** Остаток репозитория фиксации на диске
   (`.artel/projects/<проект>/.git`) Оператор уберёт сам после мержа
   (очередь Оператора `docs/backlog.md`).

4. **Полный прогон.** Полный `tests/` в шаге недоступен (сторож роли) —
   прогони по модулям все затронутые, включая `amend`, `answer`,
   `canary`, `brief`, `review`, и приведи итоговые строки в PLAN.
