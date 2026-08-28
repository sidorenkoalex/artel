---
task: T063
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 4
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: RETRO — полное первое предложение сути, killed из ТЗ

## Фаза A: проверка плана
PLAN.md не менялся с iteration 3 (`git diff 6c503bb..8931374 --
tasks/T063/PLAN.md` — пусто). Полный разбор из iteration 2/3 остаётся
в силе без изменений: таблица покрытия полна, шаг — одна проверяемая
единица, подход не конфликтует с конвенциями. Замечаний к плану нет.

## Соответствие SPEC

Между sha предыдущего (approved, iteration 3) вердикта `6c503bb...`
и текущим HEAD (`8931374...`) ветка получила merge из main
(коммит «T063: подтяжка main») — в main тем временем влилась T061
(«Единая тестовая песочница»). Это НЕ доработка кода T063: сам
`orchestrator/retro.py` и приёмочные тесты T063 не тронуты (см. ниже),
изменения ограничены (а) подстройкой `tests/test_retro.py` под новый
общий `sandbox.TmpRootTest` (T061) и (б) перегенерацией
`docs/codebase-map.md`. Проверено самостоятельно на этой итерации:

- `git diff 6c503bb..8931374 -- orchestrator/retro.py
  tasks/T063/PLAN.md tasks/T063/SPEC.md tasks/T063/acceptance_tests/`
  — пусто: код требований и приёмочные тесты не менялись.
- `git diff 6c503bb..8931374 -- tests/test_retro.py` — единственное
  изменение: `RetroGenerationTest(unittest.TestCase)` →
  `RetroGenerationTest(sandbox.TmpRootTest)` с `super().setUp()`
  вместо собственного ручного патчинга путей (тот же перенос, что
  T061 сделала во всех шести перечисленных в её SPEC файлах). Сценарии
  и ассерты самих тестов `test_retro.py` не изменились — только
  базовый класс песочницы.
- `git diff main...HEAD --stat -- .github/ gates.yaml roles.yaml
  templates/ skills/ scripts/guard.py` — пусто: защищённые пути не
  затронуты.
- `git diff main...HEAD --name-only` — только ожидаемые файлы
  (`docs/codebase-map.md`, `orchestrator/retro.py`, `tasks/T063/*`,
  `tests/test_retro.py`); `docs/retro/T061.md` в диффе branch vs main
  не значится (пришёл через merge и идентичен main — не часть diff
  этой задачи).
- `git merge-base --is-ancestor main HEAD` — true: ветка содержит весь
  main, подтяжка полная, конфликтов не оставлено.

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/retro.py` не менялся с iteration 3 (diff пуст) — `_first_sentence`/`_first_context_sentence` на месте. |
| 2 | OK | Без изменений с iteration 3 — `_first_sentence` применяется к `tz_text` из журнала `kill` в `build_killed`. |
| 3 | OK | Без изменений с iteration 3 — `_first_context_line`/фолбэк `build_killed` без ТЗ в журнале прежние. |
| 4 | OK | Регенерация карты перепроверена самостоятельно на этой итерации (см. ниже) — свежа. |

Независимая перепроверка на этой итерации (после подтяжки main):

- `python3 -m unittest discover -s tests` — **853 теста, OK** (то же
  число, что iteration 3 — рост с 829 на iteration 2 был вкладом
  других задач в main, здесь дрейфа нет).
- `python3 -m unittest discover -s tasks/T063/acceptance_tests -p
  "test_*.py"` — **4/4 OK** (AC-1, AC-2, AC-3, AC-5 подтверждены).
- Регенерация карты: `python3 scripts/codebase_map.py` даёт diff
  только по строке `built_at_sha` (закоммичено `6c503bb...` — sha
  родителя коммита «подтяжка main», локальный прогон сейчас даёт
  `8931374...` — текущий HEAD) — тот же ожидаемый допуск, что и на
  iteration 3 (комментарий в CI-джобе `.github/workflows/ci.yml:66-81`).
  Содержимое карты вне этой строки не отличается. Рабочее дерево после
  проверки возвращено в чистое состояние (`git checkout --
  docs/codebase-map.md`, подтверждено `git status --short` пустым).
  AC-4/требование 4 подтверждены.

AC-1..AC-5 выполняются.

## Замечания
Тот же нерешённый minor из iteration 2/3, перенесён без изменений
(логика `build_killed` со времён iteration 3 не менялась, повод для
его закрытия не появился):

- **minor** — `tests/test_retro.py:181-193` и
  `tasks/T063/acceptance_tests/test_retro_gist_sentence.py` — прямого
  теста на уровне `build_killed` для класса «точка внутри токена
  (путь/дата) в `tz_text` из журнала `kill`» по-прежнему нет (есть
  только для `_first_sentence` напрямую и для `build_done`). Риск
  низкий — `build_killed` вызывает ту же покрытую `_first_sentence` —
  не блокирует, но стоит закрыть отдельным малым тестом при следующей
  правке `retro.py`.

## Вердикт
approved — с sha предыдущего (approved, iteration 3) вердикта
(`6c503bb...`) до текущего HEAD (`8931374...`) сам код требований
T063 (`orchestrator/retro.py`, `tasks/T063/PLAN.md/SPEC.md/
acceptance_tests/`) не менялся; единственные изменения — подтяжка main
(привнёсшая рефакторинг базового класса `tests/test_retro.py` из T061,
без изменения сценариев/ассертов) и ожидаемая перегенерация
`docs/codebase-map.md`. Независимая перепроверка на этой итерации
(полный набор — 853 теста, OK; все 4 приёмочных теста T063 — OK;
карта свежа с точностью до ожидаемой строки `built_at_sha`; защищённые
пути не тронуты; ветка полностью содержит main) не выявила регрессий.
AC-1..AC-5 выполняются. Один minor (неполное покрытие тестом
token-dot-класса на уровне `build_killed`) остаётся не блокирующим
мерж, как и на предыдущих итерациях.

## Предложения системе
(пусто)
