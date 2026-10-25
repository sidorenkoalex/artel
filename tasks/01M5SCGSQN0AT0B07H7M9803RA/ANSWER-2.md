---
task: 01M5SCGSQN0AT0B07H7M9803RA
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

Ослабление тестов разрешено: tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py

Основание: решение Оператора 25.10.2026 (дословно: «Ок по рекомендациям») на эскалацию разработчика — вариант (а). Объём — только `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py::ProjectAreaSandbox.setUp`: одна строка сразу после `targets_patcher.start()` / `self.addCleanup(targets_patcher.stop)` — `(self.root / ".artel" / "targets.yaml").unlink(missing_ok=True)`, удаление записи артели, посеянной `RealGitSandbox` под адрес локального слоя. Утверждения, методы, их число и сообщения не меняются; правка `tests/sandbox.py`, других тестов и других классов файла, удаление утверждений, `skip`/`xfail` не разрешены (вариант (б) отклонён).

Независимая проверка: сверка диффа файла сессией при Операторе до approve на merge_gate — обязательна.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит | Остаётся ли свойство после изменения | Чем покрыто после | Решение |
|---|---|---|---|---|
| tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py — `ProjectAreaSandbox.setUp`: удаление посеянного `RealGitSandbox` файла `.artel/targets.yaml` после перенаправления `config.TARGETS` на `root/targets.yaml` | песочница области проекта читает декларацию проектов только из `targets.yaml` главной копии (файл в git), посеянная запись артели в ней не участвует | остаётся: декларация по-прежнему из `root/targets.yaml`; удаляется только файл, который тесты и до правки не читали, а с задачей он попадал бы в локальный слой | tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py:171 — те же 28 тестов классов на `ProjectAreaSandbox`/`TaskFlowSandbox`; tests/test_invariants.py — `MainCopyGitUnchangedDuringTaskTest` | изоляция песочницы (решение Оператора 25.10, вариант а) |
