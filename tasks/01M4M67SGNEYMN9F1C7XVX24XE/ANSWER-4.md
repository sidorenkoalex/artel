---
task: 01M4M67SGNEYMN9F1C7XVX24XE
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-4: ответ Оператора

## Ответы

---
task: 01M4M67SGNEYMN9F1C7XVX24XE
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-4: третий метод test_invariants — та же подмена чтения ссылки, только в подтесте merge_gate

## Ответы

Ослабление тестов разрешено: tests/test_invariants.py::ManualGatesNeedTheOperatorTest::test_operator_approve_passes_each_gate
Основание: решение Оператора 11.10.2026 — продолжение ANSWER-2 п.4; независимая проверка Оператора: утверждения не меняются, ветку «ссылки нет» держит AC-11 долгоживущего файла задачи на настоящем git.

Полный прогон (`suite-run` №3 и №4) красный по одному подтесту, которого
отчёт команды не показал (провал внутри `subTest` печатается как
`SUBFAILED` и в счёт «упало» не попадает — это дефект пульта, записан
Оператором):

`tests/test_invariants.py::ManualGatesNeedTheOperatorTest::test_operator_approve_passes_each_gate`,
подтест `гейт='merge_gate'`: «merge отклонён: … ссылки документов
refs/artifacts/<id> нет в репозитории задачи».

Условия (каждое обязательно):

1. Только приложением PLAN к защищённому файлу — дописать третий метод в
   раздел «Приложение: правка tests/test_invariants.py» тем же образцом,
   что два метода ANSWER-2 п.4: `mock.patch.object(fsm_merge_gate,
   "_task_docs_files", return_value=("d" * 40, [f"tasks/{self.TASK}/SPEC.md"], ""))`.
2. Подмена — только вокруг `self.capture(fsm.cmd_approve, self.TASK)` в
   подтесте `merge_gate`; подтесты `spec_gate` и `acceptance` исполняются
   без подмены.
3. Утверждение `self.assertEqual(self.state(), expected)` и перечень
   гейтов — без изменений; комментарий о причине подмены и строка «Ловит
   мутацию» в docstring — как в двух прежних методах.
4. `git apply --check` приложения на чистом дереве ветки — проходит.

Иных правок существующих тестов этот ответ не разрешает. Других
падений в прогонах №3 и №4 нет (базовые прогоны чистые).
