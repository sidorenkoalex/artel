# Записка analyst — 01M53B45XW3J56RJHGD70TD8A2 (D2)

## Выяснено
- Исход шага: QUESTIONS.md (4 вопроса), SPEC.md не писался.
- Проверка записи проекта живёт в `orchestrator/targets.py::check` (:139-168) — файл в ТЗ «только чтение», а п.2 ТЗ требует «отказ проверки записи» для project_skills → вопрос 1.
- Все git-вызовы пульта идут через `gitcmd.git`/`gitcmd.carpentry` → `gitcmd.pult_env` (:22-29, :225) — помощник учётных данных для п.1 укладывается в зону `gitcmd.py`; artifact_branch.py, fsm_merge_gate.py, github_adapter.py, snapshot.py зовут push через них.
- Белый список: `providers/claude.py:45` `ALLOWED_TOOLS`, argv `:158-174` (`--permission-mode acceptEdits`, `--allowedTools`).
- Вызовы `python3` из скилов/миссий: команды пульта абсолютным путём (`knowledge_cards.py:954`, `role_prompt.py:240-245,323`, `suite_run.py:232`); `python3 scripts/guard.py` относительно (spec-authoring.md:211, role_prompt.py:59,117,217) — в рабочей копии внешнего проекта файла нет; `python3 scripts/codebase_map.py` (conventions-core.md:42, только артель); `python3 -m pytest` (test-authoring.md:408, coding-standards.md:103,109, role_prompt.py:91) — исполняет код проекта → вопрос 2.
- ADR-0023 п.8 (:512-524): белый список не граница (`git -c alias…`), достаточно «штатной работы» → вопрос 3 о «надёжности».
- Порог свежести п.3.1 ТЗ не назван ни в ТЗ, ни в исследовании (ТЗ-5 :634-635) → вопрос 4.
- Сигналы объёма сработают (10 зон, $45) — в SPEC понадобится нарезка или обоснование монолита.

## Не сработало
- grep с `-o` и пайпами в Bash требует подтверждения — простой `grep -rn` проходит.

## Где остановился
- QUESTIONS.md написан, guard прогнан. Ждём ANSWER-1.md.

## Чего не хватило
- Нет готового перечня всех вызовов `python3` ролями — собирал grep по skills/ и orchestrator/role_prompt.py.
