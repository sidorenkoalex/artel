---
task: 01M409YKM3QE5KVRGV0G94F5ZC
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: ADR-0021, этап 1 (б1) — документы вне рабочей копии кода и доступ ролей

Родительская задача: 01M4097E8JTNF61N4YAHQKA0AP — ADR-0021, этап 1 (б): документы вне рабочей копии кода, доступ ролей, упразднение репозитория фиксации
Зоны: orchestrator/, tests/, docs/codebase-map.md, docs/stack.md
Порядок: первая, без зависимостей
Рамка: $45

Источник: ADR-0021 (принят 29.09.2026), пункты 2, 7, 12, 13, этап 1;
SPEC и ANSWER-1 задачи 01M4097E8JTNF61N4YAHQKA0AP (деление части (б),
03.10.2026).

Факты (пин 7b23d1f0):
- Часть (а) (01M3Z2DMQRD0BD7AARFVTCVVG8) перевела документы задачи на одну
  ссылку `refs/artifacts/<id>` (`orchestrator/artifact_branch.py`).
- Документы выкладываются ВНУТРЬ рабочей копии кода:
  `runner.role_cwd` → `artifact_branch.materialize_task_dir` пишет весь
  `tasks/<id>/` в `.artel/worktrees/<id>`;
  `acceptance.materialize_from_branch()` пишет `acceptance_tests/` в
  рабочую копию кода из `fsm_advance`, `advance_gates/acceptance`,
  `advance_gates/tests_writing`, `amend`, `pull`.
- Шаг роли: claude — `orchestrator/providers/claude.py`, codex —
  `orchestrator/providers/codex.py` (сейчас `exec --json --sandbox
  workspace-write --ephemeral --ignore-rules`); флага `--add-dir` в коде
  нет.
- Поддержка проверена: claude 2.1.283 — `claude --help` содержит
  `--add-dir <directories...>`; codex-cli 0.157.1 — `codex exec --help`
  содержит `--add-dir <DIR>  Additional directories that should be
  writable alongside the primary workspace` (проверка Оператора 03.10).
  Закреплённый минимум codex `min_cli_version: 0.155.1` (`models.yaml`)
  не проверен.
- Уроки части (а): шаг developer на крупной правке дважды упёрся в потолок
  45 минут; тесты, запускающие CLI пульта отдельным процессом, краснеют в
  шаге роли из-за унаследованного `ARTEL_ROLE` — свою красноту проверять с
  `env -u ARTEL_ROLE`.

Требуется:
1. Каталог документов задачи — `.artel/projects/<проект>/tasks/<id>/` для
   любого проекта, включая артель до этапа 2. Пульт выкладывает туда
   документы из `refs/artifacts/<id>` перед шагом роли и забирает правки
   роли оттуда автокоммитом шага.
2. Каталог роли — рабочая копия кода задачи; каталог документов открыт
   роли на запись дополнительно: claude — `--add-dir <каталог
   документов>`; codex — `codex exec --add-dir <каталог документов>`,
   глобальные флаги остаются до подкоманды. Developer в PLAN сверяет флаг
   `codex exec --add-dir` со справкой версии 0.155.1 или с журналом
   изменений вендора; при расхождении — эскалация, не обход.
   `models.yaml` только для чтения.
3. `acceptance_tests/` выкладывается в рабочую копию кода только на время
   прогона и убирается после — при зелёном, красном исходе и сбое прогона;
   прочие документы в рабочей копии кода не лежат никогда.
4. Защита документов и закреплённых тестов от роли — гейты пульта (сверка
   с зафиксированным коммитом ссылки, перечень сумм, отметка автокоммита),
   не права доступа (ADR-0021 п.7); существующие гейты не ослабляются.
5. `docs/stack.md`: таблица паритета безопасности роли и описание
   провайдеров отражают каталог документов на запись у обоих провайдеров.
6. Инвариант 21 (часть: каталог роли плюс каталог документов задачи на
   запись) — приложением к PLAN, проверено `git apply --check`.
7. Тесты (`tests/`, постоянные сторожа с заявками «Ловит мутацию»):
   документы не лежат в рабочей копии кода вне прогона; `acceptance_tests/`
   убирается после прогона при любом исходе; команда шага каждого
   провайдера открывает каталог документов на запись; правка роли в
   каталоге документов попадает в ссылку. Существующие тесты не
   ослабляются; меняются только в объёме, прямо требуемом ADR-0021, — с
   перечнем в PLAN (гейт неослабления тестов пропускает их только с
   мандатом Оператора в ANSWER-n.md).

Приложением: docs/invariants.md, tests/test_invariants.py, skills/ (только
абзацы о расположении документов задачи на диске, если они есть).

Только чтение (не менять): docs/adr/, docs/roadmap.md, docs/backlog.md,
docs/operator-session.md, templates/, targets.yaml, models.yaml,
roles.yaml, CLAUDE.md, .github/workflows/ci.yml, scripts/guard.py,
scripts/ci_push_class.py.

Не входит: часть (б2) — упразднение репозитория фиксации
(`fixation._fix_external`, `_read_external`, `projects.init_artifact_repo`),
ссылка документов внешнего проекта в его репозитории и `origin`,
инвариант 25; часть (в) — команда `docs`, пакетный fetch, отмена CI на
`artifact/**`, перевод `--artifact-branch` в `scripts/guard.py` на гейт,
уборка веток `artifact/**`; этапы 2–4 ADR-0021; изоляция файловой системы
ролей (строка бэклога); перенос исторических снимков и живых задач;
подъём `min_cli_version`.