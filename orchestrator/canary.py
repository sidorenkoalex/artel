"""Команда `canary`: синтетический прогон конвейера, v2 (SPEC
01M1NEEWH5K1XPFRDGRMPYSBXJ; v1 — tasks/T065/SPEC.md).

Канарейка — типовые синтетические ТЗ с неподвижным (параметризуемым
сидом) входом, заведённые и проведённые через FSM без участия
Оператора: сдвиг метрик прогона относительно бейзлайна читается как
регрессия самого конвейера, не кодовой базы.

v2 отличия от v1 (дыра v1: RETRO/ветки/алерты убитых канареек текли в
`config.ROOT` пульта):
1. Пул шаблонов ТЗ — вне корня пульта (`~/.artel-canary`, требование 1)
   с случайной выборкой `k` из `N` доступных, не «все файлы каталога».
2. Полный цикл КАЖДОЙ выбранной задачи — в ОТДЕЛЬНОМ эфемерном клоне
   пульта (`_ephemeral_clone`): свой рабочий каталог, своя БД
   состояния, свой origin-заглушка. Ноль следов в главном пульте
   (требование 3) — структурное следствие того, что весь FSM-код читает
   пути ТОЛЬКО через модульные атрибуты `orchestrator/config.py`.
3. Метрики — БД пульта СНАРУЖИ клона, отдельные таблицы `canary_runs`/
   `canary_baseline` (требование 5), не JSON на диске (v1). Бейзлайн —
   per-task, ключом `title` (стабильное имя шаблона МЕЖДУ прогонами,
   требование 9), не суммой по набору.
4. Эскалация — синтетический `ANSWER` Оператора-заглушки, прогон
   продолжается сам (требование 6), а не «canary дальше не ведёт», как
   в v1.
5. Машиночитаемый маркер «ожидается эскалация» в теле шаблона
   (`<!-- canary-expect-escalation: yes|no -->`) сверяется с фактом по
   завершении задачи; расхождение — в отчёте прогона (требование 8).

Целевой sha прогона (SPEC 01M2B6K02YVJBWE1JDWP85EJH0): без `--sha` —
голова `origin/<config.MAIN_BRANCH>` (`gitcmd.fetch_ref_sha`), не HEAD
главной копии (пина); эфемерный клон делает checkout именно этого sha
(`_ephemeral_clone`), а `canary_runs.main_sha` несёт его же — до этой
задачи оба всегда были `gitcmd.head_sha()` пина, из-за чего правка,
ушедшая в `origin/main`, но ещё не в пин, не могла получить зелёный
прогон (инцидент 12.09, SPEC/«Контекст»). `_sha_label` — пометка
происхождения sha в отчёте («код пина»/«код origin/main»/«код <sha>»).

Каждый шаблон пула, использованный боевым прогоном, обязан нести
метку `canary-guid: <значение>` (HTML-комментарием, тем же приёмом, что
и маркер эскалации выше) — требование 7: CI-джоб пульта (`.github/
workflows/ci.yml`, приложение к PLAN.md этой задачи — путь защищённый)
отклоняет коммит/PR, если эта метка обнаружена в `skills/`, `templates/`
или `docs/` пульта. Содержание/создание конкретных шаблонов — вне
объёма этой задачи («Не входит» SPEC); эта метка нужна коду задачи
только КАК ФОРМАТ-ДОКУМЕНТАЦИЯ для Оператора/ассистента, руками
пишущих пул, — сам код `canary.py` её не читает и не проверяет.

Набор ролей прогона (SPEC 01M3FQ2Z2PY0E9T5F5WQ207NP5): `canary --k <N>
[--sha <sha>] [--set <имя>]` — именованный набор «роль -> (провайдер,
модель)» из `canary_sets:` локального слоя пульта, действующий ТОЛЬКО
внутри эфемерного клона. Обе половины приходят в клон одним каналом —
локальным слоем клона (`_clone_local_layer_text`), который уже
переадресован сюда `_CLONE_CONFIG_ATTRS`: модели — ярусами `tiers:`,
провайдер — картой `role_providers:`, которую читает
`orchestrator/roles.py::provider`. `roles.yaml` при этом не меняется ни в
клоне, ни в главной копии: путь защищённый, и прогон канарейки не вправе
переводить роль пульта на другого исполнителя. Бейзлайн и строки прогонов
ключуются ПАРОЙ (шаблон, набор): прогон на другом наборе моделей иначе
сравнивался бы с бейзлайном прежнего набора и переписывал бы его. Без
`--set` действует набор по умолчанию (`config.CANARY_DEFAULT_SET`) —
сегодняшнее поведение байт-в-байт, без единого чтения `canary_sets:`.

Выбор шаблонов прогона и судьба бюджетной эскалации (SPEC
01M3HJQV2QV9BXNXSH3F8STAYH): `canary --k <N> --template <имя>[,<имя>…]`
берёт из пула НАЗВАННЫЕ шаблоны в порядке их перечисления, вместо
случайной выборки (`_named_pool_templates`); имя — стабильное имя файла
шаблона без `.md`, число имён обязано равняться `--k`, и каждый случай
битого флага — именованный отказ ДО эфемерного клона, до origin и до
заведения задачи. Без флага выбор прежний, случайной выборкой. Первая
строка вывода прогона называет выбранные шаблоны в порядке прогона.
Эскалация канареечной задачи ПО БЮДЖЕТУ (её признак — причина перехода,
которую пишет `orchestrator/budget.py::enforce_budget`) отличается от
остальных эскалаций: первую такую прогон закрывает ОДНОКРАТНЫМ подъёмом
потолка этой задачи (`_raise_task_ceiling`, множитель
`config.CANARY_BUDGET_CEILING_FACTOR`) и ведёт задачу дальше; исчерпание
уже поднятого потолка снимает задачу своим исходом («исчерпан потолок
задачи: $X из $Y на шаге <роль>», `_kill_ceiling_exhausted`) со своим
вердиктом `VERDICT_CEILING_EXHAUSTED`. До этой задачи бюджетная эскалация
закрывалась синтетическим ANSWER без изменения потолка, задача крутилась
до снятия «задача не сходится», и прогон 20260927T123258Z дал красный
вердикт там, где шаблон просто не уложился в потолок. Сам факт подъёма
прогон не красит: задача, прошедшая после него штатно до `merge_gate` без
расхождения маркера, остаётся `green`.

`canary pool-seal`/восстановление пула (SPEC 01M1NSR5M5THYRC0RFWPMVE2DW,
часть 2) — отдельная от прогона конвейера механика; вынесена в
`orchestrator/pool_seal.py` (SPEC 01M2CN42RV0EBBP7HS4HP2VNY1) — детали
формата (HMAC, openssl, GUID-манифест) см. там.

`spec_gate`/`acceptance` эта команда проходит САМА, отдельным кодовым
путём (не через `fsm.cmd_approve`): инвариант 18 («`auto` не проходит
гейты», docs/invariants.md) этим не затронут — путь существует только
внутри этого модуля и только для задач, которые сама же команда
`canary` завела (тот же принцип, что и v1). `merge_gate` canary не
approve никогда — задача убивается штатным `cleanup.cmd_kill` (main
этим путём не трогается — kill не мержит; здесь «main» — main клона,
не главного пульта) — единственный штатный kill во всём прогоне.
`verifying` (SPEC T079; ADR-0015 переставил его перед ревьювером) тоже
не дожидается — CI ветки, которого у неё нет и не будет (канареечные
задачи не заводят Draft MR), но, в отличие от `merge_gate`, не убивает
задачу: проходится синтетически (`_pass_verifying`) в `review`, тем же
приёмом, что `spec_gate`/`acceptance` — ANSWER-3.md 06.09, задача
01M1TKP269W9JN3NBJCR5Q6C3B (до ADR-0015 `verifying` шёл ПОСЛЕ ревью и
его kill был штатным финалом; теперь он стоит до первого ревью и
приравнивание к финалу убивало прогон раньше, чем он успевал дойти до
сценариев «не сошлась»/эскалации). Старая `_kill_at_verifying` (v1-эпоха,
SPEC 01M1SC3Y20YBTTJVQDJBF2NDQW) `_drive_task` больше не зовёт никогда —
но сама функция и её классификация «штатно» в `_kill_outcome_note`
остаются: `tasks/01M1SC3Y20YBTTJVQDJBF2NDQW/acceptance_tests/
test_canary_report_kill_reason.py` (залоченная планка ДРУГОЙ, уже
смерженной задачи) зовёт её напрямую и сверяет вывод — правка чужой
планки требует отдельного мандата Оператора (REVIEW.md 01M1TKP269W9JN3
NBJCR5Q6C3B итерации 2, R2-F1), которого эта задача не получала; функция
живёт как чистый совместимый alias, не участвующий в реальном вождении
канарейки.
"""
import io
import os
import random
import shutil
import subprocess
import sys
import tempfile
from collections import namedtuple
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

from scripts import guard

from . import (alerts, answer, artifact_branch, artifact_source, artifacts,
              auto, budget, catalog, cleanup, config, fsm, gitcmd, models,
              roles, runner, store, workspace, yamlmini)
from .pool_seal import _pool_dir
from .providers import codex as codex_provider

CANARY_MARK_ACTOR = "canary"

# Причины `agent run SKIPPED` (`runner.role_cwd`/`runner.role_env`),
# короткое замыкание холостых проходов `_drive_task` на них — SPEC
# 01M1SC3Y20YBTTJVQDJBF2NDQW, требование 3/AC-3: воспроизведение боевого
# прогона 05.09, где причина терялась внутри уже уничтоженного
# эфемерного клона за `CANARY_MAX_STALL_ITERS` холостых проходов.
_SKIP_SHORTCIRCUIT_REASONS = (
    "рабочий каталог роли не создан",
    "каталог окружения роли не создан",
)

# Литерал `action`, которым `_kill_at_merge_gate` журналирует убийство —
# узнаётся `_kill_outcome_note` (требование 4, AC-4) как «штатный» исход,
# не «не сошлась». `verifying` больше не убивает задачу в РЕАЛЬНОМ
# вождении (ADR-0015 сдвинул его перед ревьювером — ANSWER-3.md 06.09):
# канарейка проходит его синтетически (`_pass_verifying`), единственный
# штатный kill живого прогона — `merge_gate`. `_VERIFYING_KILL_ACTION`
# ниже классифицируется так же «штатно» ради чужой залоченной планки
# (`_kill_at_verifying`, REVIEW.md итерации 2, R2-F1) — не потому, что
# `_drive_task` ещё может её достичь.
_MERGE_GATE_KILL_ACTION = "canary: merge_gate не approve — задача убивается"

# Литерал `action`, которым `_kill_at_verifying` (v1-эпоха, ныне
# недостижимая из `_drive_task` — см. `_pass_verifying`) журналировала
# убийство: `_kill_outcome_note` узнаёт его как «штатно» тем же приёмом,
# что и `_MERGE_GATE_KILL_ACTION` — совместимость с
# `tasks/01M1SC3Y20YBTTJVQDJBF2NDQW/acceptance_tests/
# test_canary_report_kill_reason.py::test_ac4_verifying_kill_is_also_
# reported_as_normal` (залоченная планка ДРУГОЙ, уже смерженной задачи —
# правка её планки требует отдельного мандата Оператора, которого эта
# задача не получала).
_VERIFYING_KILL_ACTION = "canary: verifying не дожидается CI — задача убивается"

# Литерал `detail`, которым `_kill_inconclusive` журналирует убийство —
# `_kill_outcome_note` отличает эту запись от остальных записей
# `CANARY_MARK_ACTOR` и берёт её `action` (сама причина) для отчёта.
_INCONCLUSIVE_KILL_DETAIL = "прогон дальше эту задачу не ведёт — cleanup.cmd_kill"

# Литерал `action`, которым `orchestrator/fsm_advance.py::
# _acceptance_run_refuses` отклоняет `in_dev -> verifying` на красной
# приёмочной планке (01M2ARQD7C472KZACB3SZXGF1N, требование 2) — не
# экспортируется `fsm_advance.py` как публичное имя, согласованный
# литерал здесь, тем же приёмом, что уже дублирует `REFUSAL_ACTION_
# PREFIX` между `store.py`/`auto.py`.
_ACCEPTANCE_TESTS_REFUSAL_ACTION = "переход отклонён: приёмочные тесты"

# Литерал `action`, которым `canary._drive_task` журналирует КАЖДЫЙ
# повтор developer на красной планке (требование 5) — читается
# `_dev_retry_count` для строки отчёта; сам повтор — не переход
# состояния, поэтому не подпадает под `_step_count`.
_DEV_RETRY_ACTION = "canary: повтор developer на красной планке"

# Признак эскалации ПО БЮДЖЕТУ (01M3HJQV2QV9BXNXSH3F8STAYH, требование 6):
# устойчивая часть `detail`, которым `orchestrator/budget.py::
# enforce_budget` сопровождает переход в `escalated` («бюджет исчерпан: $X
# из $Y»). `budget.py` не экспортирует эту формулировку публичным именем и
# по разделу «Не входит» SPEC не правится — согласованный литерал здесь,
# тем же приёмом, что уже дублируют `_AUTO_STOPPED_ACTION` и
# `_ACCEPTANCE_TESTS_REFUSAL_ACTION` ниже/выше.
_BUDGET_ESCALATION_DETAIL_MARK = "бюджет исчерпан"

# Литерал `action`, которым `_raise_task_ceiling` журналирует ОДНОКРАТНЫЙ
# подъём потолка канареечной задачи (требования 7, 11). Он же — ПАМЯТЬ о
# том, что подъём уже был (`_ceiling_already_raised`): признак живёт в
# журнале задачи, а не в переменной цикла `_drive_task`, потому что
# переменная обнулялась бы на уходе из состояния (как `dev_retries`) и
# поднятый потолок перестал бы быть конечной верхней границей расхода
# (требование 8).
_CEILING_RAISE_ACTION = "canary: потолок канареечной задачи поднят однократно"

# Литерал `detail`, которым `_kill_ceiling_exhausted` помечает снятие
# задачи по исчерпанию УЖЕ ПОДНЯТОГО потолка (требование 9) — по нему
# `_kill_outcome_note` отличает этот исход и от штатного, и от «не
# сошлась», а `_ceiling_exhausted` — от любого другого снятия. Сама
# причина с числами и ролью шага живёт в `action` той же записи, тем же
# приёмом, что и `_INCONCLUSIVE_KILL_DETAIL`.
_CEILING_EXHAUSTED_KILL_DETAIL = (
    "прогон дальше эту задачу не ведёт — исчерпан поднятый потолок задачи")

# Устойчивая часть причины исхода (требование 9, AC-6): по этой
# формулировке исход узнаётся и в отчёте прогона, и в справке пульта, и в
# docs/operator-session.md.
_CEILING_EXHAUSTED_REASON = "исчерпан потолок задачи"

#: Третье значение `canary_runs.verdict` (требование 10): прогон, задача
#: которого не уложилась в уже поднятый потолок. Не `green` и не `red` —
#: диагноз «шаблон не уложился в потолок» и диагноз «конвейер не сошёлся»
#: обязаны различаться по строке журнала прогонов. Годным для `pin-update`
#: такой прогон не становится: `store.green_canary_runs` отбирает строго
#: `verdict='green'`, поэтому ни `store.py`, ни `pin.py` этой задачей не
#: правятся и условие ADR-0013 не ослабляется.
VERDICT_CEILING_EXHAUSTED = "ceiling"

# Origin эфемерного клона (требование 2, AC-2) — заглушка ЯВНО, не то,
# что `git clone` подставил бы сам (локальный путь до `config.ROOT`,
# формально не http(s), но реально дотягивающийся до главного пульта):
# `artifact_branch.push()` (best-effort) с таким origin смог бы
# по-настоящему запушить ветку канареечной задачи в главный пульт —
# ровно то, что запрещает требование 3. С задачи 01M297HFSKV3GVZJ9YF20FZEZE
# заглушка — не несуществующая схема (`workspace.ensure` теперь требует
# успешного `git fetch origin` при заведении НОВОЙ ветки задачи, а
# канареечная задача всегда новая), а ОТДЕЛЬНЫЙ одноразовый bare-клон
# рядом с самим эфемерным клоном (см. `_ephemeral_clone`): fetch с него
# проходит (там есть `config.MAIN_BRANCH` на момент старта прогона), а
# push по-прежнему не достигает главного пульта — уходит в тот же
# одноразовый bare-клон, убираемый вместе с эфемерным клоном.

# Машиночитаемый маркер «ожидается эскалация» (требование 8) — HTML-
# комментарий в теле шаблона: `catalog.cmd_new`/`_tz_document` кладёт
# сырой текст шаблона ТЕЛОМ итогового TZ.md — маркер во фронтматтере
# самого шаблона до задачи не доедет, только как текст тела; HTML-
# комментарий читаем механикой и невидим при рендере markdown.
MARK_EXPECT_ESCALATION_YES = "<!-- canary-expect-escalation: yes -->"
MARK_EXPECT_ESCALATION_NO = "<!-- canary-expect-escalation: no -->"


def _pool_md_files(pool_dir: Path) -> list:
    """Шаблоны пула — отсортированные `*.md` каталога, не «все файлы»
    (требование 1 SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ). Пустой пул — отказ
    ЗДЕСЬ, общий для обеих ветвей выбора: без шаблонов прогону нечего
    вести ни по имени, ни случайно."""
    files = sorted(p for p in pool_dir.iterdir()
                   if p.is_file() and p.suffix == ".md")
    if not files:
        sys.exit(f"canary: в пуле {pool_dir} нет файлов *.md")
    return files


def _sample_pool_templates(pool_dir: Path, k: int) -> list:
    """`k` случайных `*.md` шаблонов пула из доступных `N` (требование 1,
    AC-1) — не «все файлы каталога», как v1."""
    files = _pool_md_files(pool_dir)
    if k > len(files):
        sys.exit(f"canary: --k={k} больше числа доступных шаблонов пула "
                 f"({len(files)})")
    return random.sample(files, k)


def _named_pool_templates(pool_dir: Path, k: int, titles: list) -> list:
    """Названные шаблоны пула в ПОРЯДКЕ перечисления во флаге
    `--template` (01M3HJQV2QV9BXNXSH3F8STAYH, требования 1-3).

    Возвращается список по списку имён, не по отсортированному пулу и не
    по множеству: порядок имён во флаге и есть порядок задач прогона —
    иначе воспроизвести конкретный сценарий пула командой было бы
    нельзя, а именно за этим флаг и заведён.

    Каждый из трёх отказов требования 3 — `sys.exit` ЗДЕСЬ, то есть до
    `_resolve_target_sha` (единственное обращение к origin) и до первого
    `_ephemeral_clone`: за опечатку в имени шаблона Оператор не платит ни
    сетью, ни `git clone`, ни заведённой задачей — тот же принцип, что у
    отказов `_set_plan` по соседству. Четвёртый случай («`--template` без
    значения») разбирается ещё раньше, в `artel._template_arg`: до этой
    функции пустой флаг просто не доходит.
    """
    available = [p.stem for p in _pool_md_files(pool_dir)]
    if len(titles) != k:
        sys.exit(f"canary: --template называет {len(titles)} имён, а --k={k} "
                 "— число имён обязано равняться --k (иначе прогон вёл бы "
                 "не то число задач, которое назвал Оператор)")
    repeated = sorted({title for title in titles if titles.count(title) > 1})
    if repeated:
        sys.exit(f"canary: --template повторяет имя шаблона: "
                 f"{', '.join(repeated)} — обе задачи писали бы бейзлайн "
                 "одного шаблона в одном прогоне, и вторая строка "
                 "перезаписывала бы первую")
    unknown = [title for title in titles if title not in available]
    if unknown:
        sys.exit(f"canary: --template называет имя, которого нет в пуле "
                 f"{pool_dir}: {', '.join(unknown)}; доступные шаблоны: "
                 f"{', '.join(available)}")
    return [pool_dir / f"{title}.md" for title in titles]


def _expected_escalation(raw_text: str) -> bool | None:
    """Ожидание маркера шаблона; None — маркера нет вовсе (требование 8
    сверяет только шаблоны, которые его несут)."""
    if MARK_EXPECT_ESCALATION_YES in raw_text:
        return True
    if MARK_EXPECT_ESCALATION_NO in raw_text:
        return False
    return None


# Атрибуты `config.py`, которыми ЛЮБОЙ код пульта (store/catalog/fsm/
# auto/cleanup/artifact_branch/workspace/...) адресует пути пульта —
# каждый определён буквально как `ROOT / <подпуть>`, поэтому пересчёт
# под клон универсален (`dest / saved[attr].relative_to(outer_root)`),
# без повторного перечисления подпутей. Тот же список путей, что и
# `tests/sandbox.py::TmpRootTest.PATCHED_ATTRS`/`_sandbox.CanarySandbox.
# setUp` патчат `unittest.mock`'ом — здесь то же самое вручную:
# исполняемый код, не тест.
#
# `MODELS_LOCAL` (SPEC 01M3009Y9AGGY6ZCFA7H1HJ1TD, требование 7, REVIEW
# итерации 1 R1-F1) — обязателен здесь по двум причинам сразу: без него
# `catalog.cmd_init()` ниже кладёт шаблон локального слоя в ГЛАВНЫЙ
# пульт (след в главной копии — ровно то, что канарейка v2 заводилась
# исключить, требование 3 SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ), а шаги ролей
# клона разрешают модель по ЖИВОМУ слою Оператора снаружи клона — правка
# слоя во время прогона меняла бы модель синтетических шагов, и метрика
# прогона переставала бы быть функцией клона.
#
# Инвариант списка («каждый путь `config` под `ROOT/.artel` либо здесь,
# либо в `_CLONE_EXEMPT_CONFIG_ATTRS` с причиной») держит
# `tests/test_canary.py::CloneConfigAttrsInvariantTest`: до него оба
# списка перечисляли сами себя, и новый путь ловился только ревью.
_CLONE_CONFIG_ATTRS = (
    "ROOT", "DB", "TASKS", "LOGS", "PROJECTS", "TARGETS",
    "ROLE_HOME", "ROLE_CONFIG_DIR", "BACKUP_MARKER", "WORKTREES",
    "MODELS_LOCAL",
)

#: Пути `config` под `ROOT/.artel`, которые клон сознательно НЕ
#: переадресует — с причиной у каждого. Список существует ради
#: инварианта выше: «забыли» и «решили не переадресовывать» обязаны
#: различаться машинно, а не по памяти ревьювера.
_CLONE_EXEMPT_CONFIG_ATTRS = {
    # Venv пульта: клон исполняется ТЕМ ЖЕ интерпретатором, что и главная
    # копия, и собственного venv не заводит — переадресация увела бы
    # `stack.check_stack()` клона на заведомо отсутствующий каталог.
    "VENV_DIR": "клон исполняется интерпретатором главной копии",
}


#: Указатель связки ключей внутри дома роли — ОТНОСИТЕЛЬНЫМ путём (SPEC
#: 01M3HST1381E1FZCYAN2TSB1F3, требование 1). Абсолютный адрес считается в
#: момент обращения (`config.ROLE_HOME / _KEYCHAIN_POINTER_REL`): снаружи
#: блока клона то же выражение даёт указатель ПУЛЬТА, внутри — указатель
#: КЛОНА, потому что `ROLE_HOME` там уже переадресован
#: (`_CLONE_CONFIG_ATTRS`). Абсолютной константой в `config.py` это заводить
#: незачем: её значение всё равно пересчитывалось бы от `ROLE_HOME`, а
#: инвариант `tests/test_canary.py::CloneConfigAttrsInvariantTest` требовал
#: бы записи в один из двух списков переадресации — учёта пути, у которого
#: своего адреса нет.
#:
#: Сам файл — настройки, не секрет: в нём лежит ПУТЬ к связке ключей, по
#: которому `codex` её ищет (`$HOME/Library/Preferences`, см.
#: `CodexProvider.environment`), а токены остаются в самой связке, которую
#: пульт не читает и не пишет.
_KEYCHAIN_POINTER_REL = Path("Library/Preferences/com.apple.security.plist")

#: Вход Codex, который прогон переносит в эфемерный клон (SPEC
#: 01M3HST1381E1FZCYAN2TSB1F3, требования 1/4): `role` — роль, которой
#: зовётся проверка входа домом клона (первая по алфавиту из идущих
#: провайдером Codex — `CodexProvider.environment` роль не читает, и
#: аргумент нужен только для воспроизводимости строки отказа), `pointer` —
#: БАЙТЫ указателя связки ключей дома роли пульта, прочитанные ДО клона.
#:
#: Байты, а не путь: читаемость указателя обязана выясниться до клона
#: (требование 3), то есть прочитать его снаружи всё равно нужно — и второе
#: чтение внутри клона могло бы отказать там, где отказывать уже нельзя.
CodexCloneAuth = namedtuple("CodexCloneAuth", "role pointer")

#: План прогона по набору ролей (SPEC 01M3FQ2Z2PY0E9T5F5WQ207NP5):
#: `name` — имя набора (им ключуются бейзлайн и строка прогона),
#: `entries` — записи набора «роль -> `models.CanarySetRole`»,
#: `layer_text` — готовый текст локального слоя эфемерного клона (`None` —
#: слой клона остаётся шаблоном, ветка набора по умолчанию),
#: `summary` — сводка «роль -> модель» прогона для строки журнала и вывода,
#: `codex_roles` — роли прогона, идущие провайдером Codex (SPEC
#: 01M3HST1381E1FZCYAN2TSB1F3, требование 2), отсортированные по алфавиту;
#: пустой кортеж — переноса указателя и проверки входа не будет вовсе.
CanarySetPlan = namedtuple("CanarySetPlan",
                           "name entries layer_text summary codex_roles")

#: План набора ПО УМОЛЧАНИЮ: локального слоя пульта не читает вовсе и в
#: `canary_sets:` не заглядывает (требование 3, AC-14) — прогон без `--set`
#: обязан воспроизводить сегодняшнее поведение байт-в-байт на пульте,
#: который наборов не заводил.
_DEFAULT_SET_PLAN = CanarySetPlan(config.CANARY_DEFAULT_SET, {}, None, "", ())


def _set_plan(set_name: str) -> CanarySetPlan:
    """План прогона по набору `set_name` — либо ИМЕНОВАННЫЙ ОТКАЗ
    (требование 6): каждый случай битого набора обязан остановить команду
    ДО эфемерного клона, то есть до `git clone` и до строки в `tasks` —
    иначе за опечатку в имени набора Оператор платит клоном и заведённой
    задачей, а причина умирает вместе с уничтоженным клоном.
    """
    if set_name == config.CANARY_DEFAULT_SET:
        return _DEFAULT_SET_PLAN
    try:
        sets = models.load_canary_sets()
    except models.ModelsError as exc:
        sys.exit(f"canary: набор {set_name} не прочитан: {exc}")
    entries = sets.get(set_name)
    if entries is None:
        known = ", ".join(sorted(sets)) or "ни одного"
        sys.exit(f"canary: набора {set_name} нет в "
                 f"'{models.CANARY_SETS_KEY}:' {config.MODELS_LOCAL} "
                 f"(известны: {known}); набор по умолчанию — "
                 f"{config.CANARY_DEFAULT_SET}, он в этом разделе не "
                 f"описывается")
    try:
        catalog_data = models.load_catalog()
    except models.ModelsError as exc:
        sys.exit(f"canary: каталог моделей не разобран: {exc}")
    tiers = _set_tiers_or_exit(set_name, entries, catalog_data)
    affected = _roles_of_tiers(tiers)
    return CanarySetPlan(
        set_name, entries,
        _clone_local_layer_text(set_name, tiers, affected, catalog_data),
        _set_summary(tiers, affected),
        _codex_roles(tiers, affected, catalog_data))


def _set_tiers_or_exit(set_name: str, entries: dict, catalog_data) -> dict:
    """{ярус -> модель} набора; каждый из четырёх отказов требования 6
    (б, в, г, д) — `sys.exit` с названной сущностью, из-за которой набор
    битый: без имени роли/модели Оператор не знает, какую строку набора
    править.
    """
    tiers = {}
    for role, entry in entries.items():
        try:
            tier = roles.model_tier(role)
        except roles.RolesError as exc:
            sys.exit(f"canary: набор {set_name} называет роль {role}, ярус "
                     f"которой не прочитан в карте исполнителей целевого "
                     f"sha: {exc}")
        try:
            model = models.catalog_model(entry.model, catalog_data)
        except models.ModelsError as exc:
            sys.exit(f"canary: набор {set_name}, роль {role}: {exc}")
        if entry.provider != model.provider:
            sys.exit(f"canary: набор {set_name}, роль {role}: провайдер "
                     f"{entry.provider} не совпадает с провайдером "
                     f"{model.provider} её модели {entry.model} в каталоге "
                     f"{config.MODELS} — шаг ушёл бы чужим CLI с "
                     f"идентификатором чужой модели, то есть оплаченной "
                     f"попыткой")
        named = tiers.get(tier)
        if named is not None and named != entry.model:
            sys.exit(f"canary: набор {set_name} даёт ярусу {tier} две "
                     f"разные модели ({named} и {entry.model}) — локальный "
                     f"слой клона ключуется ярусом, и такой набор в нём "
                     f"невыразим")
        tiers[tier] = entry.model
    return tiers


def _roles_of_tiers(tiers: dict) -> dict:
    """{роль -> ярус} ВСЕХ agent-ролей карты исполнителей, чей ярус набор
    сдвинул — не только ролей, названных набором.

    Слой клона ключуется ярусом (требование 4), поэтому роль, стоящая на
    том же ярусе, что и названная набором, получает модель набора, названа
    она в нём или нет. Провайдер обязан следовать за моделью: иначе
    предполёт ЕЁ шага в клоне отказал бы расхождением «провайдер роли ≠
    провайдер её модели» (`doctor.check_model_provider_cli`, вызывается по
    конкретной роли), и любой набор ронял бы прогон на первом же шаге
    такой роли. Провайдер яруса определён однозначно: модель на ярусе одна
    (отказ 6г), а её провайдер совпадает с провайдером записи набора
    (отказ 6д).

    Нечитаемая карта исполнителей или нечитаемый ярус — отказ до клона, а
    не пропуск роли: без ярусов согласованный слой клона не собрать, а
    молчаливый пропуск дал бы роль с моделью набора и провайдером пульта.
    """
    try:
        entries = roles.load()
    except roles.RolesError as exc:
        sys.exit(f"canary: карта исполнителей не прочитана: {exc}")
    affected = {}
    for role, entry in entries.items():
        if not isinstance(entry, dict) or entry.get("executor") != "agent":
            continue
        try:
            tier = roles.model_tier(role)
        except roles.RolesError as exc:
            sys.exit(f"canary: ярус роли {role} не прочитан: {exc}")
        if tier in tiers:
            affected[role] = tier
    return affected


def _set_summary(tiers: dict, affected: dict) -> str:
    """Сводка «роль -> модель» прогона (требование 7): по КАЖДОЙ роли,
    которая реально идёт на модели набора, — сам набор живёт в файле вне
    git, и по его сегодняшнему тексту прошлый прогон не восстановить."""
    return ", ".join(f"{role} → {tiers[affected[role]]}"
                    for role in sorted(affected))


def _codex_roles(tiers: dict, affected: dict, catalog_data) -> tuple:
    """Роли прогона, идущие провайдером Codex (SPEC
    01M3HST1381E1FZCYAN2TSB1F3, требование 2), по алфавиту.

    Считается по `affected` (`_roles_of_tiers`), а не по записям самого
    набора: ярус сдвигается целиком, поэтому роль-сосед по ярусу идёт
    провайдером набора, названа она в нём или нет — и её шаг в клоне тоже
    требует входа. Тот же перечень, который `_clone_local_layer_text`
    кладёт в `role_providers:` слоя клона, просто названный отдельно.

    Имя провайдера — из реестра (`codex_provider.CLI_NAME`), не литералом:
    так же его спрашивает `doctor/preflight.py`, и переименование
    провайдера не должно расходиться по двум местам.
    """
    return tuple(role for role in sorted(affected)
                if catalog_data.models[tiers[affected[role]]].provider
                == codex_provider.CLI_NAME)


def _scalar_text(value: str) -> str:
    """Строковое значение слоя клона так, чтобы обратный разбор
    (`yamlmini.scalar`) вернул его дословно: `#` после пробела начинает
    комментарий, а хвостовые пробелы срезаются, поэтому такое значение
    уходит в кавычки. Значение с кавычкой внутри остаётся как есть:
    экранирования внутри кавычек разбор пульта не знает вовсе
    (`yamlmini`, докстринг модуля), и сочинять его здесь значило бы писать
    слой, которого читатель не поймёт."""
    text = str(value)
    if '"' in text:
        return text
    if "#" in text or text != text.strip():
        return f'"{text}"'
    return text


def _clone_local_layer_text(set_name: str, tiers: dict, affected: dict,
                            catalog_data) -> str:
    """Текст локального слоя ЭФЕМЕРНОГО КЛОНА, собранный из набора
    (требования 4-5): ярусы набора на его модели, остальные ярусы — как в
    шаблоне, разрешение каждой `experimental`-модели набора, тариф пульта
    для моделей набора и карта «роль -> провайдер».

    Тариф снимается с локального слоя ПУЛЬТА здесь, ДО клона (требование
    4): стоимость шага в клоне обязана считаться по тарифу этого пульта, а
    не по прейскуранту каталога — иначе метрика стоимости прогона
    разошлась бы с тарифом, на который её же и сравнивают с бейзлайном.
    Слой пульта нечитаем — переопределений просто нет: прогон не должен
    отказывать из-за того, чего у пульта могло и не быть (об этом говорит
    своя строка `doctor`).
    """
    layer_tiers = dict(models.local_template_layer().tiers)
    layer_tiers.update(tiers)
    lines = [
        "# Локальный слой ЭФЕМЕРНОГО КЛОНА канарейки — собран прогоном из",
        f"# набора {set_name} (`canary --k <N> --set {set_name}`, SPEC",
        "# 01M3FQ2Z2PY0E9T5F5WQ207NP5, требования 4-5). Живёт и умирает",
        "# вместе с клоном: ни одна роль пульта набором не переведена,",
        "# roles.yaml ни здесь, ни в главной копии не тронут.",
        "",
        f"{models.TIERS_KEY}:",
    ]
    lines += [f"  {tier}: {layer_tiers[tier]}" for tier in models.TIERS
              if tier in layer_tiers]

    experimental = sorted(
        model_id for model_id in set(tiers.values())
        if catalog_data.models[model_id].status == models.STATUS_EXPERIMENTAL)
    if experimental:
        lines += ["", f"{models.ALLOW_EXPERIMENTAL_KEY}:"]
        lines += [f"  {model_id}: true" for model_id in experimental]

    overrides = _pult_overrides(set(tiers.values()))
    if overrides:
        lines += ["", f"{models.OVERRIDES_KEY}:"]
        for model_id in sorted(overrides):
            override = overrides[model_id]
            lines.append(f"  {model_id}:")
            lines += [f"    {kind}: {price!r}" for kind, price
                      in zip(models.PRICE_KINDS, override.tariff)]
            lines.append(f"    {models.CALIBRATED_AT_KEY}: "
                        f"{_scalar_text(override.calibrated_at)}")
            lines.append(f"    {models.SOURCE_KEY}: "
                        f"{_scalar_text(override.source)}")

    lines += ["", f"{models.ROLE_PROVIDERS_KEY}:"]
    lines += [f"  {role}: {catalog_data.models[tiers[affected[role]]].provider}"
              for role in sorted(affected)]
    return "\n".join(lines) + "\n"


def _pult_overrides(model_ids) -> dict:
    """Переопределения тарифа ПУЛЬТА для моделей набора (требование 4);
    слоя нет или он не разобран — пусто."""
    try:
        local = models.load_local()
    except models.ModelsError:
        return {}
    return {model_id: local.overrides[model_id] for model_id in model_ids
            if model_id in local.overrides}


def _codex_clone_auth(plan: CanarySetPlan) -> CodexCloneAuth | None:
    """Вход Codex для эфемерного клона — либо ИМЕНОВАННЫЙ ОТКАЗ (SPEC
    01M3HST1381E1FZCYAN2TSB1F3, требование 3). `None` — ни одна роль
    прогона не идёт провайдером Codex: дом клона не меняется, проверка
    входа не зовётся, поведение прежнее байт-в-байт (требование 2).

    Зовётся в `cmd_canary` сразу после `_set_plan` — та же стадия, что у
    отказов по битому набору: до `_resolve_target_sha` (сеть) и до первого
    `_ephemeral_clone`, то есть за несделанный однократный шаг Оператора
    пульт не платит ни обращением к сети, ни `git clone`, ни заведённой
    задачей. ВНУТРЬ `_set_plan` эта проверка не ставится намеренно: тот
    разбирает набор и файловой системы не касается вовсе, а его
    собственные тесты (`tests/test_canary_sets.py`) зовут его на наборах
    Codex в песочнице, где дома роли с указателем нет и быть не должно.

    Указатель читается РОВНО один раз и здесь: это одновременно и
    проверка «файла нет или он не читается» (любой `OSError` — нет файла,
    каталог вместо файла, нет прав), и сам payload копии, которую положит
    `_install_codex_pointer` внутри клона. Второе чтение уже из блока
    клона могло бы отказать там, где отказывать поздно.
    """
    if not plan.codex_roles:
        return None
    # Импорт отложенный (пакет `doctor` импортирует этот модуль) и стоит до
    # чтения, а не в ветке отказа: рецепт нужен только отказу, но импорт
    # полупакета на пути обработки ошибки — лишняя причина отказа отказать.
    from . import doctor
    pointer = config.ROLE_HOME / _KEYCHAIN_POINTER_REL
    try:
        payload = pointer.read_bytes()
    except OSError as exc:
        sys.exit(f"canary: набор {plan.name} ведёт провайдером "
                 f"{codex_provider.CLI_NAME} роли "
                 f"{', '.join(plan.codex_roles)}, а указатель связки ключей "
                 f"дома роли пульта не прочитан ({exc}): {pointer} — без "
                 f"него `codex login status` домом эфемерного клона искал бы "
                 f"связку не там, где её нашёл вход Оператора, и шаг роли "
                 f"упал бы авторизацией до первого токена. "
                 f"{doctor.CODEX_AUTH_RECIPE}")
    return CodexCloneAuth(plan.codex_roles[0], payload)


def _install_codex_pointer(payload: bytes) -> None:
    """Кладёт указатель связки ключей в дом роли КЛОНА тем же
    относительным путём (SPEC 01M3HST1381E1FZCYAN2TSB1F3, требование 1).

    Ровно один файл и никакого `Library/` помимо него: копией каталога
    (`copytree` на `Library/` или на `Library/Preferences/`) в клон уехали
    бы и соседние plist'ы, и содержимое каталога связок — ровно та
    изоляция (требование 5), которую задача обязана сохранить.

    `config.ROLE_HOME` читается ЗДЕСЬ, изнутри блока клона: снаружи то же
    имя указывает на дом роли пульта, и копия легла бы обратно в пульт.
    """
    target = config.ROLE_HOME / _KEYCHAIN_POINTER_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)


def _refuse_unless_clone_logged_in(role: str, pult_role_home: Path) -> None:
    """Проверяет вход Codex окружением шага КЛОНА и отказывает до первого
    шага роли, если он не подтверждён (SPEC 01M3HST1381E1FZCYAN2TSB1F3,
    требование 4), НАЗЫВАЯ при этом, чей это дефект (SPEC
    01M3M55070T5NJFYM3QQJH4B9V, требование 6).

    Тем же узлом, что `doctor` (`doctor.check_codex_chatgpt_auth`), а не
    своей копией его логики: расхождение копилось бы молча — `ok` у
    канарейки при красной строке `doctor` или наоборот. По той же причине
    вторым вызовом ниже спрашивается ТОТ ЖЕ узел, а не отдельная проверка
    «а пультом-то вошли?».

    Импорт отложенный, потому что пакет `orchestrator/doctor` импортирует
    этот модуль (тот же приём и по той же причине, что в
    `catalog.py`/`runner.py`).

    Два исхода отказа адресованы РАЗНЫМ людям и потому различаются
    текстом:

    - вход не подтверждён и домом роли пульта — однократный шаг Оператора
      не сделан; в отказ идут имя проверки и её `detail` целиком, потому
      что `detail` несёт рецепт `CODEX_AUTH_RECIPE` с обоими шагами,
      которыми красная строка и чинится;
    - вход домом роли пульта подтверждён, а окружением шага клона нет —
      сломан перенос входа Codex в клон, то есть дефект пульта. Рецепта
      в таком отказе нет намеренно: он адресовал бы Оператору шаг,
      который тот уже сделал, и настоящая причина осталась бы
      неназванной.

    Половин у переноса ДВЕ, и отказ называет обе: окружения двух вызовов
    различаются не одним именем, а тремя (`HOME`, `ZDOTDIR`,
    `CODEX_HOME`), поэтому тот же исход «клон не `ok`, пульт `ok`» даёт и
    сломанный указатель связки ключей (`_install_codex_pointer`;
    например, относительный путь `_KEYCHAIN_POINTER_REL` сменился в новой
    macOS). Назови отказ единственной причиной — Оператор читал бы две
    исправные функции, а сломанная третья в тексте не значилась бы вовсе.

    Второй вызов делается ТОЛЬКО на пути отказа: при подтверждённом входе
    узел зовётся ровно один раз, как до задачи (требование 6).
    """
    from . import doctor
    check = doctor.check_codex_chatgpt_auth(role)
    if check.status == "ok":
        return
    if _pult_home_login_confirmed(role, pult_role_home):
        sys.exit(f"canary: вход Codex домом роли пульта подтверждён, а "
                 f"проверка {check.name} окружением шага эфемерного клона "
                 f"— нет. Это дефект пульта, а не несделанный шаг "
                 f"Оператора: повторный вход этого не изменит. Сломана "
                 f"одна из двух половин переноса входа в клон — "
                 f"переопределение {codex_provider.HOME_ENV} "
                 f"(`canary._ephemeral_clone` его ставит, "
                 f"`CodexProvider.environment` отдаёт; шагу клона отдано "
                 f"{codex_provider.HOME_ENV}="
                 f"{pult_role_home / codex_provider.DEPLOYED_HOME_DIR}) "
                 f"и/или указатель связки ключей "
                 f"(`canary._install_codex_pointer` кладёт его в "
                 f"{config.ROLE_HOME / _KEYCHAIN_POINTER_REL}) — до "
                 f"починки прогон на наборе с ролями "
                 f"{codex_provider.CLI_NAME} невозможен.")
    sys.exit(f"canary: вход Codex не подтверждён ни окружением шага "
             f"эфемерного клона, ни домом роли пульта — шаг роли упал бы "
             f"авторизацией за деньги. {check.name}: {check.detail}")


def _pult_home_login_confirmed(role: str, pult_role_home: Path) -> bool:
    """Подтверждён ли вход Codex домом роли ПУЛЬТА — тем же узлом
    `doctor`, но с окружением, которое собралось бы вне блока клона
    (SPEC 01M3M55070T5NJFYM3QQJH4B9V, требование 6).

    Снимается и переадресация `config.ROLE_HOME`, и переопределение
    `CODEX_HOME`: узел берёт все три имени у `CodexProvider.environment`,
    и ответ обязан относиться к тому дому, каким входил Оператор, а не к
    гибриду «`HOME` клона + `CODEX_HOME` пульта». Оба снятия — в
    `finally`: вызывающий на обеих ветках уходит `sys.exit`, а внешний
    `finally` блока клона до этого ещё не добрался, и оставленные
    пультовские пути увели бы уборку клона не туда.
    """
    from . import doctor
    saved_role_home = config.ROLE_HOME
    saved_override = codex_provider.set_codex_home_override(None)
    config.ROLE_HOME = pult_role_home
    try:
        return doctor.check_codex_chatgpt_auth(role).status == "ok"
    finally:
        config.ROLE_HOME = saved_role_home
        codex_provider.set_codex_home_override(saved_override)


@contextmanager
def _ephemeral_clone(target_sha: str | None = None,
                    local_layer_text: str | None = None,
                    codex_auth: CodexCloneAuth | None = None):
    """Заводит эфемерный клон пульта на время блока: собственный рабочий
    каталог, собственная БД состояния, собственный origin-заглушка
    (требование 2, AC-2) — и убирает его по выходу из блока, включая
    исключение (требование 4, AC-4). Патчит МОДУЛЬНЫЕ атрибуты
    `config.py`, через которые весь FSM-код читает пути пульта — не сам
    код FSM (см. модульный докстринг).

    `target_sha` (SPEC 01M2B6K02YVJBWE1JDWP85EJH0, требование 1/AC-3) —
    клон делает checkout именно этого sha (`git checkout -B
    <MAIN_BRANCH> <target_sha>`, ветка не отсоединённым HEAD — остальной
    код канарейки и FSM ожидают, что клон стоит НА `config.MAIN_BRANCH`,
    как обычный клон), а не остаётся на HEAD `outer_root`, унаследованном
    от обычного `git clone`: раньше клон всегда тестировал код ПИНА
    (HEAD главной копии) — ровно тот тупик 12.09, который устраняет эта
    задача. Локальный `git clone` источника на диске переносит объекты
    файловой копией/хардлинком каталога `objects/` целиком, не только
    объекты, достижимые с текущего HEAD источника, — поэтому `target_sha`,
    только что подтянутый `gitcmd.fetch_ref_sha` в `outer_root` ДО входа в
    этот блок (сама ссылка уже удалена, но объект остался в базе), доедет
    до `dest` даже будучи недостижимым ни с одной ветки `outer_root`.
    Checkout — ДО создания `origin_dir` ниже, чтобы origin-заглушка тоже
    несла `config.MAIN_BRANCH` на `target_sha`, не на прежнем HEAD.

    `target_sha=None` (по умолчанию) — обратная совместимость с `tasks/
    01M1SC3Y20YBTTJVQDJBF2NDQW/acceptance_tests/
    test_canary_report_kill_reason.py` (залоченная планка ДРУГОЙ, уже
    смерженной задачи, зовущая `_run_one_task` без `target_sha`, что
    транслируется в вызов `_ephemeral_clone()` без аргументов): checkout
    не делается вовсе, клон остаётся на HEAD `outer_root`, ровно прежнее
    поведение байт-в-байт.

    Origin эфемерного клона — ОТДЕЛЬНЫЙ одноразовый bare-клон `origin_dir`
    рядом с самим клоном (снят с `dest` сразу после его создания, то есть
    несёт `config.MAIN_BRANCH` на момент старта прогона), не сам
    `outer_root` и не несуществующая схема (см. комментарий у бывшей
    `ORIGIN_STUB_URL`, задача 01M297HFSKV3GVZJ9YF20FZEZE): `workspace.
    ensure` при заведении НОВОЙ ветки задачи требует успешного `git fetch
    origin` — с недостижимого адреса он валился бы на каждом канареечном
    прогоне, а с прямым `outer_root` best-effort push из клона реально
    достигал бы главного пульта (требование 3 это запрещает). Bare-клон —
    ни то, ни другое: fetch с него проходит локально, а push по-прежнему
    не покидает пару временных каталогов, убираемых вместе. `--shared`
    (объекты — alternate-ссылка на `dest`, не копия): без него вторая
    полная копия объектов пульта на каждую канареечную задачу подрывала
    временной запас AC-11/AC-8/AC-9 (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ) —
    `origin_dir` живёт и умирает строго вместе с `dest`, объекты которого
    он занимает, поэтому «протухание» alternate-ссылки после prune
    исходника здесь не сценарий.

    `local_layer_text` (SPEC 01M3FQ2Z2PY0E9T5F5WQ207NP5, требования 4-5) —
    готовый текст локального слоя КЛОНА, собранный из набора ролей
    (`_clone_local_layer_text`): кладётся ПОСЛЕ `catalog.cmd_init()`,
    поверх положенного им шаблона. Именно после, а не до: порядок «сначала
    слой, потом init» работал бы только за счёт того, что
    `models.ensure_local_template` не трогает существующий файл, — связь
    неочевидная, и первая же правка того умолчания положила бы шаблон
    поверх собранного слоя молча. `None` (по умолчанию) — слой клона
    остаётся ровно шаблоном, который кладёт `cmd_init`, то есть прежнее
    поведение байт-в-байт (требование 3, AC-14).

    `codex_auth` (SPEC 01M3HST1381E1FZCYAN2TSB1F3, требования 1/4) — вход
    Codex для клона: указатель связки ключей копируется в дом роли КЛОНА,
    `CODEX_HOME` шага переопределяется каталогом клиента дома роли ПУЛЬТА
    (SPEC 01M3M55070T5NJFYM3QQJH4B9V, требование 1), и вход проверяется
    узлом `doctor` уже этим окружением; не `ok` — отказ до `yield`, то
    есть до заведения задачи и до первого шага роли. `None` (по
    умолчанию) — ни одна роль прогона не идёт провайдером Codex, дом клона
    остаётся ровно тем, что развернул холодный старт (требование 2), а
    окружение шага — тремя именами от `config.ROLE_HOME` клона.

    Все три действия — ПОСЛЕ `catalog.cmd_init()` и ВНУТРИ `try:`, и ни
    одно не переставимо. После `cmd_init()`: `catalog._deploy_role_home_
    reference` выходит первой же строкой на существующем `ROLE_HOME`, и
    указатель, положенный раньше, лишил бы роли клона курируемого дома
    целиком. Внутри `try:`: `finally` ниже — единственная уборка клона, и
    отказ проверки входа обязан оставить `/tmp` чистым, а скопированный
    указатель не обязан пережить прогон. Переопределение — ДО проверки
    входа: зелёная строка предполёта обязана доказывать вход того дома,
    каким пойдёт шаг (требование 5), а оба читают один
    `CodexProvider.environment`.

    Переопределение `CODEX_HOME` сохраняется и восстанавливается тем же
    приёмом и в том же `finally`, что и пути `config`: оно такое же
    модульное состояние процесса, и выход исключением обязан вернуть
    боевому шагу прежнее окружение (требование 4). Восстанавливается
    ПРЕЖНЕЕ значение, а не `None`, — по той же причине, по которой пути
    восстанавливаются из `saved`: вложенный блок не вправе снимать
    переопределение внешнего.

    `tempfile.mkdtemp`/`shutil.rmtree` — единственные стандартные
    способы завести/убрать временный каталог в CPython (перехватываются
    приёмочной песочницей этой задачи, `_EphemeralDirTracker`, тем же
    приёмом, каким `tempfile.TemporaryDirectory` изнутри их и зовёт).
    """
    outer_root = config.ROOT
    dest = Path(tempfile.mkdtemp(prefix="artel-canary-"))
    origin_dir = Path(tempfile.mkdtemp(prefix="artel-canary-origin-"))
    saved = {attr: getattr(config, attr) for attr in _CLONE_CONFIG_ATTRS}
    saved_codex_home = codex_provider.codex_home_override()
    try:
        clone = subprocess.run(
            ["git", "clone", "-q", str(outer_root), str(dest)],
            capture_output=True, text=True)
        if clone.returncode != 0:
            raise RuntimeError(
                f"canary: эфемерный клон не создан: {clone.stderr.strip()}")
        if target_sha is not None:
            checkout = subprocess.run(
                ["git", "checkout", "-q", "-B", config.MAIN_BRANCH, target_sha],
                cwd=dest, capture_output=True, text=True)
            if checkout.returncode != 0:
                raise RuntimeError(
                    f"canary: checkout целевого sha {target_sha} в "
                    f"эфемерном клоне не удался: {checkout.stderr.strip()}")
        mirror = subprocess.run(
            ["git", "clone", "-q", "--bare", "--shared", str(dest),
             str(origin_dir)],
            capture_output=True, text=True)
        if mirror.returncode != 0:
            raise RuntimeError(
                f"canary: origin-заглушка не создана: "
                f"{mirror.stderr.strip()}")
        origin = subprocess.run(
            ["git", "remote", "set-url", "origin", str(origin_dir)],
            cwd=dest, capture_output=True, text=True)
        if origin.returncode != 0:
            raise RuntimeError(
                f"canary: origin-заглушка не выставлена: "
                f"{origin.stderr.strip()}")
        for attr in _CLONE_CONFIG_ATTRS:
            setattr(config, attr, dest / saved[attr].relative_to(outer_root))
        catalog.cmd_init()
        if local_layer_text is not None:
            config.MODELS_LOCAL.parent.mkdir(parents=True, exist_ok=True)
            config.MODELS_LOCAL.write_text(local_layer_text, encoding="utf-8")
        if codex_auth is not None:
            _install_codex_pointer(codex_auth.pointer)
            codex_provider.set_codex_home_override(
                saved["ROLE_HOME"] / codex_provider.DEPLOYED_HOME_DIR)
            _refuse_unless_clone_logged_in(codex_auth.role, saved["ROLE_HOME"])
        yield dest
    finally:
        codex_provider.set_codex_home_override(saved_codex_home)
        for attr, value in saved.items():
            setattr(config, attr, value)
        shutil.rmtree(dest, ignore_errors=True)
        shutil.rmtree(origin_dir, ignore_errors=True)


def _spec_gate_next_state(conn, task_id: str, t) -> str | None:
    """Куда ведёт SPEC-гейт — та же ветка условий, что и у
    `fsm._approve_spec_gate` для `spec_gate` (AC-разметка SPEC),
    скопированная сюда намеренно (см. модульный докстринг: не через
    `cmd_approve`). Источник SPEC — `artifact_source.resolve` (SPEC
    01M2A22CG2P0E69H00RDHFF3K4, требование 1), не `gitcmd.
    on_foreign_branch(t["branch"])`: после ADR-0016 `tasks/<id>/` живёт
    только в артефактной ветке — ни на кодовой ветке задачи, ни на диске
    `config.TASKS/<id>/SPEC.md`, и старая проверка давала пустой словарь
    на обеих ветках, уводя канареечную задачу с AC-разметкой мимо
    `tests_writing`. Параметр `t` в теле не используется (AC-4: источник
    определяется исключительно через `artifact_source.resolve`) —
    оставлен третьим позиционным ради сигнатуры, зафиксированной
    залоченной приёмочной планкой (ANSWER-1).

    `None` — SPEC не прочитан ни в одном источнике (дерево не на ветке
    задачи, файл там не прочитан) — требование 2: это не трактуется как
    «SPEC без AC-разметки», вызывающий код (`_pass_spec_gate`) решает,
    как трактовать `None` отдельно от найденного, но пустого SPEC.
    """
    branch, foreign = artifact_source.resolve(conn, task_id)
    if foreign:
        spec_text = fsm._read_branch_text_or_refuse(conn, task_id, branch,
                                                     "SPEC.md")
        if spec_text is None:
            return None
        meta = yamlmini.frontmatter(spec_text) or {}
    else:
        meta = artifacts.frontmatter(config.TASKS / task_id / "SPEC.md")
    return "tests_writing" if guard.requires_ac_markup(meta) else "in_dev"


def _pass_spec_gate(conn, task_id: str) -> None:
    t = store.get_task(conn, task_id)
    next_state = _spec_gate_next_state(conn, task_id, t)
    if next_state is None:
        # Требование 2/AC-3: SPEC не найден ни в одном источнике не
        # трактуется как «SPEC без AC-разметки» (что увело бы задачу в
        # `in_dev`, минуя test_author) — задача снимается тем же путём,
        # что и прочие случаи «прогон дальше не ведёт».
        branch, _ = artifact_source.resolve(conn, task_id)
        _kill_inconclusive(
            conn, task_id,
            f"canary: SPEC не найден в источнике артефактов ({branch})")
        return
    store.set_state(conn, task_id, next_state, CANARY_MARK_ACTOR,
                    expected_state="spec_gate",
                    detail="canary: гейт SPEC пройден автоматически "
                    "(эквивалент operator approve)")


def _pass_acceptance_gate(conn, task_id: str) -> None:
    t = store.get_task(conn, task_id)
    if fsm._pull_main_or_escalate(conn, task_id, t, "acceptance") in (
            "escalated", "refused"):
        return
    store.set_state(conn, task_id, "merge_gate", CANARY_MARK_ACTOR,
                    expected_state="acceptance",
                    detail="canary: приёмка пройдена автоматически "
                    "(эквивалент operator approve)")


def _kill_at_merge_gate(conn, task_id: str) -> None:
    store.journal(conn, task_id, CANARY_MARK_ACTOR,
                 "canary: merge_gate не approve — задача убивается",
                 "канареечная задача никогда не мержится в main "
                 "(tasks/T065/SPEC.md, требование 3)")
    cleanup.cmd_kill(task_id)


def _kill_at_verifying(conn, task_id: str) -> None:
    """v1-эпоха (SPEC T079) — `_drive_task` эту функцию больше НЕ зовёт
    (ADR-0015 переставил `verifying` перед ревьювером, реальное вождение
    идёт через `_pass_verifying`, см. её докстринг). Функция и признание
    её литерала «штатным» в `_kill_outcome_note` оставлены нетронутыми
    ЧИСТО ради совместимости с залоченной планкой ДРУГОЙ, уже смерженной
    задачи (`tasks/01M1SC3Y20YBTTJVQDJBF2NDQW/acceptance_tests/
    test_canary_report_kill_reason.py::
    test_ac4_verifying_kill_is_also_reported_as_normal` зовёт её
    напрямую) — правка чужой планки требует отдельного мандата Оператора
    (REVIEW.md 01M1TKP269W9JN3NBJCR5Q6C3B итерации 2, R2-F1), которого
    эта задача не получала."""
    store.journal(conn, task_id, CANARY_MARK_ACTOR,
                 _VERIFYING_KILL_ACTION,
                 "канареечная задача не заводит Draft MR и не имеет "
                 "реального CI ветки (tasks/T079/SPEC.md, требование 1 — "
                 "canary вне объёма адаптера)")
    cleanup.cmd_kill(task_id)


def _pass_verifying(conn, task_id: str) -> None:
    """`verifying` (SPEC T079; ADR-0015 переставил его перед ревьювером,
    `in_dev -> verifying -> review`) ждёт реального CI ветки — у
    канареечной задачи его никогда не будет, а Draft MR она не заводит
    (tasks/T079/SPEC.md, требование 1 — canary вне объёма адаптера).
    Раньше (до ADR-0015) это состояние шло ПОСЛЕ ревью и её убийство
    здесь было штатным финалом прогона; теперь оно стоит ДО первого
    ревью, и приравнивание к финальному kill убивало канарейку прежде,
    чем сценарий «не сошлась»/эскалация вообще успевали случиться
    (ANSWER-3.md, 06.09: 6 из 18 приёмочных тестов планки покраснели
    после подтяжки main по этой причине). Проходим синтетически, тем же
    приёмом, что `_pass_spec_gate`/`_pass_acceptance_gate` — единственный
    штатный kill канарейки остаётся `_kill_at_merge_gate`."""
    store.journal(conn, task_id, CANARY_MARK_ACTOR,
                 "canary: verifying пройден синтетически — CI у "
                 "эфемерного клона нет",
                 "канареечная задача не заводит Draft MR и не имеет "
                 "реального CI ветки (tasks/T079/SPEC.md, требование 1 — "
                 "canary вне объёма адаптера)")
    store.set_state(conn, task_id, "review", CANARY_MARK_ACTOR,
                    expected_state="verifying",
                    detail="canary: verifying пройден синтетически")


def _pass_escalated_with_synthetic_answer(conn, task_id: str) -> None:
    """Возврат из `escalated` синтетическим ANSWER Оператора-заглушки
    (требование 6, AC-6) — повторяет эффект ветки `elif state ==
    "escalated"` `fsm._cmd_approve` (читает `answer_baseline`/
    `escalated_from`, пишет `store.set_state`), НЕ вызов
    `fsm.cmd_approve`: тот на `escalated` требует sha
    (`fsm.APPROVE_NEEDS_SHA`), которого у первого вызова ещё нет, и
    печатает «повтори с sha» вместо перехода — тот же принцип, что и
    остальные гейты этого модуля (не через `cmd_approve`, см. модульный
    докстринг). Не полная копия: не проверяет `answer_baseline`
    (canary сама пишет ровно один новый ANSWER непосредственно перед
    вызовом — проверка была бы тавтологией) и не зовёт
    `_maybe_ensure_draft_mr` (для канареечных задач он и так no-op,
    `github_adapter.py`, `is_canary`) — при будущей содержательной правке
    оригинала в `fsm.py` это стоит перепроверить (REVIEW.md итерации 1,
    R1-F3).

    `answer.cmd_answer` коммитит ANSWER-n.md в артефактную ветку
    (best-effort push уходит в origin-заглушку клона, требование 3) —
    он не требует ни sha, ни фиксации, только `state == "escalated"`.
    """
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8")
    try:
        tmp.write(
            "Синтетический ответ прогона канарейки (заглушка Оператора, "
            "SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ, требование 6): вариант A — "
            "продолжай штатным путём.\n")
        tmp.close()
        answer.cmd_answer(task_id, tmp.name)
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    t = store.get_task(conn, task_id)
    back = t["escalated_from"] or "in_dev"
    store.update_task(conn, task_id, escalated_from=None, answer_baseline=None)
    store.set_state(conn, task_id, back, CANARY_MARK_ACTOR,
                    expected_state="escalated",
                    detail="canary: эскалация закрыта синтетическим "
                    "ANSWER — прогон продолжается без Оператора")


def _last_role_skip_reason(conn, task_id: str) -> str | None:
    """Последняя запись журнала — `agent run SKIPPED` по одной из двух
    причин ТЗ (требование 3/AC-3) -> её `detail` дословно; иначе `None`
    (в том числе на пустом журнале — генуинная стагнация без единой
    записи не должна замкнуться коротко, AC-7)."""
    steps = store.task_steps(conn, task_id)
    if not steps:
        return None
    last = steps[-1]
    if last["action"] != "agent run SKIPPED":
        return None
    detail = last["detail"] or ""
    if any(reason in detail for reason in _SKIP_SHORTCIRCUIT_REASONS):
        return detail
    return None


def _acceptance_refusal_blocks_in_dev(conn, task_id: str) -> bool:
    """Последняя запись журнала задачи — отказ `in_dev -> verifying` по
    красной приёмочной планке (01M2ARQD7C472KZACB3SZXGF1N, требование 2):
    либо напрямую `fsm` (`_ACCEPTANCE_TESTS_REFUSAL_ACTION` — сам
    `action`), либо стоп-кран T038 `auto` (`_AUTO_STOPPED_ACTION`, тот же
    текст ВНУТРИ `detail` — `auto.py::auto_stop` журналирует `f"{state}:
    {reason}"`, а `reason` `_pre_advance_step` несёт дословный `action`
    отказа `advance`). Отказы другого класса (планка не найдена в
    источнике, зоны, гейт заявки мутации, лок планки — требование 4) этим
    литералом не журналируются, условие на них не срабатывает — прежняя
    стагнация (`config.CANARY_MAX_STALL_ITERS`) остаётся байт-в-байт."""
    steps = store.task_steps(conn, task_id)
    if not steps:
        return False
    last = steps[-1]
    if last["actor"] == "fsm" and last["action"] == _ACCEPTANCE_TESTS_REFUSAL_ACTION:
        return True
    if last["action"] == _AUTO_STOPPED_ACTION:
        return _ACCEPTANCE_TESTS_REFUSAL_ACTION in (last["detail"] or "")
    return False


def _has_subtasks(conn, task_id: str) -> bool:
    """Родитель поделён (01M29284PTCJXGERV5262E9XMM, требование 1) — хоть
    одна строка `tasks` ссылается на `task_id` через `parent_task_id`.
    Фильтрация уже существующего `store.all_tasks(conn)`, без новой
    сырой SQL вне `store.py` (ADR-0003 3ж).

    `conn` без таблицы `tasks` (БД ещё не проинициализирована `init`,
    тот же вырожденный случай, что `schema.migrate` уже трактует как
    штатный, `schema.py:92-93`) — подзадач нет физически, не ошибка."""
    if not store.table_columns(conn, "tasks"):
        return False
    return any(r["parent_task_id"] == task_id for r in store.all_tasks(conn))


def _kill_outcome_note(conn, task_id: str, steps) -> str:
    """Причина исхода `killed` для отчёта прогона (требование 4, AC-4):
    родитель, поделённый на подзадачи (01M29284PTCJXGERV5262E9XMM,
    требование 4) — «поделена», штатный исход наравне со «штатно».
    Иначе прежняя классификация: «штатно» — `_kill_at_merge_gate`
    (единственный путь, которым РЕАЛЬНОЕ вождение `_drive_task` убивает
    задачу сегодня — `verifying` теперь проходится синтетически, не
    убивает, `_pass_verifying`) и `_kill_at_verifying` (недостижима из
    `_drive_task`, распознаётся здесь только ради совместимости с чужой
    залоченной планкой — см. докстринг `_kill_at_verifying`), иначе —
    «не сошлась: <причина>» с текстом причины из журнальной записи
    `_kill_inconclusive` (её `detail` — фиксированный литерал-маркер,
    `action` несёт саму причину — требование 3/AC-3 идёт этим же путём).

    Исчерпание уже поднятого потолка (01M3HJQV2QV9BXNXSH3F8STAYH,
    требование 9) — ТРЕТИЙ, свой исход: причина из `action` записи
    `_kill_ceiling_exhausted` возвращается как есть, без приписки «не
    сошлась». Приписка сделала бы два взаимоисключающих диагноза одной
    строкой отчёта: «шаблон не уложился в потолок» и «конвейер не
    сошёлся»."""
    if _has_subtasks(conn, task_id):
        return "поделена"
    for r in reversed(steps):
        if r["actor"] != CANARY_MARK_ACTOR:
            continue
        if r["action"] in (_MERGE_GATE_KILL_ACTION, _VERIFYING_KILL_ACTION):
            return "штатно"
        if r["detail"] == _CEILING_EXHAUSTED_KILL_DETAIL:
            return r["action"]
        if r["detail"] == _INCONCLUSIVE_KILL_DETAIL:
            return f"не сошлась: {r['action']}"
    return "не сошлась"


def _ceiling_exhausted(steps) -> bool:
    """Задача снята исчерпанием уже поднятого потолка (требование 10) —
    запись `_kill_ceiling_exhausted` в журнале. Отдельно от
    `_kill_outcome_note`: вердикт прогона читает признак, а не текст
    причины."""
    return any(row["actor"] == CANARY_MARK_ACTOR
              and row["detail"] == _CEILING_EXHAUSTED_KILL_DETAIL
              for row in steps)


def _ceiling_raise_line(steps) -> str | None:
    """Строка отчёта прогона о подъёме потолка (требование 11) или `None`,
    если подъёма не было. Журнал задачи живёт в БД эфемерного клона и
    умирает вместе с ним — без этой строки Оператор, читая зелёный
    прогон, не узнал бы, что задача уложилась только со второго потолка."""
    for row in steps:
        if (row["actor"] == CANARY_MARK_ACTOR
                and row["action"] == _CEILING_RAISE_ACTION):
            return f"{row['action']} — {row['detail'] or ''}".strip()
    return None


def _kill_inconclusive(conn, task_id: str, detail: str) -> None:
    """Убивает ОДНУ задачу как «не сошлась» вместо бесконечного цикла без
    прогресса (REVIEW.md итерации 1, R1-F1) — журналирует причину,
    поднимает Оператору тот же вид алерта, что и отклонение метрик от
    бейзлайна (`kind=threshold`, `source=canary`; требование 12: реакция
    — только сигнал, никакого автоисправления), и убивает штатным
    `cleanup.cmd_kill`. Прогон `cmd_canary` остальных k-1 задач набора
    это не останавливает — цикл `for` в `cmd_canary` последовательный и
    не разделяет состояние между задачами."""
    store.journal(conn, task_id, CANARY_MARK_ACTOR, detail,
                 "прогон дальше эту задачу не ведёт — cleanup.cmd_kill")
    alerts.raise_alert(conn, task_id, "threshold", "canary", detail)
    cleanup.cmd_kill(task_id)


def _budget_escalation(steps) -> bool:
    """Последний переход `state -> escalated` журнала — эскалация ПО
    БЮДЖЕТУ (требование 6): его `detail` несёт причину
    `budget.enforce_budget`. Смотрится именно последний переход: задача
    могла эскалировать раньше по другой причине, и прогон обязан
    реагировать на ту эскалацию, в которой стоит СЕЙЧАС."""
    for row in reversed(steps):
        if row["action"] != "state -> escalated":
            continue
        return _BUDGET_ESCALATION_DETAIL_MARK in (row["detail"] or "")
    return False


def _ceiling_already_raised(steps) -> bool:
    """Потолок этой задачи прогон уже поднимал (требование 8) — запись
    `_CEILING_RAISE_ACTION` в журнале. Журнал, а не переменная цикла: см.
    комментарий у самого литерала."""
    return any(row["actor"] == CANARY_MARK_ACTOR
              and row["action"] == _CEILING_RAISE_ACTION for row in steps)


def _raise_task_ceiling(conn, task_id: str, t) -> None:
    """ОДНОКРАТНЫЙ подъём потолка канареечной задачи, эскалировавшей по
    бюджету (требования 7, 11): новый потолок — прежний, умноженный на
    `config.CANARY_BUDGET_CEILING_FACTOR`, факт подъёма — в журнал задачи,
    а сама задача возвращается в состояние, из которого эскалировала.

    Возврат — существующим `_pass_escalated_with_synthetic_answer`, не
    собственным `set_state`: канал возврата из `escalated` в системе один
    (ANSWER Оператора-заглушки в артефактной ветке), и второй, «тихий»,
    расходился бы с тем, что Оператор делает руками — `budget <id> <usd>`
    и затем ответ на эскалацию.

    Потолок правится ДО возврата: вернувшаяся задача иначе упёрлась бы в
    `budget.budget_block` на первом же запуске роли, то есть подъём не дал
    бы прогону продолжиться.
    """
    before = t["budget_usd"] or 0.0
    after = before * config.CANARY_BUDGET_CEILING_FACTOR
    spent = budget.spent_with_estimate(t)
    store.update_task(conn, task_id, budget_usd=after)
    store.journal(
        conn, task_id, CANARY_MARK_ACTOR, _CEILING_RAISE_ACTION,
        f"эскалация по бюджету (${spent:.2f} из ${before:.2f}): потолок "
        f"задачи поднят до ${after:.2f} (множитель "
        f"{config.CANARY_BUDGET_CEILING_FACTOR}) — прогон продолжается, "
        "второго подъёма не будет")
    _pass_escalated_with_synthetic_answer(conn, task_id)


def _kill_ceiling_exhausted(conn, task_id: str, t) -> None:
    """Снимает задачу прогона по исчерпанию УЖЕ ПОДНЯТОГО потолка
    (требования 8-9): своя причина исхода с фактическими числами и ролью
    шага, свой литерал-маркер `detail`, тот же алерт и тот же штатный
    `cleanup.cmd_kill`, что и у `_kill_inconclusive`.

    Отдельный исход, а не «задача не сходится»: поднятый потолок —
    конечная верхняя граница расхода канареечной задачи, и её пробой
    означает «шаблон не уложился в потолок», а не «конвейер не сошёлся»
    (требование 10 требует различать эти диагнозы и по вердикту прогона).

    Роль шага — по `escalated_from`, который `budget.enforce_budget`
    записал перед самой эскалацией: именно на шаге этой роли потолок и
    кончился. Состояние вне `config.STATE_ROLE` (эскалация не с шага
    роли) — печатаем само состояние: причина без адреса шага
    бессодержательна.
    """
    spent = budget.spent_with_estimate(t)
    ceiling = t["budget_usd"] or 0.0
    origin = t["escalated_from"] or ""
    where = config.STATE_ROLE.get(origin, origin or "неизвестном")
    reason = (f"canary: {_CEILING_EXHAUSTED_REASON}: ${spent:.2f} из "
             f"${ceiling:.2f} на шаге {where}")
    store.journal(conn, task_id, CANARY_MARK_ACTOR, reason,
                 _CEILING_EXHAUSTED_KILL_DETAIL)
    alerts.raise_alert(conn, task_id, "threshold", "canary", reason)
    cleanup.cmd_kill(task_id)


def _drive_task(conn, task_id: str) -> None:
    """Ведёт ОДНУ заведённую канарейкой задачу до её конца (`killed`) или
    до состояния, дальше которого canary не умеет вести — не роняет
    прогон остальных задач набора ни в одном случае.

    Два независимых потолка (REVIEW.md итерации 1, R1-F1) не дают циклу
    `while True` крутиться бесконечно: `escalation_cycles` — число
    возвратов из `escalated` подряд (лимит ревью не сброшен — задача
    эскалируется заново на первом же `changes_requested`, каждый круг
    реально тратит бюджет); `stall_streak` — число проходов подряд без
    ЛЮБОГО прогресса (ни смена состояния, ни расход бюджета) — сценарий
    «бюджет исчерпан, состояние агентское»: `runner.cmd_run` отказывает
    `SystemExit`'ом ДО смены состояния на каждом вызове, `auto.cmd_auto`
    эту причину не отличает от «шаг ещё не готов» и просто возвращается.
    """
    escalation_cycles = 0
    stall_streak = 0
    prev_signature = None
    dev_retries = 0
    while True:
        auto.cmd_auto(task_id)
        t = store.get_task(conn, task_id)
        state = t["state"]
        if state != "in_dev":
            # Требование 3: потолок повторов developer держит один визит
            # `in_dev` — уход из состояния (гейт пройден, эскалация,
            # kill) обнуляет счётчик для следующего возможного визита.
            dev_retries = 0
        skip_detail = _last_role_skip_reason(conn, task_id)
        if skip_detail is not None:
            # Требование 3/AC-3: не тратим холостые проходы до
            # `CANARY_MAX_STALL_ITERS` — рабочий/окружения каталог роли
            # не появится сам по себе на следующем проходе, причина
            # известна СЕЙЧАС и не должна теряться после уборки клона.
            _kill_inconclusive(conn, task_id, f"canary: {skip_detail}")
            return
        if state == "spec_gate":
            _pass_spec_gate(conn, task_id)
            continue
        if state == "acceptance":
            _pass_acceptance_gate(conn, task_id)
            continue
        if state == "merge_gate":
            _kill_at_merge_gate(conn, task_id)
            return
        if state == "verifying":
            _pass_verifying(conn, task_id)
            continue
        if state == "escalated":
            # Требования 6-9: эскалация ПО БЮДЖЕТУ идёт своим путём —
            # первая закрывается однократным подъёмом потолка, повторная
            # (потолок уже поднят) снимает задачу своим исходом. Развилка
            # стоит ДО `escalation_cycles` и счётчик не трогает: потолок
            # повторных эскалаций остаётся прежним для ВСЕХ остальных
            # эскалаций прогона («Не входит» SPEC).
            steps = store.task_steps(conn, task_id)
            if _budget_escalation(steps):
                if _ceiling_already_raised(steps):
                    _kill_ceiling_exhausted(conn, task_id, t)
                    return
                _raise_task_ceiling(conn, task_id, t)
                continue
            escalation_cycles += 1
            if escalation_cycles > config.CANARY_MAX_ESCALATION_CYCLES:
                _kill_inconclusive(
                    conn, task_id,
                    f"canary: {config.CANARY_MAX_ESCALATION_CYCLES} "
                    "повторных эскалаций подряд — задача не сходится")
                return
            _pass_escalated_with_synthetic_answer(conn, task_id)
            continue
        if state == "in_dev" and _acceptance_refusal_blocks_in_dev(conn, task_id):
            # Требование 2 (решение Оператора 12.09, вариант а):
            # воспроизводим ручной возврат Оператора `run <id>` — в
            # реальном конвейере `auto` уже остановился бы здесь стоп-
            # краном T038, не дав developer ни одного шанса на повтор.
            dev_retries += 1
            if dev_retries > config.CANARY_MAX_DEV_RETRIES:
                _kill_inconclusive(
                    conn, task_id,
                    f"canary: {config.CANARY_MAX_DEV_RETRIES} повторов "
                    "developer на красной планке — задача не сходится")
                return
            store.journal(
                conn, task_id, CANARY_MARK_ACTOR, _DEV_RETRY_ACTION,
                f"попытка {dev_retries}/{config.CANARY_MAX_DEV_RETRIES} — "
                "developer получает бриф с блоком «ОТКАЗ ADVANCE (история)»")
            runner.cmd_run(task_id)
            # Требование 3: повтор — прогресс цикла, не стагнация;
            # `prev_signature` намеренно не трогаем — следующий проход без
            # прогресса (если он случится) сравнивается с состоянием ДО
            # этого повтора, тем же приёмом, что и ветка `escalated` выше.
            stall_streak = 0
            continue
        if runner.step_role(t) is not None:
            # `auto` остановился, не дойдя до гейта (лимит AUTO_MAX_STEPS
            # за один вызов) — задаче всё ещё есть кому работать, просто
            # продолжаем цикл новым вызовом `auto.cmd_auto`. Отличаем это
            # от «прогресса нет вовсе» по неизменности (состояние,
            # потраченное) между проходами.
            signature = (state, t["spent_usd"])
            if signature == prev_signature:
                stall_streak += 1
                if stall_streak >= config.CANARY_MAX_STALL_ITERS:
                    _kill_inconclusive(
                        conn, task_id,
                        f"canary: {config.CANARY_MAX_STALL_ITERS} "
                        f"проходов подряд без прогресса в состоянии "
                        f"{state} — задача не сходится")
                    return
            else:
                stall_streak = 0
                prev_signature = signature
            continue
        # done/killed или любое другое состояние без агентской роли и не
        # входящее в canary-гейты выше — canary дальше не ведёт.
        return


def merges_since_last_green_run(conn, target_sha: str) -> int | None:
    """Возраст (в мержах main) самого свежего ЗЕЛЁНОГО прогона канарейки,
    чей `main_sha` лежит на истории `target_sha` — общий guard AC-1/AC-3/
    AC-4 (tasks/01M1NGFK3N6MRMYGCC09H975V3/SPEC.md, ANSWER-1 п.3):
    `pin.cmd_pin_update` (AC-1/AC-2) и `doctor.check_canary_trigger`
    (AC-3/AC-4) сравнивают ОДНО и то же число с ОДНИМ и тем же порогом
    `config.CANARY_MAX_MERGES_SINCE_GREEN`, поэтому арифметика возраста
    живёт в одном месте, не дублируется в двух.

    Прогон, чей `main_sha` не предок `target_sha` (чужая, несвязанная
    история — например, тупиковая ветка), не считается вовсе — берётся
    наименьший возраст среди ОСТАЛЬНЫХ. `None` — журнал зелёных прогонов
    пуст, либо ни один из них не лежит на истории `target_sha`
    (вырожденный случай того же порога: «сравнивать не с чем» ⇔ «порог
    всегда достигнут», AC-3 второй сценарий).

    Считаются только прогоны НАБОРА ПО УМОЛЧАНИЮ — это уже решено
    источником (`store.green_canary_runs`, SPEC
    01M3FQ2Z2PY0E9T5F5WQ207NP5, требование 10): пин двигает прогон того
    конвейера, которым пульт работает, а прогон по требованию на моделях
    другого провайдера зелёной канарейкой для сдвига пина не считается.
    """
    best = None
    for row in store.green_canary_runs(conn):
        main_sha = row["main_sha"]
        if not main_sha or not gitcmd.is_ancestor(main_sha, target_sha):
            continue
        age = gitcmd.merges_between(main_sha, target_sha)
        if age is None:
            continue
        if best is None or age < best:
            best = age
    return best


def _step_count(steps) -> int:
    """«Шаги» задачи — число переходов FSM в её журнале, не число
    прогонов агента: устойчиво к подмене `runner.cmd_run` (приёмочная
    песочница `_sandbox.py::SmartAgent` не журналирует "agent run …",
    только реальный `cmd_run` это делает)."""
    return sum(1 for r in steps if r["action"].startswith("state -> "))


def _escalation_notes(steps) -> list:
    return [r["detail"] or "" for r in steps if r["action"] == "state -> escalated"]


def _dev_retry_count(steps) -> int:
    """Число повторов developer на красной планке (требование 5) —
    записи `_DEV_RETRY_ACTION`, журналируемые `_drive_task` ДО каждого
    вызова `runner.cmd_run` этой веткой, не переходы состояния."""
    return sum(1 for r in steps
              if r["actor"] == CANARY_MARK_ACTOR and r["action"] == _DEV_RETRY_ACTION)


def _test_author_visited(steps) -> bool:
    """Прошла ли задача `tests_writing` (требование 3, AC-5): переход
    `state -> tests_writing` в журнале задачи — знак, что роль
    test_author реально её увидела, не была пропущена гейтом SPEC."""
    return any(r["action"] == "state -> tests_writing" for r in steps)


def _task_metrics(conn, task_id: str) -> dict:
    t = store.get_task(conn, task_id)
    steps = store.task_steps(conn, task_id)
    return {
        "steps": _step_count(steps),
        "cost_usd": t["spent_usd"] or 0.0,
        "review_iterations": t["review_iters"],
        "escalations": _escalation_notes(steps),
        "dev_retries": _dev_retry_count(steps),
        "outcome": t["state"],
        "kill_note": (_kill_outcome_note(conn, task_id, steps)
                     if t["state"] == "killed" else None),
        "test_author_visited": _test_author_visited(steps),
        "ceiling_exhausted": _ceiling_exhausted(steps),
        "ceiling_raise": _ceiling_raise_line(steps),
    }


def _deviation_exceeds(current: float, baseline: float, ratio: float) -> bool:
    """|отклонение| текущего значения от бейзлайна превышает `ratio`.

    `baseline == 0` — сравнивать нечего делением: любое ненулевое текущее
    значение считается полным (100%) отклонением, нулевое — нулевым.
    """
    if baseline == 0:
        return current != 0
    return abs(current - baseline) / baseline > ratio


def _task_deviation_warnings(metrics: dict, baseline, ratio: float) -> list:
    """Отклонение МЕТРИК ОДНОЙ задачи от ЕЁ per-task бейзлайна (требование
    9, 12) — та же арифметика, что и v1 `_baseline_warnings`, применённая
    per-task, не к сумме набора."""
    warnings = []
    for key, label, current in (
        ("steps", "шагам", metrics["steps"]),
        ("cost_usd", "стоимости", metrics["cost_usd"]),
    ):
        base = baseline[key] if baseline[key] is not None else 0
        if _deviation_exceeds(current, base, ratio):
            warnings.append(
                f"отклонение по {label} от бейзлайна превышает "
                f"{ratio:.0%}: сейчас {current}, бейзлайн {base}")
    return warnings


# Литерал `action`, которым `auto.cmd_auto` журналирует остановку цикла
# (`orchestrator/auto.py:291`) — та же строка узнаётся выдержкой журнала
# (требование 2, AC-6), без отдельной разделяемой константы: `auto.py` не
# экспортирует её как публичное имя, а дублирование одного литерала
# третьей копией — тот же принцип, что уже есть у `store.
# REFUSAL_ACTION_PREFIX`/`auto.REFUSAL_ACTION_PREFIX`.
_AUTO_STOPPED_ACTION = "auto остановлен"

# Потолок строк выдержки журнала (требование 2, AC-6) — с запасом под
# итоговую строку метрик и строку пути диагностики, которые печатаются
# ниже: суммарный вывод по задаче не должен вылезать за 20 строк
# целиком, не только сама выдержка.
_JOURNAL_EXCERPT_LIMIT = 18


def _journal_excerpt_lines(steps, limit: int = _JOURNAL_EXCERPT_LIMIT) -> list:
    """Выдержка журнала задачи (требование 2, AC-6): переходы состояний
    (`state -> ...`) и записи «переход отклонён»/«auto остановлен» —
    вместо одной итоговой строки исхода. Последние `limit` записей по
    времени — самые информативные для итога прогона (причина
    финального kill журналируется непосредственно перед ним).

    `detail` схлопывается в одну строку (`" ".join(...split())`): текст
    некоторых записей (эскалация от разработчика несёт содержимое
    секции «Эскалация» PLAN.md целиком) содержит переводы строк — без
    схлопывания ОДНА запись журнала печаталась бы НЕСКОЛЬКИМИ
    физическими строками вывода, срывая потолок в 20 строк на задачу
    (требование 2) числом записей, укладывающимся в лимит `limit`."""
    lines = []
    for row in steps:
        action = row["action"]
        if not (action.startswith("state -> ")
               or action.startswith(store.REFUSAL_ACTION_PREFIX)
               or action == _AUTO_STOPPED_ACTION):
            continue
        detail = " ".join((row["detail"] or "").split())
        suffix = f" — {detail}" if detail else ""
        lines.append(f"{row['ts']} {row['actor']}: {action}{suffix}")
    return lines[-limit:]


def _needs_diagnostics(normal_outcome: bool, mismatch: bool) -> bool:
    """ANSWER-1.md, правило 1 (требование 1, AC-1/AC-4): диагностика
    сохраняется во всех случаях, КРОМЕ штатного исхода БЕЗ расхождения
    маркера — единственная комбинация, где сохранять нечего расследовать."""
    return not (normal_outcome and not mismatch)


def _run_verdict(normal_outcome: bool, mismatch: bool,
                 ceiling_exhausted: bool) -> str:
    """Вердикт строки `canary_runs` (01M3HJQV2QV9BXNXSH3F8STAYH,
    требования 10-11): исчерпание уже поднятого потолка — свой вердикт,
    иначе прежняя формула «обратное `_needs_diagnostics`» байт-в-байт.

    Сам факт ОДНОКРАТНОГО подъёма прогон не красит (требование 11): задача,
    прошедшая после подъёма штатно до `merge_gate` без расхождения
    маркера, остаётся `green` — иначе механизм починки красноты сам красил
    бы прогоны, и ни один шаблон, однажды пробивший потолок, больше не мог
    бы разрешить сдвиг пина.
    """
    if ceiling_exhausted:
        return VERDICT_CEILING_EXHAUSTED
    return "green" if not _needs_diagnostics(normal_outcome, mismatch) else "red"


def _diagnostics_dir(outer_root: Path, run_stamp: str, task_id: str) -> Path:
    return outer_root / ".artel" / "canary" / run_stamp / task_id


def _save_diagnostics(outer_root: Path, run_stamp: str, task_id: str,
                      steps) -> Path:
    """Сохраняет диагностику незелёного/расходящегося исхода канареечной
    задачи ДО удаления эфемерного клона (требование 1, AC-1..AC-3):
    журнал задачи (`steps`) текстом, логи ролей клона, последние
    PLAN.md/REVIEW.md из артефактной ветки клона, если они там есть.

    Зовётся ИЗНУТРИ `with _ephemeral_clone()` — `config.LOGS`/`gitcmd.show`
    в этот момент читают клон (`_CLONE_CONFIG_ATTRS` уже подменены), не
    внешний пульт; `outer_root` — путь СНАРУЖИ клона (`config.ROOT` до
    входа в блок), под который складывается результат, чтобы диагностика
    пережила `shutil.rmtree` клона на выходе из блока."""
    diag_dir = _diagnostics_dir(outer_root, run_stamp, task_id)
    diag_dir.mkdir(parents=True, exist_ok=True)

    lines = [f"{r['ts']} {r['actor']}: {r['action']}"
            + (f" — {r['detail']}" if r["detail"] else "")
            for r in steps]
    (diag_dir / "steps.txt").write_text(
        "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    if config.LOGS.is_dir():
        for log_path in sorted(config.LOGS.glob(f"{task_id}-*.log")):
            shutil.copy2(log_path, diag_dir / log_path.name)

    branch = artifact_branch.branch_name(task_id)
    for name in ("PLAN.md", "REVIEW.md"):
        text, _reason = gitcmd.show(branch, f"tasks/{task_id}/{name}")
        if text is not None:
            (diag_dir / name).write_text(text, encoding="utf-8")

    return diag_dir


def _local_full_sha(revision: str) -> str:
    """Полный 40-символьный sha ревизии по ЛОКАЛЬНОЙ базе главной копии
    (`git rev-parse --verify <revision>^{commit}`); пустая строка — ревизия
    локально не разрешается либо git не ответил.

    Зачем отдельная функция при существующей `gitcmd.fetch_ref_sha`: та
    ходит к `origin`, а этой ветке (`--sha` задан явно) обращение к origin
    запрещено (AC-2 задачи 01M2B6K02YVJBWE1JDWP85EJH0). Правки самого
    `orchestrator/gitcmd.py` тут не нужно (SPEC
    01M3GKJFN90ATK2KECNDZXPPP6, требование 7): нужный вызов даёт
    существующая `gitcmd.git`.

    `^{commit}` — чтобы на выходе был sha КОММИТА (аннотированный тег
    развернулся бы в свой объект тега), а `--verify` — чтобы
    неразрешимая ревизия дала ненулевой код, а не эхо самой строки.
    """
    res = gitcmd.git("rev-parse", "--verify", f"{revision}^{{commit}}")
    if res is None or res.returncode != 0:
        return ""
    return res.stdout.strip()


def _resolve_target_sha(explicit_sha: str | None) -> tuple[str, str | None]:
    """(sha, origin_sha) целевого прогона (SPEC 01M2B6K02YVJBWE1JDWP85EJH0,
    требование 1, AC-1/AC-2): `explicit_sha` задан — он и есть целевой
    sha, БЕЗ единого обращения к `origin` (`origin_sha=None` — сравнивать
    с головой `origin/<MAIN_BRANCH>` для пометки происхождения, AC-8,
    после этого нечем, не запрашивать её отдельно ради пометки — именно
    это и запрещает AC-2). Без `--sha` — голова `origin/<config.
    MAIN_BRANCH>` через `gitcmd.fetch_ref_sha`, не `gitcmd.head_sha()`
    главной копии; `origin_sha` в этой ветке — тот же sha (уже известно,
    что целевой sha и есть голова origin, используется `_sha_label`).

    `fetch_ref_sha` не ответил (нет `origin` вовсе, сеть недоступна) —
    деградация на `gitcmd.head_sha()` главной копии, тем же приёмом, что
    и `doctor.check_root_pin`/`check_pin_unpushed` (отсутствие ответа
    origin — это «сверить не с чем», не повод отказывать прогону целиком):
    стенд БЕЗ единого `origin` — легитимный случай (канареечная задача v1/
    v2, `tasks/01M1NEEWH5K1XPFRDGRMPYSBXJ/acceptance_tests/`, гоняла canary
    без единого настроенного origin ДО этой задачи) — сам целевой sha
    прогона в этом вырожденном случае остаётся прежним, но `canary --k <N>`
    не отказывает целиком там, где origin в принципе недостижим.

    Явный `--sha` приводится к ПОЛНОМУ 40-символьному sha (SPEC
    01M3GKJFN90ATK2KECNDZXPPP6, требования 7-8): дальше это значение
    уходит и в `canary_runs.main_sha`, и в сравнения строк (`_sha_label`,
    `pin.cmd_pin_to`), а короткая запись делала их слепыми — пометка «код
    пина» не срабатывала для явного sha пина никогда. Неразрешимая
    ревизия — именованный отказ ЗДЕСЬ: эта функция зовётся до первого
    `_ephemeral_clone` и до `catalog.cmd_new`, так что за опечатку в
    `--sha` Оператор не платит ни клоном, ни заведённой задачей (AC-8)."""
    if explicit_sha is not None:
        full_sha = _local_full_sha(explicit_sha)
        if not full_sha:
            sys.exit(
                f"canary: --sha {explicit_sha} не разрешается в локальной "
                "базе главной копии — проверь опечатку либо подтяни ревизию "
                f"(git rev-parse --verify {explicit_sha})")
        return full_sha, None
    target_sha, _reason = gitcmd.fetch_ref_sha("origin", config.MAIN_BRANCH)
    if not target_sha:
        return gitcmd.head_sha(), None
    return target_sha, target_sha


def _sha_label(target_sha: str, origin_sha: str | None) -> str:
    """Пометка происхождения целевого sha отчёта (требование 4, AC-8):
    «код пина» — целевой sha совпадает с `gitcmd.head_sha()` главной
    копии (проверяется первым — приоритет над «код origin/main», даже
    когда оба совпадения истинны разом, стенд синхронен); «код
    origin/main» — известно (только в ветке без `--sha`, `_resolve_
    target_sha`), что целевой sha и есть голова `origin/<MAIN_BRANCH>`;
    иначе — «код <sha>» буквально, в том числе для явного `--sha`, для
    которого сравнение с origin недоступно (AC-2 запрещает запрос
    origin ради этой пометки).

    Сравниваются ПОЛНЫЕ sha с обеих сторон — `_resolve_target_sha`
    приводит к полному и явный `--sha` (SPEC
    01M3GKJFN90ATK2KECNDZXPPP6, требование 8). До этого короткий `--sha`
    не мог совпасть с 40-символьным `gitcmd.head_sha()` ни при каких
    условиях, и «код пина» для явного sha пина не срабатывала никогда
    (AC-10). Собственного префиксного правила здесь не нужно: обе строки
    приходят полными, и БД эта функция не читает."""
    if target_sha == gitcmd.head_sha():
        return "код пина"
    if origin_sha is not None and target_sha == origin_sha:
        return "код origin/main"
    return f"код {target_sha}"


def _run_task_in_ephemeral_clone(
        template_path: Path, run_stamp: str,
        explicit_target_sha: str | None, outer_root: Path,
        layer_text: str | None = None,
        codex_auth: CodexCloneAuth | None = None) -> tuple:
    """Фаза 1 из 3 (требование 6) `_run_one_task`: заводит и ведёт ОДНУ
    канареечную задачу в собственном эфемерном клоне на checkout'е
    `explicit_target_sha` (требование 1/2), сохраняя диагностику, пока
    клон ещё жив. Возвращает всё, что нужно двум следующим фазам —
    `task_id`, `title`, `expected`, `steps`, `metrics`, `actual`,
    `mismatch`, `normal_outcome`, `diag_dir`.

    `layer_text` (SPEC 01M3FQ2Z2PY0E9T5F5WQ207NP5, требования 4-5) —
    локальный слой клона, собранный из набора ролей; `None` — слой клона
    остаётся шаблоном `models.LOCAL_TEMPLATE`, как его кладёт
    `catalog.cmd_init()` (набор по умолчанию, AC-14).

    `codex_auth` (SPEC 01M3HST1381E1FZCYAN2TSB1F3) — вход Codex для клона
    (указатель связки ключей и проверка входа домом клона); `None` — ни
    одна роль прогона не идёт провайдером Codex.

    Создание задачи и её вождение — с подавленным stdout
    (`redirect_stdout`): между строкой «заведена» (печатается вызывающим
    ПОСЛЕ выхода из этой фазы) и остальным выводом иначе ложится десяток
    строк `store.set_state`/`cleanup.cmd_kill`.
    """
    raw = template_path.read_text(encoding="utf-8")
    title = template_path.stem
    expected = _expected_escalation(raw)

    # Позиционность вызова `_ephemeral_clone` обязана в точности повторять
    # прежнюю (`_ephemeral_clone()`, без аргументов) для обратной
    # совместимости с планкой `01M1SC3Y20YBTTJVQDJBF2NDQW`, зовущей
    # `_run_one_task` тремя позиционными аргументами: та планка мокает саму
    # `_ephemeral_clone` нульарной функцией — вызов с ЛЮБЫМ позиционным
    # аргументом (даже `None`) упал бы `TypeError` на этом моке.
    clone_ctx = (_ephemeral_clone()
                if (explicit_target_sha is None and layer_text is None
                    and codex_auth is None)
                else _ephemeral_clone(explicit_target_sha, layer_text,
                                      codex_auth))
    with clone_ctx:
        conn = store.db()
        with redirect_stdout(io.StringIO()):
            task_id = catalog.cmd_new(title, tz_path=str(template_path),
                                      canary=True)
            # `cmd_new` (A7) не заводит worktree/кодовую ветку задачи —
            # это делает `runner.role_cwd` на первом РЕАЛЬНОМ шаге агента
            # (`workspace.ensure`). Приёмочная песочница подменяет
            # `runner.cmd_run` целиком синтетическим агентом, который сам
            # worktree не заводит (пишет прямо в него), поэтому canary
            # заводит его явно и заранее — идемпотентно, тем же вызовом,
            # каким это сделал бы реальный первый шаг.
            t = store.get_task(conn, task_id)
            _wt_path, wt_error = workspace.ensure(task_id, t["branch"])
            if wt_error is not None:
                raise RuntimeError(
                    f"canary: worktree для {task_id} не создан: {wt_error}")
            _drive_task(conn, task_id)
        steps = store.task_steps(conn, task_id)
        metrics = _task_metrics(conn, task_id)
        actual = bool(metrics["escalations"])
        mismatch = expected is not None and expected != actual
        # «Поделена» (01M29284PTCJXGERV5262E9XMM, требование 4) — штатный
        # исход наравне со «штатно»: родитель, поделённый на подзадачи,
        # не сбой прогона, диагностика ему не нужна.
        normal_outcome = metrics["kill_note"] in ("штатно", "поделена")
        diag_dir = None
        if _needs_diagnostics(normal_outcome, mismatch):
            diag_dir = _save_diagnostics(outer_root, run_stamp, task_id, steps)

    return (task_id, title, expected, steps, metrics, actual, mismatch,
           normal_outcome, diag_dir)


def _record_canary_run(outer_conn, run_stamp: str, title: str, task_id: str,
                       metrics: dict, expected: bool | None, actual: bool,
                       mismatch: bool, normal_outcome: bool,
                       explicit_target_sha: str | None,
                       target_sha: str, sha_label: str | None,
                       plan: CanarySetPlan) -> tuple:
    """Фаза 3 из 3 (требование 6) `_run_one_task`: закрывает целевой sha
    прогона (если он не был передан явно), вычисляет вердикт зелёности и
    пишет строку `canary_runs` СНАРУЖИ клона (требование 5, 9). Возвращает
    финальные `(target_sha, sha_label)` для отчёта.

    `main_sha` записи — целевой sha ЭТОГО прогона (SPEC
    01M2B6K02YVJBWE1JDWP85EJH0, требование 1/4, AC-4), не `gitcmd.
    head_sha()` главной копии (ANSWER-1 01M1NGFK3N6MRMYGCC09H975V3 п.2,
    прежнее поведение до этой задачи) — расходится с ним всегда, когда
    `--sha` явно отличается от пина, и по умолчанию, когда `origin/
    <MAIN_BRANCH>` ушёл вперёд пина. Без явного `target_sha` (см.
    докстринг `_run_one_task` — совместимость со старой планкой) — тот же
    `gitcmd.head_sha()` главной копии, снятый ПОСЛЕ выхода из клона, что и
    до этой задачи, байт-в-байт.

    Имя набора и сводка «роль -> модель» (SPEC
    01M3FQ2Z2PY0E9T5F5WQ207NP5, требование 7) идут в ту же строку: набор
    — файл вне git, и к разбору истории прогонов его текст уже будет
    другим.
    """
    if explicit_target_sha is None:
        target_sha = gitcmd.head_sha()
    if sha_label is None:
        sha_label = _sha_label(target_sha, None)
    main_sha = target_sha
    # Возврат из merge_gate (06.09, п.2): вердикт зелёности выражен через
    # уже смерженное понятие штатного исхода прогона (`normal_outcome`/
    # `_needs_diagnostics`, вычислены фазой 1), не через «дошла до
    # состояния merge_gate/verifying» — `verifying` с ADR-0015 не конечная
    # точка реального вождения вовсе (проходится синтетически,
    # `_pass_verifying`). Третье значение вердикта (исчерпание уже
    # поднятого потолка, 01M3HJQV2QV9BXNXSH3F8STAYH, требование 10) живёт в
    # `_run_verdict` — не «не green», а свой диагноз.
    verdict = _run_verdict(normal_outcome, mismatch,
                           metrics["ceiling_exhausted"])
    store.insert_canary_run(
        outer_conn, run_stamp, title, task_id, metrics["steps"],
        metrics["cost_usd"], metrics["review_iterations"],
        len(metrics["escalations"]), metrics["outcome"],
        "yes" if expected else ("no" if expected is False else None),
        actual, mismatch, main_sha=main_sha, verdict=verdict,
        set_name=plan.name, models_summary=plan.summary or None)
    return target_sha, sha_label


def _baseline_deviation_note(outer_conn, task_id: str, title: str,
                             metrics: dict, normal_outcome: bool,
                             mismatch: bool, ratio: float,
                             set_name: str = config.CANARY_DEFAULT_SET) -> str:
    """Фаза 2 из 3 (требование 6) `_run_one_task`: сверка метрик задачи с
    ЕЁ per-task бейзлайном — заводит бейзлайн, если его ещё нет, либо
    поднимает алерт на отклонение сверх `ratio`. Возвращает готовую
    строку-примечание для итогового отчёта (пустую — если сравнивать не
    положено или отклонений нет).

    Требование 3/AC-7/AC-8: бейзлайн заводится и сравнение отклонений
    применяется ТОЛЬКО для штатного исхода без расхождения маркера —
    прогон, снятый как «не сошлась», или с расхождением, в это сравнение
    не попадает, даже если он первый для шаблона (копилка 06.09:
    killed-прогон дважды за день ложно завёл бейзлайн).

    Бейзлайн читается и пишется по ПАРЕ (шаблон, набор ролей) — SPEC
    01M3FQ2Z2PY0E9T5F5WQ207NP5, требование 7: прогон на другом наборе
    моделей сравнивался бы с бейзлайном прежнего набора (предупреждение
    «отклонение сверх 50%» на ожидаемой разнице моделей, и именно этот
    алерт — вход гейта сдвига пина) и затем переписал бы его своими
    числами.
    """
    if _needs_diagnostics(normal_outcome, mismatch):
        return ""
    baseline = store.canary_baseline(outer_conn, title, set_name)
    if baseline is None:
        store.set_canary_baseline(outer_conn, title, metrics["steps"],
                                  metrics["cost_usd"],
                                  metrics["review_iterations"], set_name)
        return "  [бейзлайн создан]"
    warnings = _task_deviation_warnings(metrics, baseline, ratio)
    if not warnings:
        return ""
    for w in warnings:
        alerts.raise_alert(
            outer_conn, task_id, "threshold", "canary",
            f"канарейка {title} ({task_id}), набор {set_name}: {w}")
    return "  [ВНИМАНИЕ: отклонение от бейзлайна: " + "; ".join(warnings) + "]"


def _run_one_task(template_path: Path, run_stamp: str, ratio: float,
                  target_sha: str | None = None,
                  sha_label: str | None = None,
                  plan: CanarySetPlan | None = None,
                  codex_auth: CodexCloneAuth | None = None) -> None:
    """Полный цикл одной канареечной задачи: заводит, ведёт в собственном
    эфемерном клоне на checkout'е `target_sha` (требование 1/2), пишет
    метрики/бейзлайн в БД пульта СНАРУЖИ клона (требование 5, 9) и
    печатает итог со сноской происхождения `target_sha` (`sha_label`,
    требование 4/AC-8). Разбита на три фазы (требование 6, SPEC
    01M2CN42RV0EBBP7HS4HP2VNY1) — `_run_task_in_ephemeral_clone` (прогон
    в эфемерном клоне), `_record_canary_run` (запись в `canary_runs`),
    `_baseline_deviation_note` (сверка с бейзлайном) — эта функция только
    их вызывает и собирает итоговую печать.

    `target_sha`/`sha_label` необязательны — `cmd_canary` всегда передаёт
    оба, но `tasks/01M1SC3Y20YBTTJVQDJBF2NDQW/acceptance_tests/
    test_canary_report_kill_reason.py` (залоченная планка ДРУГОЙ, уже
    смерженной задачи) зовёт эту функцию тремя позиционными аргументами
    напрямую — правка чужой планки требует отдельного мандата Оператора,
    которого эта задача не получала. Без явного `target_sha` — тот же sha,
    на котором и раньше молча оставался клон без единого checkout
    (`gitcmd.head_sha()` главной копии в момент вызова), с меткой «код
    пина» тем же вычислением, что и у явного вызова с этим же sha.

    «Штатный исход без расхождения» (ANSWER-1.md, вариант Б) — ЕДИНСТВЕННЫЙ
    случай, где диагностика не сохраняется (требование 1, AC-4) и где
    бейзлайн/сравнение отклонений вообще применяются (требование 3,
    AC-7/AC-8): `_kill_outcome_note` отличает штатный kill на
    `merge_gate` (единственный штатный kill РЕАЛЬНОГО вождения —
    `verifying` теперь проходится синтетически, ANSWER-3.md 06.09; см.
    также недостижимую из `_drive_task` `_kill_at_verifying`, оставленную
    ради чужой планки, REVIEW.md итерации 2 R2-F1) от «не сошлась»,
    `mismatch` — расхождение маркера ожидания эскалации с фактом.

    `plan` (SPEC 01M3FQ2Z2PY0E9T5F5WQ207NP5) — план прогона по набору
    ролей: слой клона, ключ бейзлайна, имя набора и сводка моделей в
    строке прогона и в выводе. `None` — набор по умолчанию
    (`_DEFAULT_SET_PLAN`), то есть прежнее поведение байт-в-байт: как для
    `cmd_canary` без `--set`, так и для залоченной планки задачи
    01M1SC3Y20YBTTJVQDJBF2NDQW, зовущей эту функцию тремя позиционными
    аргументами.

    `codex_auth` (SPEC 01M3HST1381E1FZCYAN2TSB1F3) — вход Codex для клона,
    собранный `_codex_clone_auth` ДО клона; `None` — ни одна роль прогона
    не идёт провайдером Codex.
    """
    plan = plan or _DEFAULT_SET_PLAN
    explicit_target_sha = target_sha
    outer_root = config.ROOT

    # `codex_auth` доезжает до фазы 1 ТОЛЬКО когда он есть — тот же довод,
    # что у развилки `clone_ctx` внутри неё: залоченная планка
    # 01M3GKJFN90ATK2KECNDZXPPP6 подменяет фазу 1 фикстурой с пятью
    # параметрами, и шестой аргумент уронил бы её `TypeError` даже значением
    # `None`.
    phase_one_extra = {} if codex_auth is None else {"codex_auth": codex_auth}
    (task_id, title, expected, steps, metrics, actual, mismatch,
     normal_outcome, diag_dir) = _run_task_in_ephemeral_clone(
        template_path, run_stamp, explicit_target_sha, outer_root,
        plan.layer_text, **phase_one_extra)

    print(f"[canary] {task_id} заведена из {template_path.name}")

    outer_conn = store.db()
    target_sha, sha_label = _record_canary_run(
        outer_conn, run_stamp, title, task_id, metrics, expected, actual,
        mismatch, normal_outcome, explicit_target_sha, target_sha, sha_label,
        plan)

    note = _baseline_deviation_note(outer_conn, task_id, title, metrics,
                                    normal_outcome, mismatch, ratio, plan.name)

    mismatch_note = ""
    if mismatch:
        mismatch_note = (
            "  [РАСХОЖДЕНИЕ: маркер ожидал "
            f"{'эскалацию' if expected else 'без эскалации'}, по факту "
            f"{'эскалация была' if actual else 'эскалации не было'}]")

    outcome_note = f" ({metrics['kill_note']})" if metrics["kill_note"] else ""
    test_author_note = "да" if metrics["test_author_visited"] else "нет"
    for line in _journal_excerpt_lines(steps):
        print(f"  {line}")
    # Требование 11 (01M3HJQV2QV9BXNXSH3F8STAYH): факт подъёма потолка — в
    # отчёт прогона, не только в журнал задачи. Журнал остаётся в БД
    # эфемерного клона и умирает вместе с ним; выдержка `_journal_excerpt_
    # lines` эту запись не несёт (она не переход состояния).
    if metrics["ceiling_raise"] is not None:
        print(f"  {metrics['ceiling_raise']}")
    print(f"  {task_id}: шагов={metrics['steps']}  "
         f"${metrics['cost_usd']:.2f}  "
         f"ревью-итераций={metrics['review_iterations']}  "
         f"эскалаций={len(metrics['escalations'])}  "
         f"повторов developer={metrics['dev_retries']}  "
         f"исход={metrics['outcome']}{outcome_note}  "
         f"sha={target_sha} ({sha_label})  "
         f"набор={plan.name}{_summary_note(plan)}  "
         f"test_author={test_author_note}{mismatch_note}{note}")
    if diag_dir is not None:
        print(f"  диагностика: {diag_dir}")


def _summary_note(plan: CanarySetPlan) -> str:
    """Сводка моделей набора в скобках — пусто у набора по умолчанию:
    модели там те же, что у живого конвейера, и называть их отдельно
    нечего."""
    return f" ({plan.summary})" if plan.summary else ""


def cmd_canary(*, k: int, sha: str | None = None,
               set_name: str = config.CANARY_DEFAULT_SET,
               templates: list | None = None) -> None:
    """`set_name` (SPEC 01M3FQ2Z2PY0E9T5F5WQ207NP5, требование 1) — имя
    набора ролей прогона из `canary_sets:` локального слоя; значение по
    умолчанию — набор по умолчанию, то есть прогон «как пульт».

    `templates` (01M3HJQV2QV9BXNXSH3F8STAYH, требования 1-4) — стабильные
    имена шаблонов пула (имя файла без `.md`) в порядке прогона: прогон
    берёт из пула ровно их, без случайной выборки. `None` (по умолчанию) —
    выбор прежний, случайная выборка `k` шаблонов из пула, байт-в-байт как
    до этой задачи: развилка ровно одна и стоит здесь, прежняя ветка не
    переписана."""
    pool_dir = _pool_dir()
    if not pool_dir.is_dir():
        sys.exit(f"canary: каталог пула не найден: {pool_dir}")
    if k <= 0:
        sys.exit("canary: --k должен быть положительным целым числом")
    templates = (_sample_pool_templates(pool_dir, k) if templates is None
                else _named_pool_templates(pool_dir, k, templates))
    # Набор разбирается и проверяется ЗДЕСЬ — до `_resolve_target_sha` (он
    # ходит к origin) и до первого `_ephemeral_clone` (требование 6): за
    # битый набор Оператор не платит ни обращением к сети, ни `git clone`,
    # ни заведённой задачей.
    plan = _set_plan(set_name)
    # Вход Codex для клона — здесь же, на той же стадии (SPEC
    # 01M3HST1381E1FZCYAN2TSB1F3, требование 3): за несделанный однократный
    # шаг Оператора пульт тоже не платит ни сетью, ни `git clone`, ни
    # заведённой задачей. `None` — ни одна роль прогона не идёт провайдером
    # Codex, и дальше всё идёт байт-в-байт как до этой задачи.
    codex_auth = _codex_clone_auth(plan)

    target_sha, origin_sha = _resolve_target_sha(sha)
    sha_label = _sha_label(target_sha, origin_sha)

    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # Требование 5: имена выбранных шаблонов в порядке прогона — в САМОЙ
    # первой строке вывода, до первого эфемерного клона. Иначе состав
    # прогона Оператор узнавал бы по мере того, как задачи одна за другой
    # доходят до конца, то есть через десятки минут, а при падении первого
    # же клона — не узнал бы вовсе.
    print(f"[canary] прогон {run_stamp}: {len(templates)} задач из пула "
         f"{pool_dir} в порядке прогона: "
         f"{', '.join(p.stem for p in templates)}; целевой sha {target_sha} "
         f"({sha_label}), набор {plan.name}{_summary_note(plan)}")
    for template_path in templates:
        _run_one_task(template_path, run_stamp, config.CANARY_DEVIATION_RATIO,
                      target_sha, sha_label, plan, codex_auth)
    print(f"[canary] прогон {run_stamp} завершён")
