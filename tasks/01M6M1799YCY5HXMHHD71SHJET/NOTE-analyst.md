# Записка аналитика 01M6M1799YCY5HXMHHD71SHJET

## Выяснено
- Факты 1-12 ТЗ сверены по HEAD 89698bf92: forge.py:127-212, github_adapter.py:340-430, fsm_merge_gate.py:1581-1908, mr_sync.py:51-53/319-359, targets.py:33/590-592/699-706 — номера совпадают.
- Блокер: удаление 4 ключей `GH_CALLS` (tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py:370-383) = удаление параметров test_ac13 → мандат «Ослабление тестов разрешено», не «Меняемое поведение». Отсюда QUESTIONS.md (вопрос 1, дефолт A — мандат на метод).
- tests/test_mr_delivery_units.py::ExistingLinkTest подменяет targets.target записью БЕЗ `forge` → mr_assignee(policy, проект) с неопределённым хостингом обязан вести себя как без проекта.
- Решения для SPEC (в QUESTIONS, раздел «Решения аналитика»): признак «уже существует» — булево поле MergeRequest, ставит только _GitHub.open_mr; 409 GitLab по регулярке — как было. Бюджет 40, монолит (часть 1 из 2).
- «Не найден» для gh pr view: stderr `Could not resolve to a PullRequest` (код 1) → `(404)`; `Could not resolve to a Repository`, код 4, сеть → без `(404)`.

## Не сработало
- `gh help …` в окружении роли требует подтверждения — справка gh не прочитана, текст признака — по знанию, вопрос 2.

## Где остановился
- QUESTIONS.md сдан (guard ок). После ANSWER-1: написать SPEC по решениям выше, удалить QUESTIONS.md.

## Чего не хватило
- Механики выдачи мандата тестов на spec_gate без эскалации (spec_gate_decision.mandate_refusal сверяет с ANSWER-n) — искал в docs/operator-gates.md гейт SPEC п.6.
