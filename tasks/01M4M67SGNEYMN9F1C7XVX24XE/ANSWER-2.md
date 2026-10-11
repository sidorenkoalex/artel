---
task: 01M4M67SGNEYMN9F1C7XVX24XE
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

---
task: 01M4M67SGNEYMN9F1C7XVX24XE
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: смены ожиданий существующих тестов — с условиями; drop_task_dir на прежнем признаке

## Ответы

Ослабление тестов разрешено: tests/test_retro.py::RetroGenerationTest::test_build_done_has_merge_sha_address_and_first_context_line_only, tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py::MergeGuardAfterSnapshotTest::test_ac1_clean_snapshot_merges_as_before, tests/test_retro_artifact_branch_reads.py::RetroBranchReadTest::test_done_address_names_the_snapshot_ref_when_asked, tests/test_invariants.py::MergeOnlyFromMergeGateTest::test_merge_gate_approve_is_that_path, tests/test_invariants.py::MergeNeedsGreenCiTest::test_green_ci_merges
Основание: решение Оператора 11.10.2026 — смены следуют из требований 1, 7, 9 SPEC; независимая проверка Оператора (матрица неослабления) — допустимы только при условиях ниже, каждое обязательно.

1. `tests/test_retro.py::…::test_build_done_has_merge_sha_address_and_first_context_line_only`:
   адрес → `assertIn(f"Адрес артефактов: refs/artifacts/{self.TASK}", text)`,
   и ОБЯЗАТЕЛЬНО добавить `assertIn("Итог: done, sha " + "deadbeef" * 5, text)` —
   иначе sha мержа на уровне модуля не проверяется. Строки о первой строке
   контекста — без изменений.
2. `tests/test_01m3sf7…_main_ci.py::…::test_ac1_clean_snapshot_merges_as_before`:
   `assertTrue(origin_tree_has(...))` → `assertFalse(...)` и ОБЯЗАТЕЛЬНО
   добавить проверку, что `{dir}/acceptance_tests/test_ac1_fixture.py` есть
   в дереве `refs/artifacts/<id>` на origin после мержа (документы не
   потеряны). Проверки `done` и сдвига origin/main — без изменений.
3. `tests/test_retro_artifact_branch_reads.py::RetroBranchReadTest::test_done_address_names_the_snapshot_ref_when_asked`
   (в эскалации пропущен; после требования 9 явный адрес совпал бы с
   адресом по умолчанию и мутация «параметр address игнорируется»
   перестала бы ловиться): передавать отличимый адрес (например,
   `address="X-адрес"`) и проверять именно его; вызов без `address` —
   проверять на `refs/artifacts/{TASK}`.
4. Два метода `tests/test_invariants.py` — только приложением PLAN к
   защищённому файлу: внутри каждого метода `mock.patch.object(fsm_merge_gate,
   "_task_docs_files", ...)` возвращает непустое чистое дерево документов
   задачи; проверка документов исполняется настоящая, подменяется только
   чтение дерева ссылки; утверждения методов не меняются. `SpyRun` в
   `tests/sandbox.py` не трогать. Отказ при отсутствующей ссылке остаётся
   покрыт AC-11 долгоживущего файла.
5. `cleanup.drop_task_dir` — на прежнем признаке «каталог в дереве main»
   (вариант а): прежний запрос `ls-tree … tasks/<id>` вынести в отдельную
   функцию или оставить в `drop_task_dir`, сохранив «None — каталог
   оставлен»; новый `artifacts_in_main` по ссылке документов поведение
   уборки не меняет. Шесть методов `tests/test_kill_cleanup.py` не трогать.

Перед сдачей — `suite-run`; иных красных существующих тестов быть не
должно, а найденные — эскалацией, не правкой.
