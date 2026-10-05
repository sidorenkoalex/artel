---
task: 01M446WV7S94FTZGJCGMPJ667F
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Клон проекта получает ссылки документов задач; doctor не шумит на свежем клоне

# ТЗ: клон проекта получает ссылки документов задач; doctor не шумит на свежем клоне

Источник: копилка 04.10.2026 (после сдвига пина на этап 2 ADR-0021:
12 ложных предупреждений `artifact-ref-sync`, коммит закрытия
01M42NB9GKXNP74HAYEJ7C7CA8 только в git главной копии). Решение Оператора
04.10 «заводи волну один».

Факты (пин 0a87c8b0, сверка кода 04.10):
- `orchestrator/workspace.py::ensure_clone` (~94-120): `git clone`,
  хуки (`set_clone_hooks`), идентичность (`inherit_identity`); refspec
  для `refs/artifacts/*` не настраивается, fetch ссылок документов нет;
  существующий клон не дополняется.
- Ссылки документов приносят в клон только явные `docs <id>` и
  `docs --fetch-all` (`orchestrator/docs_fetch.py` ~31, ~109-150;
  `orchestrator/artifact_branch.py::fetch_all_from_origin` ~545-570 —
  fetch в приватное пространство и сдвиг `refs/artifacts/<id>` только
  вперёд).
- Проверка `artifact-ref-sync` (`orchestrator/doctor/artifact_branches.py`
  ~122-179) читает локальную ссылку в клоне; для закрытой задачи без
  локальной ссылки выдаёт «голова (нет локально)» (~74), хотя origin
  совпадает с коммитом закрытия.
- `_fix_unsent_closed_refs` (~92-119) берёт sha закрытия из БД
  (`snapshot.closing_sha`) и пушит из клона только если локальная голова
  в клоне равна ему; иначе молча пропускает. В `doctor --fix` он идёт
  раньше `_fix_project_clones` (`orchestrator/doctor/cli.py` ~161, ~173).
- Прецедент 04.10: после `doctor --fix` клон без ссылок — 12 ложных
  предупреждений до ручного `docs --fetch-all` (принесено 355); коммит
  закрытия 854edaaa задачи 01M42NB9 был только в главной копии —
  Оператор дослал его ручным push.

Требуется:
1. Заведение клона пультом (`ensure_clone` из `init`, `doctor --fix`,
   `new`) приносит в клон `refs/artifacts/*` из origin тем же узлом, что
   `docs --fetch-all` (только вперёд, без перезаписи).
2. `artifact-ref-sync` различает «ссылки нет в клоне, но в origin она
   совпадает с коммитом закрытия» и настоящее расхождение: первое — не
   предупреждение (либо предупреждение с подсказкой `docs --fetch-all`
   и отдельной строкой, а не по строке на задачу — решение в SPEC).
3. `_fix_unsent_closed_refs` при отсутствии объекта коммита закрытия в
   клоне ищет его в git главной копии (переходный период этапа 2) и
   досылает в origin только продвижением ссылки (без force); если
   объекта нет нигде — строка предупреждения с id задачи, а не молчание.
   SPEC решает порядок шагов `doctor --fix` (клон заводится до досылки).
4. Тесты в `tests/` с заявками «Ловит мутацию» на пп. 1–3. Существующие
   тесты не ослабляются.

Зоны: orchestrator/, tests/, docs/codebase-map.md.

Только чтение (не менять): docs/adr/, docs/roadmap.md, docs/backlog.md,
docs/operator-session.md, templates/, skills/, CLAUDE.md, models.yaml,
roles.yaml, scripts/guard.py, .github/workflows/ci.yml, conftest.py,
tests/test_invariants.py, docs/invariants.md.

Не входит: уборка старых каталогов `.artel/worktrees/`, `.artel/notes-work`,
`workspace/`; ссылки документов внешних проектов вне их клона.

Рамка: $15.
