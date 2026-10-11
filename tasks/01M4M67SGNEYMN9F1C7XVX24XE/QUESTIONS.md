---
task: 01M4M67SGNEYMN9F1C7XVX24XE
type: questions
author_role: analyst
status: ready
schema_version: 2
---

# QUESTIONS: Этап 4 ADR-0021, часть A — мерж артели не кладёт в main снимок задачи и RETRO

## Вопросы

Всё остальное в ТЗ хватает для SPEC: требования 1–4 и критерии приёмки
однозначны. Сверку делал по коду ветки (= origin/main 415f1de4). Два
вопроса ниже ТЗ не снимает. Первый — про ослабление тестов: по
`skills/spec-authoring.md` такое ослабление нельзя оформить разделом
«Меняемое поведение», нужен мандат Оператора. Второй — про расхождение
ТЗ с ADR-0021.

1. **Тесты, у которых требования 1–2 убирают предмет: удалить по
   мандату, оставить мёртвый код или переписать?** Требования 1–2
   убирают коммит RETRO и killed-RETRO долгов в дерево мержа. После
   этого у `fsm_postmerge._generate_and_commit_retro` не остаётся
   вызывающих (единственный вызов — `orchestrator/fsm_merge_gate.py:1082`).
   Требование 1 убирает и `_overlay_artifact_snapshot`
   (`fsm_merge_gate.py:356`, вызов `:1076`). Ниже — методы, которые
   проверяют именно этот механизм. Поменять им ожидание «было → стало»
   нельзя: проверять становится нечего, остаётся только удаление метода
   или утверждения. Рубеж неослабления
   (`advance_gates/test_integrity.py::_test_integrity_gate`) пропустит
   такое удаление только по строке «Ослабление тестов разрешено: …» в
   ANSWER, раздел SPEC «Меняемое поведение» его не покрывает:
   - `tests/test_fsm_retro.py::GenerateAndCommitRetroTest` — все 10
     методов. Это юнит-тесты коммита done-RETRO и подбора killed-долгов
     в репозиторий мержа: `test_happy_path_writes_and_commits_done_retro`,
     `test_killed_debt_is_picked_up_and_committed_separately`,
     `test_no_killed_debts_means_only_done_commit` и остальные;
   - `tests/test_main_ci_line.py::GuardAllLaunchTest::test_task_retro_does_not_hide_snapshot_violation`.
     Он проверяет, что RETRO задачи в дереве мержа не скрывает от
     `guard --all` нарушение снимка. Не будет ни RETRO, ни снимка — не
     будет и этого класса дефекта. Кроме того, тест подменяет по имени
     `_overlay_artifact_snapshot` (`:321`), и `mock.patch.object`
     упадёт, как только функцию удалят;
   - `tests/test_plan_appendix.py::MergeAppendixTest::test_appendix_commit_precedes_the_artifact_snapshot`:
     утверждения `assertTrue(snapshot, …)` и
     `assertLess(applied[0], snapshot[0], …)` (`:792–793`). Утверждение
     «нет коммита снимка» по требованию 1 ложится в «Меняемое
     поведение» (`assertTrue(snapshot)` → `assertEqual(snapshot, [])`).
     А вот у `assertLess` второй точки отсчёта больше нет, его можно
     только удалить.
   Варианты:
   A) мандат строкой ANSWER: «Ослабление тестов разрешено:
      tests/test_fsm_retro.py,
      tests/test_main_ci_line.py::GuardAllLaunchTest::test_task_retro_does_not_hide_snapshot_violation,
      tests/test_plan_appendix.py::MergeAppendixTest::test_appendix_commit_precedes_the_artifact_snapshot».
      Мёртвый код и его тесты уходят вместе. Остальные смены ожидания
      (`tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py::…::test_ac5_code_map_and_retro_are_committed_in_the_clone_merge_copy`
      `assertIn("docs/retro/<id>.md")` → `assertNotIn`, адрес по
      умолчанию в
      `tests/test_retro_artifact_branch_reads.py::…::test_done_address_names_the_snapshot_ref_when_asked`)
      SPEC перечислит в «Меняемом поведении»;
   B) мандата нет. `_generate_and_commit_retro` остаётся в
      `fsm_postmerge.py` без вызывающих, `test_fsm_retro.py` не трогаем.
      Для двух других методов SPEC требует замену, строгость которой не
      ниже прежней: например, «коммит приложений предшествует коммиту
      карты» вместо «…снимку». Цена — мёртвый код в пульте и тест,
      который подменяет удалённую функцию по имени (его тоже придётся
      оставить живым, то есть функцию-пустышку);
   C) другое решение Оператора.
   Дефолт: A. Механизм удаляется по ТЗ, а тест мёртвого кода сторожит
   то, чего пульт больше не делает. Мандат узкий — перечислены
   конкретные методы.

2. **Наложение снимка `tasks/<id>/` для внешнего проекта: оставить или
   тоже отменить?** Сегодня наложение не зависит от проекта:
   `_publish_merge_artifacts` зовёт `_overlay_artifact_snapshot` и
   `_guard_task_root_or_refuse` без проверки `is_artel`
   (`fsm_merge_gate.py:1076–1077`), и
   `artifact_branch.materialize_task_dir` читает
   `refs/artifacts/<id>` клона проекта. Значит, в main внешнего проекта
   сегодня уходит коммит «<id>: снимок артефактной ветки поверх merge».
   «Факты» ТЗ про это молчат и говорят только, что RETRO внешнего
   проекта в main не коммитится. Требование 5 ТЗ («внешний проект:
   поведение мержа не меняется») и требование 1 («мерж задачи артели»)
   при буквальном чтении оставляют наложение у внешнего проекта как
   есть. ADR-0021 п.4 (`docs/adr/0021-project-area-and-immutable-pult.md:119–120`)
   говорит иначе: «наложение снимка `tasks/<id>/` и коммит RETRO на
   `main` отменяются для всех проектов».
   Варианты:
   A) буквально по ТЗ: отмена только для артели. У внешнего проекта
      наложение и `_guard_task_root_or_refuse` по дереву мержа остаются
      как сегодня, его отмена уходит в «Не входит» (отдельная задача);
   B) по ADR: наложение отменяется для всех проектов, а защита
      требования 3 (посторонний файл на дереве ссылки документов)
      действует и для внешнего проекта. Требование 5 тогда читается как
      «прочее в мерже внешнего проекта не меняется»: нет карты, нет
      RETRO, нет `guard --all`;
   C) другое.
   Дефолт: A. ТЗ — источник требований, и требование 5 с критерием
   «Внешний проект: мерж как сегодня» сформулированы явно, а расширять
   объём сверх ТЗ аналитику нельзя.
