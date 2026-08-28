---
task: T061
type: plan
author_role: developer
status: ready        # draft | ready | approved
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# PLAN: Единая тестовая песочница — второй заход (FakeProc, claude-only, TmpRootTest)

## Подход

Три независимых по коду, но одновременно закрываемых куска дедупликации
(один MR, SPEC требование 8) — продолжение T037 на файлы, появившиеся
или не докрученные после него.

**1) `class FakeProc`.** 11 файлов (вне `tasks/`) держали идентичный
или строго эквивалентный класс. Контракт везде один: `stdout` — поток
заготовленных строк, `wait(timeout=None)` возвращает `returncode`.
Единственное расхождение — `tests/test_agent_failure.py`, где
`returncode` был обязательным позиционным (без дефолта `= 0`); во всех
вызывающих местах этого файла `FakeProc` уже вызывается двумя
аргументами, поэтому более широкий контракт с дефолтом (как у
остальных 10 файлов) — строгий надмножественный заменитель, поведение
вызывающего кода не меняется. `tests/sandbox.py` получает канонический
`class FakeProc`; 11 файлов переходят на `from tests.sandbox import
FakeProc`.

`FakeProc.__init__` собирает `self.stdout` из вспомогательного потока
(в исходниках — обычно локальный `class FakeStream`). Сам `FakeStream`
SPEC дедуплицировать не просит (только `FakeProc`, требование 1) — но
класс, слепо скопированный в `tests/sandbox.py` как публичный, раздул
бы поверхность дедупа за пределы задачи. Поэтому `sandbox.py` заводит
приватный `_FakeStream` — деталь реализации `FakeProc`, не публичное
имя. В 8 файлах, где локальный `FakeStream` использовался ИСКЛЮЧИТЕЛЬНО
локальным `FakeProc` (`test_acceptance_tests_flow.py` — вложенный,
`test_analyst_role.py`, `test_agent_prompt.py`, `test_git_fixation.py`,
`test_invariants.py`, `test_review_package.py`, `test_multitarget.py`,
`test_multitarget_invariants.py`), удаление `FakeProc` оставляло бы его
мёртвым кодом — убран тем же диффом как прямое следствие требования 1,
не отдельное «улучшение». В 3 файлах, где `FakeStream` используется ещё
и отдельно (`test_agent_failure.py`, `test_agent_log.py` — плюс
подклассы `BlockingStream`/`BrokenPipeStream`, `test_step_cost.py`),
локальный `FakeStream` остаётся как есть — не входит в предмет дедупа.

**2) Пара `claude_only_run`/`claude_only_popen`.** Уже существовали
единственный раз как ИМЕНОВАННЫЕ хелперы в `tests/test_doctor.py`
(SPEC явно называет эти имена как переносимые) — переезжают в
`tests/sandbox.py` без изменения контракта (сигнатуры и поведение
байт-в-байт те же, только источник настоящего `subprocess.run`/`Popen`
— модульные `_REAL_RUN`/`_REAL_POPEN`, захваченные в `sandbox.py` на
момент импорта, до какого-либо мокинга). `test_doctor.py` переходит на
импорt. Отдельно — `test_doctor.LiveSmokeTest.test_cli_not_found_fails`
держит СВОЙ closure (не дубликат: не возвращает готовый процесс, а
бросает `FileNotFoundError` на `claude`), которая ссылалась на теперь
удалённый модульный `REAL_POPEN` — поправлена на локальный
`real_popen = subprocess.Popen`, тем же приёмом, что был в
`test_git_fixation.py` до этой задачи; это не новый дубликат хелпера
(другое поведение), только адрес настоящего `Popen`.

Два инлайн-closure `tests/test_git_fixation.py` (SPEC требование 2,
явно названы) заменяются вызовом `sandbox.claude_only_popen(FakeProc([
"готово\n"]))` — тот же одноразовый `FakeProc` на прогон, что и раньше
(closure создавал новый экземпляр на каждый вызов `claude`; оба
использования в файле — один прогон `cmd_run` на тест, различие не
наблюдаемо).

**3) `sandbox.TmpRootTest` полным набором путей.** Шесть файлов
(SPEC требование 3) патчили частичный, вручную выписанный список
`config`-путей. Часть из них (`test_brief.py`, `test_fsm_map_regen.py`,
`test_fsm_retro.py`, `test_retro.py`) не заводят реальный git и не
резолвят путь временного каталога — для них подмена: наследование
`sandbox.TmpRootTest` + `super().setUp()` + собственная фикстура поверх
(карта/SPEC/схема БД/строка задачи). Другая часть
(`test_fsm_branch_correct_status_reads.py::RealGitBranchTest`,
`test_gitcmd_branch_reads.py::RealGitSandbox`) заводит НАСТОЯЩИЙ git
до патчинга `config.ROOT` и резолвит путь (`Path(tmp.name).resolve()`
— на macOS `/var` симлинк на `/private/var`, а `git rev-parse` и `Path`
сравниваются как строки) — здесь `super().setUp()` вызвать нельзя (он
завёл бы свой временный каталог и пропатчил НЕ резолвленный путь до
git-инициализации). Обе наследуют `sandbox.TmpRootTest` ради
`issubclass`-контракта AC-3 и переиспользуют его метод
`_patched_path(attr)`, но полностью переопределяют `setUp` — тот же
приём, что уже применяли `test_git_fixation._GitFixationTmpRootTest` и
`test_doctor._DoctorTmpRootTest` до этой задачи (см. докстринг
`sandbox.py`: «файлы, которым нужна доп. подготовка, наследуют и
переопределяют setUp»). Цикл патчинга — `for attr in
sandbox.ALL_CONFIG_ATTRS: ... self._patched_path(attr)` вместо
вручную выписанного кортежа `(attr, value)` — тем самым «точечный
mock.patch.object по своему подмножеству путей» (SPEC требование 3)
из файлов уходит, даже там, где `setUp` остаётся своим.

`test_gitcmd_branch_reads.py::TaskBranchTest` патчил только
`config.DB` (не входит в перечень AC-3 из шести КЛАССОВ, но входит в
дух требования 3 — «в файлах»): переведён на `sandbox.TmpRootTest` без
переопределения `setUp` (просто `super().setUp()` + схема БД) — не
нужен ни git, ни резолв пути.

**4) Локальные `fake_git*`.** Только в трёх файлах, названных
требованием 4. `fake_git_clean` (пустой ответ `rc=0, "", ""` на любую
подкоманду) в `test_fsm_map_regen.py` и `test_fsm_retro.py` — строгий
подмножественный случай `sandbox.fake_git` (та же семантика для
`diff`/`checkout`/`add`/`commit`, единственное расхождение —
`sandbox.fake_git` эмулирует git-идентичность и отказ
`rev-parse --verify`, ни то ни другое в этих сценариях не проверяется
и не вызывается — сверено чтением кода `fsm._regenerate_and_commit_map`/
`fsm._generate_and_commit_retro`, ни один не читает identity и не
делает `rev-parse`). Заменены прямой ссылкой на импортированный
`fake_git`.

`test_brief.py` использует ТРИ параметризуемых фейка
(`fake_git_stale`, `fake_git_diff_fails`, `fake_git_checkout_fails`),
которых `sandbox.fake_git` не покрывает (нужен управляемый ответ на
конкретную git-подкоманду с конкретным содержимым/кодом возврата).
Вместо копирования их логики в `tests/sandbox.py` под тремя разными
именами заведён ОДИН общий параметризуемый фейк `sandbox.fake_git_for
(responses: dict[подкоманда -> (rc, stdout, stderr)])` — три локальных
функции `test_brief.py` становятся тонкими обёртками (передают в него
свой словарь ответов), сама механика подмены git-вызова живёт в
`tests/sandbox.py` одним куском. `fake_git_clean` в `test_brief.py`
(4 использования) — то же рассуждение, что и в предыдущем абзаце,
заменён на `sandbox.fake_git`.

## Шаги

1. `tests/sandbox.py`: `FakeProc`/`_FakeStream`,
   `claude_only_run`/`claude_only_popen`, `fake_git_for`. Прогнать
   `tasks/T061/acceptance_tests/test_fakeproc_dedup.py` и
   `test_claude_only_helpers.py`.
2. 11 файлов — `class FakeProc` (и осиротевший `FakeStream`, где он
   больше ничем не используется) на импорт из `tests.sandbox`;
   `tests/test_git_fixation.py` — два инлайн claude-only closure на
   `sandbox.claude_only_popen`; `tests/test_doctor.py` —
   `claude_only_run`/`claude_only_popen`/`REAL_RUN`/`REAL_POPEN` на
   импорт (плюс адресный фикс `test_cli_not_found_fails`, см.
   «Подход»). Прогнать `test_claude_only_helpers.py` заново и весь
   `unittest discover -s tests`.
3. Шесть файлов — наследование `sandbox.TmpRootTest` полным набором
   `ALL_CONFIG_ATTRS` (требование 3); `test_brief.py` дополнительно —
   локальные `fake_git*` на `sandbox.fake_git`/`sandbox.fake_git_for`
   (требование 4), тот же перевод в `test_fsm_map_regen.py`/
   `test_fsm_retro.py`. Прогнать
   `tasks/T061/acceptance_tests/test_tmproottest_adoption.py` и весь
   `unittest discover -s tests`.

Шаги независимы по коду (не пересекаются файлами, кроме `sandbox.py`,
куда шаг 1 пишет, а шаги 2–3 только читают), но один MR — откат
в проде: `git revert` merge-коммита задачи целиком (требование 8).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1, 2 |
| 3 | 3 |
| 4 | 3 |
| 5 | 1, 2, 3 (только импорты/базовый класс/пути патчей — см. «Подход») |
| 6 | 1, 2, 3 (дедуп идентичных/эквивалентных кусков, без попутных улучшений) |
| 7 | 1, 2, 3 (правки только в `tests/`; карта не регенерируется) |
| 8 | этот PLAN, «Таблица переносов» и «Шаги» |
| 9 | см. ниже — фиксация числа тестов |

**Требование 9 (фиксация числа тестов).** До начала переноса, на этой
ветке до первой правки: `python3 -m unittest discover -s tests -v` —
**820 тестов, все зелёные** (совпадает с ориентиром SPEC/ТЗ и с
ориентиром `tasks/T061/acceptance_tests/test_manual_criteria.py`,
зафиксированным на коммите `9fe40ee`, — дрейфа между записью
приёмочных тестов и стартом разработки не случилось). После переноса
(текущее состояние): `python3 -m unittest discover -s tests -v` —
**820 тестов, все зелёные**. Число идентично, состав сценариев и
ассерты не менялись (см. дифф — только импорты, базовый класс
песочницы и пути патчей).

## Таблица переносов

`FakeProc`/`FakeStream` (требование 1):

| Файл | `FakeProc` | Осиротевший `FakeStream` |
|---|---|---|
| `tests/sandbox.py` | заведён (канонический, использует приватный `_FakeStream`) | — |
| `test_agent_failure.py` | импорт | остаётся (используется отдельно, строка ~314) |
| `test_agent_log.py` | импорт | остаётся (база `BlockingStream`/`BrokenPipeStream`, используется отдельно) |
| `test_acceptance_tests_flow.py` | импорт (был вложенным в метод) | удалён (вложенный, больше не нужен) |
| `test_analyst_role.py` | импорт | удалён |
| `test_agent_prompt.py` | импорт | удалён |
| `test_git_fixation.py` | импорт | удалён |
| `test_invariants.py` | импорт | удалён |
| `test_review_package.py` | импорт | удалён |
| `test_multitarget.py` | импорт | удалён |
| `test_multitarget_invariants.py` | импорт | удалён |
| `test_step_cost.py` | импорт | остаётся (используется отдельно, `timeout_then_killed_proc`) |

claude-only side_effect (требование 2):

| Файл | Было | Стало |
|---|---|---|
| `tests/sandbox.py` | — | `claude_only_run`, `claude_only_popen` заведены |
| `test_doctor.py` | собственные `claude_only_run`/`claude_only_popen`/`REAL_RUN`/`REAL_POPEN` | импорт из `sandbox`; `test_cli_not_found_fails` — точечный `real_popen = subprocess.Popen` (не дубликат, другое поведение) |
| `test_git_fixation.py` | 2 инлайн `def side_effect` с `real_popen = subprocess.Popen` | `sandbox.claude_only_popen(FakeProc(["готово\n"]))` |

`TmpRootTest` полным набором путей (требование 3) — файл → класс →
что было (частичный набор) → что стало:

| Файл | Класс | Было | Стало |
|---|---|---|---|
| `test_brief.py` | `BriefUnitTest` | `unittest.TestCase`, ручной патч ROOT/DB/TASKS | `sandbox.TmpRootTest`, `super().setUp()` |
| `test_fsm_map_regen.py` | `RegenerateAndCommitMapTest` | `unittest.TestCase`, ручной патч ROOT/DB/TASKS | `sandbox.TmpRootTest`, `super().setUp()` |
| `test_fsm_retro.py` | `GenerateAndCommitRetroTest` | `unittest.TestCase`, ручной патч ROOT/DB/TASKS | `sandbox.TmpRootTest`, `super().setUp()` |
| `test_retro.py` | `RetroGenerationTest` | `unittest.TestCase`, ручной патч ROOT/DB/TASKS через свой `_patch` | `sandbox.TmpRootTest`, `super().setUp()` |
| `test_fsm_branch_correct_status_reads.py` | `RealGitBranchTest` | `unittest.TestCase`, ручной патч 5/10 путей (ROOT,DB,TASKS,LOGS,WORKTREES) | `sandbox.TmpRootTest`, свой `setUp` (реальный git до патча), цикл по `ALL_CONFIG_ATTRS` + `self._patched_path` |
| `test_gitcmd_branch_reads.py` | `RealGitSandbox` | `unittest.TestCase`, ручной патч только ROOT | `sandbox.TmpRootTest`, свой `setUp` (реальный git до патча), цикл по `ALL_CONFIG_ATTRS` + `self._patched_path` |
| `test_gitcmd_branch_reads.py` | `TaskBranchTest` (вне перечня AC-3, но в духе требования 3 — «в файле») | `unittest.TestCase`, ручной патч только DB | `sandbox.TmpRootTest`, `super().setUp()` |

Локальные `fake_git*` (требование 4):

| Файл | Было | Стало |
|---|---|---|
| `test_fsm_map_regen.py` | `fake_git_clean` (локальная, 4 использования) | `sandbox.fake_git` |
| `test_fsm_retro.py` | `fake_git_clean` (локальная, 2 использования) | `sandbox.fake_git` |
| `test_brief.py` | `fake_git_clean` (4 исп.), `fake_git_stale`/`fake_git_diff_fails`/`fake_git_checkout_fails` (своя логика подмены `diff`/`checkout`) | `fake_git_clean` → `sandbox.fake_git`; три остальных — тонкие обёртки над новым `sandbox.fake_git_for(responses)` |

Побочная правка (не дедуп, необходимое следствие требования 1):
`test_fsm_map_regen.py` — импорт `orchestrator.config` стал неиспользуемым
после перевода `RegenerateAndCommitMapTest` на `super().setUp()` (ручной
цикл `mock.patch.object(config, ...)`, читавший `config`, — единственное
место использования в файле) — убран из `from orchestrator import ...`.

## Влияние на систему

Изменения — только в `tests/` (требование 7): `orchestrator/`,
`scripts/` не тронуты, карта кодовой базы не регенерировалась (не
изменяет ни один модуль, который она описывает). Поведение тестов не
менялось (требование 5, ADR-0002, принцип целостности): ни один
существующий сценарий, ассерт или ожидаемое сообщение не переписаны —
дифф ограничен импортами, базовым классом песочницы и путями патчей;
единственные не-текстовые с точностью до байта места — переход
`FakeProc.returncode` с обязательного параметра на параметр с
дефолтом в `test_agent_failure.py` (строго более широкий контракт,
все вызовы двухаргументные) и создание нового `FakeProc` per-call в
двух местах `test_git_fixation.py` (наблюдаемо идентично прежнему
closure — один вызов `claude` на прогон в обоих тестах). НЕОСЛАБЛЯЕМЫЕ
тесты (`test_invariants.py`, `test_multitarget_invariants.py`,
`test_git_fixation.py`, часть `test_gitcmd_branch_reads.py`) —
изменения тут ограничены тем же периметром (импорт `FakeProc`, база
`TmpRootTest`), сами кодируемые инварианты и их ассерты не тронуты.
Полный прогон `unittest discover -s tests` — 820 тестов и до, и после
(требование 9, AC-4), состав и результат идентичны.

Откат в проде: `git revert` merge-коммита задачи целиком — все правки
одного MR, промежуточных состояний нет.

## Риски

- `test_brief.py::fake_git_diff_fails` стал модульной константой
  (`fake_git_for({...})`, вычисленной один раз при импорте), а не
  функцией — поведенчески эквивалентно (сам возвращаемый объект —
  чистая функция без состояния), но сигнатура `def` → `=` в дифф-обзоре
  может показаться нетривиальной; отмечено здесь, чтобы ревьюер не
  тратил на это отдельный проход.
- Комментарии кода, объясняющие СЕГОДНЯШНЮЮ причину каждой локальной
  копии (например, «подмена subprocess.Popen глобальна» в удалённых
  closure), ушли вместе с кодом, который они объясняли, — не оставлены
  висеть на несуществующий код (в отличие от прецедента T037, где
  часть таких комментариев осталась намеренным остаточным долгом).

## Предложения системе
