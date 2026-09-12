---
task: 01M2ARQGY51B99YNP9PY806AN1
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Гонка на FETCH_HEAD: приватная ссылка fetch в трёх местах

Источник: копилка docs/backlog.md, строка П1 от 12.09 «Подтяжка main
слила в ветку задачи ЧУЖУЮ артефактную ветку» с дополнением 12.09
11:3xZ (второе место того же приёма). Решение Оператора 12.09: первая
задача волны 3.

Факты:
- Инцидент 12.09 07:15Z: у канарейки 01M2A22CG2 merge-коммит 9a7f06c4
  «подтяжка main» вторым родителем несёт f06ebf61 — голову артефактной
  ветки artifact/01m29a0f88… (автокоммит REVIEW.md другой задачи,
  07:14:38Z). В дереве ветки появился tasks/01M29A0F88…/, следующая
  подтяжка упёрлась в конфликт canary.py. Ущерб: шаг разработчика
  впустую, восстановление ветки (reset + cherry-pick + честная
  подтяжка), принудительный push Оператором.
- Механизм: `git fetch origin <main>` и следом `git rev-parse FETCH_HEAD`
  — два вызова, между которыми параллельный шаг другой задачи в том же
  репозитории (push/fetch артефактной ветки, artifact_source,
  checkpoint) перезаписывает FETCH_HEAD. FETCH_HEAD главной копии
  `config.ROOT` — один файл на все процессы пульта (для worktree он
  приватный, но все три места ниже исполняют fetch именно в
  `config.ROOT` либо в клоне target'а, общем для его задач).
- Три места одного приёма:
  1) `fsm._origin_main_sha` (orchestrator/fsm.py:105–152) — база сверки
     свежести и подтяжки (`pull.evaluate`) на всех трёх точках
     (in_dev -> review, acceptance -> merge_gate, merge_gate -> done);
     `repo=None` — `gitcmd.git` в `config.ROOT`, иначе `gitcmd.in_repo`.
  2) `fsm_merge_gate._origin_main_sha` (orchestrator/fsm_merge_gate.py:
     84–107) — sha main для плотницкого merge в scratch-worktree;
     докстринг объясняет, почему это копия, а не импорт (цикл импорта).
  3) `gitcmd.fetch_head_sha(remote, ref)` (orchestrator/gitcmd.py:
     412–435) — потребители: `workspace.ensure` (orchestrator/
     workspace.py:74, база новой ветки задачи от origin/main, задача
     01M297HF) и `artifact_branch.py:145` (родитель плотницкой записи
     артефактной ветки). Контракт: возвращённый sha ОБЯЗАН реально
     присутствовать в объектной базе (родитель `write_commit`), поэтому
     голый `ls-remote` без fetch этому потребителю не подходит.
- В gitcmd уже есть `remote_branch_sha` через `git ls-remote origin
  refs/heads/<branch>` (gitcmd.py:~397–410) — только sha, без объектов.
- Существующие тесты патчат `fsm._origin_main_sha` по имени
  (`mock.patch.object(fsm, "_origin_main_sha", ...)`, докстринг
  `_pull_main_or_escalate`) — имя и сигнатура должны сохраниться.

Требуется:
1. Один примитив в orchestrator/gitcmd.py, который приносит голову
   удалённой ветки БЕЗ обращения к FETCH_HEAD: `git fetch <remote>
   +refs/heads/<ref>:refs/artel/fetch/<pid>-<uuid>` в приватную ссылку,
   `git rev-parse --verify` этой ссылки, затем `git update-ref -d` её —
   ссылка своя у каждого процесса, гонки на общем файле нет; объекты
   при этом реально попадают в объектную базу (контракт
   `fetch_head_sha` сохраняется). Возврат — (sha, "") либо ("", причина)
   по образцу `fetch_head_sha`; параметр `repo` для клона target'а по
   образцу `in_repo`. Уборка ссылки — и на успехе, и на отказе
   `rev-parse` (`try/finally`); осиротевшие `refs/artel/fetch/*` от
   упавших процессов не мешают следующим вызовам (у каждого своё имя).
2. Все три места переводятся на этот примитив: `fsm._origin_main_sha`
   (имя и сигнатура прежние, включая `repo`), `fsm_merge_gate.
   _origin_main_sha` (имя и сигнатура прежние), `gitcmd.fetch_head_sha`
   (имя и сигнатура прежние — потребители workspace.py и
   artifact_branch.py не правятся). Литерал `FETCH_HEAD` в
   orchestrator/ после задачи остаётся только в докстрингах-пояснениях
   истории, не в вызовах git.
3. Тесты: (а) tests/test_gitcmd_*.py — примитив возвращает голову
   удалённой ветки, объекты присутствуют локально (`git cat-file -e`),
   приватная ссылка после вызова удалена; между fetch и rev-parse
   подменённый FETCH_HEAD (тест пишет в него чужой sha) НЕ влияет на
   результат (мутация «вернуть FETCH_HEAD» — красный); (б) отказ fetch
   (remote недоступен) — ("", причина), ссылки нет; (в) tests/
   test_pull.py и tests/test_fsm_merge_gate_*.py: существующие тесты
   зелёные без ослабления, патч `fsm._origin_main_sha` по имени
   по-прежнему долетает до `pull.evaluate`.

Зоны: orchestrator/gitcmd.py, orchestrator/fsm.py,
orchestrator/fsm_merge_gate.py, tests/.

Приложением: orchestrator/workspace.py (`ensure`, потребитель
`fetch_head_sha`), orchestrator/artifact_branch.py (строка 145),
orchestrator/repo_context.py (`git(ctx, …)`), docs/backlog.md (строка
П1 от 12.09 «Подтяжка main слила…» с дополнением), ветка канарейки
01M2A22CG2 — коммит 9a7f06c4 как образец ущерба (история переписана,
sha сохранён в копилке).

Не входит: гейт подтяжки «второй родитель обязан быть предком
origin/<main>» (кандидат (б) копилки — зона pull.py занята задачей
волны 3 о документных коммитах; отдельная задача после неё); проверка doctor «в истории ветки задачи нет merge-коммитов
с родителем вне origin/main» (кандидат (в) — отдельная задача);
команда принудительного push ветки задачи (строка П2 от 12.09);
правка workspace.py, artifact_branch.py, pull.py, doctor/.

Рамка: $35.
