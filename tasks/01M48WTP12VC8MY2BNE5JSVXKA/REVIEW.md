---
task: 01M48WTP12VC8MY2BNE5JSVXKA
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Вынос повторяющейся подготовки тестов в tests/sandbox.py (ревизия тестов TR-23..25)

## Фаза A: план

- Покрытие требований: таблица PLAN покрывает требования 1–6 и возврат из verifying (шаг 4). Полно.
- Шаги размера MR, не микрооперации. Подход (ленивые шаблоны `functools.cache` в `_SANDBOX_CONFIG_DIR`, копия `copytree` в `setUp`) не вводит `setUpClass`/`setUpModule` и не конфликтует с архитектурой песочницы.
- «Влияние на систему» совпадает с диффом: затронуты только `tests/`. Откат — revert merge-коммита.
- Перечень долгоживущих кандидатов (AC-8) и замеры (AC-9, шесть строк из ANSWER-1 с нагрузкой и оговоркой, `setUp` до/после) на месте.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `tests/sandbox.py` `_clone_stub_template`/`_real_git_template` создаются один раз на процесс в `_SANDBOX_CONFIG_DIR` (`tempfile.mkdtemp`, sandbox.py:421, вне каталогов тестов). Наружу отдаётся только копия, атрибуты экземпляра на шаблон не указывают. Записывающего `setUpClass`/`setUpModule` нет. |
| 2 | OK | `init_bare_origin` передаёт `-b config.MAIN_BRANCH`, через него идут `add_synced_origin`, `OriginRealGitSandbox.add_origin` и `make_project_repo`. Временная мутация (убран `-b`) ловится тестом AC-5. |
| 3 | Частично | Помощники есть. Однако три файла вне долгоживущих сохраняют дословную копию заведения bare-origin (R1-F1). Записи `targets.yaml` без `test_profile` (`test_coldstart`, `test_doctor`, `test_multitarget`, `test_draft_mr_commits`) — не копии записи с профилем, их непереход законен. |
| 4 | OK | Замеры в PLAN по ANSWER-1 и собственные замеры `setUp`. |
| 5 | OK | В диффе `tests/` меняются только импорты и строки подготовки. Утверждения существующих методов не изменены, в помощниках нет `assert*`. Фикстуры `ARTEL_TARGETS_YAML` (`test_git_fixation.py`) и `TARGETS_YAML` (`test_plan_appendix.py`) сверены по полям с прежним текстом и совпадают: `token_slot: artel-token` = `{name}-token`, url и base те же. |
| 6 | OK | Долгоживущий `tests/test_01m48wtp12vc8my2bne5jsvxka_sandbox_copies.py` (AC-1/2/3/5) с заявками. Плюс `test_sandbox.py::SandboxFixtureBuildersTest`. |

## Замечания

- major — `tests/test_pin.py:97-99`, `tests/test_workspace.py:57-58`, `tests/test_multitarget_invariants.py:203-205` — дословные копии заведения bare-origin (`git init -q --bare -b config.MAIN_BRANCH <path>`) остались непереведёнными, хотя ровно такая же форма в `tests/test_fsm_merge_gate_done_snapshot.py:122` переведена на `init_bare_origin`. AC-7/требование 3 («файлы `tests/` вне долгоживущих, где заведение bare-origin было дословной копией, на ветке используют помощники») выполнено не полностью. Последствие: TR-24 закрыт частично, следующая правка способа заведения origin (например, дополнительный флаг) опять разойдётся по копиям — именно этот дефект устраняет задача. Предложение: перевести все три места на `init_bare_origin(path)` / `init_bare_origin(path, self.git)`. `tests/test_invariants.py:1602` по SPEC только для чтения и не трогается. Его можно добавить строкой в PLAN как кандидата для Оператора.
- minor — `tests/test_sandbox.py:113-115`, `tests/test_sandbox.py:129` — докстринги обоих новых методов состоят только из заявки «Ловит мутацию» и не описывают сценарий и наблюдаемое свойство (skills/review-checklist, п. «Тесты»). Последствие: читателю не видно, что первый тест проверяет `.git/config` и шаблона, и его копии через `copytree`. Предложение: добавить первой строкой сценарий, например «Шаблоны и их копии несут локальные gc.auto=0 и maintenance.auto=false».

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_pin.py:97; tests/test_workspace.py:57; tests/test_multitarget_invariants.py:203 | дословные копии заведения bare-origin не переведены на `init_bare_origin` (AC-7 неполон) | TR-24 закрыт частично, копии снова разойдутся | перевести три места на `init_bare_origin` |
| R1-F2 | open | tests/test_sandbox.py:113; tests/test_sandbox.py:129 | докстринг — только заявка мутации, без сценария и свойства | неясно, что проверяет тест | добавить строку сценария и свойства |

## Вердикт

changes_requested: перевести на `init_bare_origin` три оставшиеся копии заведения bare-origin (R1-F1) и дописать сценарий в докстринги двух новых тестов `test_sandbox.py` (R1-F2). Других дефектов не нашёл: шаблоны, изоляция копий, HEAD origin, замеры и перечень кандидатов в порядке.

## Проверено исполнением

- `python3 orchestrator/artel.py plank-run 01M48WTP12VC8MY2BNE5JSVXKA`: 5 passed за 0,63 с, код выхода 0.
- `python3 -m pytest -q -p no:cacheprovider tests/test_sandbox.py tests/test_01m48wtp12vc8my2bne5jsvxka_sandbox_copies.py tests/test_plan_appendix.py tests/test_git_hooks.py tests/test_gitcmd_fetch_ref_sha.py tests/test_fsm_merge_gate_done_snapshot.py tests/test_kill_cleanup.py tests/test_gitcmd_branch_reads.py tests/test_doc_commit.py tests/test_answer_gate.py tests/test_git_fixation.py`: 196 passed, 5 subtests passed за 102 с.
- Временная мутация: в `tests/sandbox.py::init_bare_origin` убран `-b config.MAIN_BRANCH`. `tests/test_01m48wtp12vc8my2bne5jsvxka_sandbox_copies.py` дал 1 failed (`test_ac5_bare_origins_head_tracks_main_branch`), 3 passed. Код возвращён, `git status` чист.
- `python3 scripts/codebase_map.py` + `git diff`: расхождение только в `built_at_sha` — карта свежа. Перегенерированный файл откатил.
- grep по `tests/`: оставшиеся `init --bare` вне долгоживущих — `test_pin.py`, `test_workspace.py`, `test_multitarget_invariants.py` и `test_invariants.py` (только чтение) → R1-F1. `ARTEL_TEST_PROFILE` и шаблоны вне `sandbox.py`/`test_sandbox.py` нигде не используются. `config.MAIN_BRANCH`/`DEFAULT_TARGET` нигде не патчатся, поэтому значения по умолчанию в `artel_target_entry` и закешированный шаблон от порядка тестов не зависят.

## Предложения системе

- Ревью-пакет: AC вида «все дословные копии переведены» проверяется только grep'ом по всему `tests/`, а пакет несёт лишь дифф. Стоит, чтобы планка такого AC сама искала оставшиеся копии, а не только проверяла наличие помощника.
