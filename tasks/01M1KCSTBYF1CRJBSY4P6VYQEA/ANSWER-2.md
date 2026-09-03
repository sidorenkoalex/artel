---
task: 01M1KCSTBYF1CRJBSY4P6VYQEA
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

Эскалация ревьювера (итерация 1) и developer (PLAN, «Эскалация») —
залоченная фикстура планки после подтяжки A7: решение — правка
фикстуры по ADR-0012, канал ANSWER, правку делает developer.

Лок приёмочных тестов снимается Оператором на:
- `tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/acceptance_tests/_sandbox.py` —
  добавить подмены `gitcmd.show`/`gitcmd.ls_tree_files` по образцу
  `tests/test_auto_cycle.py::AutoCycleTest` (`disk_backed_show`/
  `disk_backed_ls_tree_files`), чтобы чтение артефактов после A7 шло
  с диска песочницы; ничего сверх этого;
- `tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/acceptance_tests/
  test_ac18_ac19_attention_alert_closes_on_next_transition.py` — только
  докстринги двух тестов AC-19 (approve/reject) с заявкой «Ловит
  мутацию: …» (R1-F3); утверждения тестов не меняются.

Ограничители ADR-0012: содержание и утверждения AC-1..AC-20 не
меняются и не ослабляются; другие файлы `acceptance_tests/` не
трогать; отдельный коммит с ссылкой на этот ANSWER-2; обязательный
прогон до итоговой строки: планка задачи и полный `tests/`, обе
строки «Ran N … OK» — в PLAN, «Влияние на систему». R1-F2
(заявки «Ловит мутацию» в `tests/test_stall_alerts.py`) — закрыть
штатно в той же итерации.

Ревьюверу: REVIEW.md предыдущей итерации отклонён guard'ом по форме
(секции «Соответствие SPEC», «Замечания», «Реестр замечаний»,
«Вердикт» обязаны быть заголовками второго уровня, не вложенными в
«Фаза B»); с этим ответом эскалация снята — вердикт changes_requested
с реестром, developer выполняет правки выше. Обновление лока после
правки — Оператором по прогону планки, как в задачах
01M1K7KP0D8ZKRM9KTE75DCCYR и 01M1HNNHDMP2C1AJTH5QF1BTN2.
