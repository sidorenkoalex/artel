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
прогон (инцидент 12.09, SPEC/«Контекст»). Подпись кода в строке итога
задачи — «код клона <sha>», коммит, сообщённый процессом клона (SPEC
01M3PYMQ6N4SCAJ9WWTTKH6XNG, требование 4): после этапа 0 ADR-0021 задачу
ведёт код клона, и прежняя пометка «код пина» (`_sha_label`, её зовут
залоченные планки других задач) вводила в заблуждение — в выводе
прогона она больше не печатается.

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
переадресован сюда `_CLONE_CONFIG_ATTRS`: модель — записью `role_models:`
ровно для роли набора, провайдер — записью `role_providers:`, которую
читает `orchestrator/roles.py::provider`. `roles.yaml` при этом не
меняется ни в клоне, ни в главной копии: путь защищённый, и прогон
канарейки не вправе переводить роль пульта на другого исполнителя.
Бейзлайн и строки прогонов ключуются ПАРОЙ (шаблон, набор): прогон на
другом наборе моделей иначе сравнивался бы с бейзлайном прежнего набора и
переписывал бы его. Без `--set` действует набор по умолчанию
(`config.CANARY_DEFAULT_SET`), без единого чтения `canary_sets:`.

Слой клона — боевой (SPEC 01M3PYMQ6N4SCAJ9WWTTKH6XNG): и прогон без
набора, и прогон с набором собирают его из слоя ПУЛЬТА — ярусы,
разрешения `experimental`, тарифы, `role_providers:`, `role_models:`;
набор ложится поверх записями своих ролей. До этой задачи клон шёл на
шаблоне `models.LOCAL_TEMPLATE`, и канарейка для сдвига пина проверяла
не те модели, на которых работает пульт. Шаблон остаётся только
запасным ходом для нечитаемого слоя пульта — и сводка прогона называет
это прямо.

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

Ведение учебной задачи — кодом ПРОВЕРЯЕМОГО коммита, не кодом пина (SPEC
01M3PKSWPETC49WFTFZ69GH3F2; ADR-0021, этап 0; ADR-0019 п.2): задачу
заводит и ведёт отдельный процесс интерпретатора из эфемерного клона
(`orchestrator/canary_drive.py`, рабочий каталог — клон), а пульт читает
его результат — один JSON-объект в файле — и сам ни одного перехода,
чекпоинта или шага роли учебной задачи не исполняет. Помощники ведения
(`_drive_task`, `_pass_*`, `_kill_*`, подъём потолка) живут в этом модуле
по-прежнему, но исполняются только процессом клона — его собственной
копией модуля. За пультом остаются выбор шаблонов и набора, клон и
origin-заглушка, слой моделей и вход Codex клона, диагностика, строка
`canary_runs`, базовая линия, вердикт и сводка. Строка прогона несёт
коммит, чьим кодом велась задача (HEAD клона, сообщённый процессом); его
расхождение с проверяемым коммитом красит прогон. Коммит без входа
`canary_drive.py` — именованный отказ до заведения задачи: вести её кодом
пина канарейка больше не умеет намеренно.

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
import fcntl
import importlib
import json
import os
import queue
import random
import re
import signal
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from collections import namedtuple
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from pathlib import Path

from scripts import guard

from . import (alerts, answer, artifact_branch, artifact_source, artifacts,
              auto, budget, catalog, cleanup, config, fsm, gitcmd, liveness,
              models, roles, runner, store, workspace, yamlmini)
from .advance_gates import spec_audit
from .pool_seal import _pool_dir
from .providers import codex as codex_provider
from .reference_cache import SHA_FORM

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

#: Вход ведения учебной задачи кодом клона (SPEC 01M3PKSWPETC49WFTFZ69GH3F2,
#: требование 1): файл в дереве проверяемого коммита и имя модуля, которым
#: его запускает интерпретатор с рабочим каталогом — клоном. Именно запуск
#: модулем (`-m`), а не путём к файлу: так первым в `sys.path` процесса
#: стоит клон, и пакет `orchestrator` приходит оттуда же, откуда вход.
CANARY_DRIVE_ENTRY = Path("orchestrator/canary_drive.py")
CANARY_DRIVE_MODULE = "orchestrator.canary_drive"

#: Предельное время процесса клона на одну учебную задачу (требование 7):
#: по истечении процесс снимается вместе со своей группой (шаги ролей —
#: его потомки), прогон красный. Задача проходит четыре роли, у каждой
#: шаг до `config.AGENT_TIMEOUT_SEC` на попытку, плюс повторы developer,
#: возвраты из эскалации и ревью-итерации — восемь часов с запасом
#: покрывают честное ведение и всё же конечны: без предела зависший
#: процесс держал бы пульт вечно.
CANARY_DRIVE_TIMEOUT_SEC = 8 * 60 * 60

# Файлы обмена с процессом клона — внутри `.artel/` клона: живут и умирают
# вместе с ним, а нужное пульту он забирает до уборки клона.
_DRIVE_RESULT_NAME = "canary-drive-result.json"
_DRIVE_LOG_NAME = "canary-drive.log"

# Исход строки `canary_runs` прогона, чей процесс клона не дал результата
# (требование 7): FSM-состояния задачи пульт в этом случае не знает.
_DRIVE_FAILED_OUTCOME = "drive_failed"

# Поля метрик результата, которые читают фазы 2-3 и печать сводки
# `_run_one_task`: без любого из них результат неразборчив.
_DRIVE_METRIC_FIELDS = (
    "steps", "cost_usd", "review_iterations", "escalations", "dev_retries",
    "outcome", "kill_note", "test_author_visited", "ceiling_exhausted",
    "ceiling_raise",
)


class CanaryDriveFailed(Exception):
    """Процесс клона не довёл учебную задачу до результата (требование 7):
    отказал, упал, не записал разборчивый результат или снят по времени.
    Несёт то, что нужно пульту для красной строки прогона и сводки, —
    диагностика к этому моменту уже сохранена."""

    def __init__(self, title: str, expected: bool | None, reason: str,
                 diag_dir: Path, task_id: str | None = None):
        super().__init__(reason)
        self.title = title
        self.expected = expected
        self.reason = reason
        self.diag_dir = diag_dir
        self.task_id = task_id

# Origin эфемерного клона (требование 2, AC-2) — заглушка ЯВНО, не то,
# что `git clone` подставил бы сам (локальный путь до `config.ROOT`,
# формально не http(s), но реально дотягивающийся до главного пульта):
# отправка ссылки документов (`artifact_branch.commit_files`, best-effort)
# с таким origin смогла бы по-настоящему запушить документы канареечной
# задачи в главный пульт —
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

# Четыре утверждения синтетического ответа на эскалацию (SPEC
# 01M3MHBNMT1VDXSRQNV1GX30BV, требования 4 и 6) — именованными
# константами, а не литералами внутри текста: утверждение существует в
# ОДНОМ экземпляре, и тест адресует его именем, а не своей копией фразы.
# Прежний текст назвал номер задачи, которая ввела механизм, и «вариант
# A» — роль читала его как ответ по ЧУЖОЙ задаче на развилку, которой в
# её вопросах не было (прогоны 20260928T165337Z и 20260928T162501Z:
# аналитик четырежды повторил тот же вопрос и был снят предохранителем).
_SYNTHETIC_ANSWER_NO_OPERATOR = "Оператора в этом прогоне нет"
_SYNTHETIC_ANSWER_ROLE_DECIDES = (
    "решение по вопросу принимаешь ты — в пределах ТЗ и SPEC задачи")
_SYNTHETIC_ANSWER_WRITE_ASSUMPTION = (
    "запиши выбранное толкование допущением в свой артефакт")
_SYNTHETIC_ANSWER_SAME_ANSWER_AGAIN = (
    "повторная эскалация по тому же вопросу получит этот же ответ")

# Текст ответа — ОДИН на все роли и на все эскалации прогона (требование
# 6): ни номера задачи (ни чужой, ни своей — роль знает свою из брифа
# шага), ни имени роли, ни ссылки на вариант ответа. Адрес допущения —
# «## Риски» с оговоркой: этот раздел несёт только `templates/PLAN.md`, а
# `templates/` — защищённый путь, поэтому раздела, которого нет ни в
# одном шаблоне, текст требовать не вправе (требование 5).
_SYNTHETIC_ANSWER_TEXT = (
    f"{_SYNTHETIC_ANSWER_NO_OPERATOR}: это синтетический прогон "
    f"конвейера, отвечать на эскалацию некому, поэтому "
    f"{_SYNTHETIC_ANSWER_ROLE_DECIDES}. Из возможных прочтений выбери "
    f"наименее рискованное и {_SYNTHETIC_ANSWER_WRITE_ASSUMPTION}: в "
    f"раздел «## Риски», а если шаблон твоего артефакта такого раздела "
    f"не несёт — в его содержательный раздел. Продолжай работу с этим "
    f"допущением: {_SYNTHETIC_ANSWER_SAME_ANSWER_AGAIN}, другого не "
    f"будет.\n")


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
CodexCloneAuth = namedtuple("CodexCloneAuth", "role pointer profile",
                            defaults=(None,))


def _canary_profile_home() -> Path:
    """Постоянный дом только канарейки, вне пульта и временных клонов."""
    return Path.home() / ".artel-canary-codex"


@contextmanager
def _locked_canary_profile():
    """Один прогон владеет профилем до завершения всех своих задач."""
    home = _canary_profile_home()
    if home.is_symlink():
        sys.exit(f"canary: профиль Codex канарейки — ссылка: {home}")
    try:
        home.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as exc:
        sys.exit(f"canary: профиль Codex канарейки не создан: {home}: {exc}")
    lock_path = home / ".lock"
    if lock_path.is_symlink():
        sys.exit(f"canary: замок профиля Codex канарейки — ссылка: {lock_path}")
    with lock_path.open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            sys.exit(f"canary: профиль Codex канарейки занят: {home}")
        try:
            yield home
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _canary_profile_auth(plan, home: Path) -> CodexCloneAuth | None:
    """Подготовить адрес отдельного входа, не обращаясь к токенам."""
    if not plan.codex_roles:
        return None
    pointer = home / _KEYCHAIN_POINTER_REL
    if not pointer.is_file():
        # Старый указатель совместим с отдельной записью входа: он задаёт
        # только связку ключей, а сама запись Codex привязана к CODEX_HOME.
        pointer = config.ROLE_HOME / _KEYCHAIN_POINTER_REL
    try:
        payload = pointer.read_bytes()
    except OSError as exc:
        sys.exit(f"canary: профиль Codex канарейки для "
                 f"{', '.join(plan.codex_roles)} (роли набора на "
                 f"{codex_provider.CLI_NAME}) не подготовлен: "
                 f"указатель связки ключей {pointer} недоступен ({exc}). "
                 f"Оператору нужен отдельный вход `codex login` для "
                 f"CODEX_HOME={home / '.codex'}")
    return CodexCloneAuth(plan.codex_roles[0], payload, home / ".codex")


def _restore_canary_profile(profile: Path, curated: Path) -> None:
    """Вернуть курируемые файлы проверяемого SHA, забыв историю и доверие.

    `curated` — референс дома Codex в дереве клона, то есть ровно файлы
    коммита: `.artel/` в git не хранится. Коммит без референса курируемых
    настроек не несёт — профиль тогда только очищается.
    """
    if curated.is_symlink() or (curated.exists() and not curated.is_dir()):
        sys.exit(f"canary: курируемый дом Codex проверяемого SHA — не "
                 f"каталог: {curated}")
    if profile.is_symlink():
        sys.exit(f"canary: профиль Codex канарейки — ссылка: {profile}")
    sources = tuple(curated.iterdir()) if curated.is_dir() else ()
    allowed = {"config.toml", "AGENTS.md", ".zshenv"}
    if sources and not (curated / "config.toml").is_file():
        sys.exit(f"canary: нет config.toml проверяемого SHA: {curated}")
    for source in sources:
        if source.name not in allowed or source.is_symlink() or not source.is_file():
            sys.exit(f"canary: неожиданный файл в курируемом доме Codex: {source}")
    profile.mkdir(mode=0o700, parents=True, exist_ok=True)
    if (profile / "auth.json").exists():
        sys.exit(f"canary: в профиле {profile} найден auth.json; "
                 "вход должен храниться в keyring, содержимое не читается")
    for item in profile.iterdir():
        if item.is_dir() and not item.is_symlink():
            shutil.rmtree(item)
        else:
            item.unlink()
    for source in sources:
        shutil.copy2(source, profile / source.name)

#: План прогона (SPEC 01M3FQ2Z2PY0E9T5F5WQ207NP5; SPEC
#: 01M3PYMQ6N4SCAJ9WWTTKH6XNG): `name` — имя набора (им ключуются бейзлайн
#: и строка прогона), `entries` — записи набора «роль ->
#: `models.CanarySetRole`» (пусто у набора по умолчанию), `layer_text` —
#: готовый текст локального слоя эфемерного клона (`None` — слой клона
#: остаётся шаблоном, который кладёт `catalog.cmd_init()`: слой пульта не
#: прочитан, а набора нет), `summary` — сводка «роль → модель» КАЖДОЙ
#: агентской роли прогона с источником слоя клона, `codex_roles` — роли
#: прогона, идущие в слое клона провайдером Codex (SPEC
#: 01M3HST1381E1FZCYAN2TSB1F3, требование 2), отсортированные по алфавиту;
#: пустой кортеж — переноса указателя и проверки входа не будет вовсе.
CanarySetPlan = namedtuple("CanarySetPlan",
                           "name entries layer_text summary codex_roles")

#: План для вызывающих `_run_one_task` БЕЗ плана — залоченная планка
#: задачи 01M1SC3Y20YBTTJVQDJBF2NDQW зовёт её тремя позиционными
#: аргументами: слой клона — шаблон, сводки нет, базовая линия
#: сравнивается прежним способом. `cmd_canary` этот план не берёт: набор
#: по умолчанию он собирает `_set_plan` из слоя пульта.
_DEFAULT_SET_PLAN = CanarySetPlan(config.CANARY_DEFAULT_SET, {}, None, "", ())

#: Источники слоя клона в сводке прогона (SPEC 01M3PYMQ6N4SCAJ9WWTTKH6XNG,
#: требование 4) и разделитель, отделяющий источник от моделей ролей:
#: базовая линия (требование 5) сверяет только модели — прогон на тех же
#: моделях сравним, откуда бы слой клона ни пришёл.
_SOURCE_PULT = "слой пульта"
_SOURCE_TEMPLATE = "шаблон"
_SUMMARY_SOURCE_SEP = "; источник: "


def _set_plan(set_name: str) -> CanarySetPlan:
    """План прогона по набору `set_name` — либо ИМЕНОВАННЫЙ ОТКАЗ
    (требование 6): каждый случай битого набора обязан остановить команду
    ДО эфемерного клона, то есть до `git clone` и до строки в `tasks` —
    иначе за опечатку в имени набора Оператор платит клоном и заведённой
    задачей, а причина умирает вместе с уничтоженным клоном.

    Слой клона собирается из слоя ПУЛЬТА и для набора по умолчанию (SPEC
    01M3PYMQ6N4SCAJ9WWTTKH6XNG, требование 1): канарейка для сдвига пина
    обязана проверять те модели, на которых пульт работает. Набор по
    умолчанию при этом в `canary_sets:` не заглядывает, а нечитаемый слой
    пульта (или каталог) его не останавливает: слой клона остаётся
    шаблоном, и сводка называет это прямо. Набор ложится поверх слоя
    пульта записями `role_models:`/`role_providers:` ровно своих ролей
    (требование 3).
    """
    entries, catalog_data = {}, None
    if set_name == config.CANARY_DEFAULT_SET:
        try:
            catalog_data = models.load_catalog()
        except models.ModelsError:
            # Разрешение ролей для сводки прочитает каталог само и назовёт
            # роли неразрешёнными; шаг роли клона откажет своей причиной.
            catalog_data = None
    else:
        entries = _set_entries_or_exit(set_name)
        try:
            catalog_data = models.load_catalog()
        except models.ModelsError as exc:
            sys.exit(f"canary: каталог моделей не разобран: {exc}")
        _check_set_entries_or_exit(set_name, entries, catalog_data)

    try:
        pult, pult_problem = models.load_local(), None
    except models.ModelsError as exc:
        pult, pult_problem = None, str(exc)
    source = _layer_source(set_name, entries, pult_problem)
    if pult is None and not entries:
        clone, layer_text = models.local_template_layer(), None
    else:
        clone = _clone_layer(pult, entries, catalog_data)
        layer_text = _clone_local_layer_text(source, clone)

    agent_roles, roles_problem = _agent_roles()
    if roles_problem is not None and entries:
        # Без карты исполнителей роли набора не сверить с ролями прогона —
        # тот же отказ до клона, что и у роли набора вне карты.
        sys.exit(f"canary: карта исполнителей не прочитана: {roles_problem}")
    in_clone = _roles_in_clone(agent_roles, clone, catalog_data)
    return CanarySetPlan(
        set_name, entries, layer_text,
        _plan_summary(in_clone, source, roles_problem),
        tuple(sorted(role for role, pair in in_clone.items()
                     if pair is not None
                     and pair[1] == codex_provider.CLI_NAME)))


def _set_entries_or_exit(set_name: str) -> dict:
    """Записи набора `set_name` из `canary_sets:` слоя пульта — либо
    именованный отказ: слой не прочитан или набора в нём нет."""
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
    return entries


def _check_set_entries_or_exit(set_name: str, entries: dict,
                               catalog_data) -> None:
    """Проверки записей набора (требование 6, б/в/д SPEC
    01M3FQ2Z2PY0E9T5F5WQ207NP5) — `sys.exit` с названной сущностью, из-за
    которой набор битый: без имени роли/модели Оператор не знает, какую
    строку набора править.

    Отказа «набор даёт ярусу две разные модели» больше нет (SPEC
    01M3PYMQ6N4SCAJ9WWTTKH6XNG, требование 3): слой клона ключует набор
    ролью, а не ярусом, и две роли одного яруса на разных моделях в нём
    выразимы.
    """
    for role, entry in entries.items():
        try:
            roles.model_tier(role)
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


def _layer_source(set_name: str, entries: dict, pult_problem) -> str:
    """Источник слоя клона для сводки (требование 4): «слой пульта»,
    «набор <имя>» или «шаблон» — с причиной, если слой пульта не прочитан.
    Прогон на шаблоне Оператор иначе принял бы за прогон на боевых
    моделях."""
    unread = f"слой пульта не прочитан: {pult_problem}"
    if entries:
        if pult_problem is not None:
            return f"набор {set_name} поверх шаблона — {unread}"
        return f"набор {set_name}"
    if pult_problem is not None:
        return f"{_SOURCE_TEMPLATE} — {unread}"
    return _SOURCE_PULT


def _clone_layer(pult, entries: dict, catalog_data) -> models.LocalLayer:
    """Слой клона разобранным: основа — слой пульта (нечитаем — шаблон),
    поверх — записи набора (требования 1, 3).

    Ярусы — ярусы основы при любом наборе: набор переводит только свои
    роли, записями `role_models:`/`role_providers:`. Разрешения
    `experimental` и тарифы основы переносятся для моделей, на которые
    слой клона ссылается, — не все подряд: чужое для прогона разрешение
    или тариф в слое клона ничего не значили бы, а читались бы как часть
    прогона. Модель набора со статусом `experimental` разрешается сама,
    как до задачи: набор — явный выбор Оператора на этот прогон.

    `canary_sets:` в слой клона не попадает: его несёт документ слоя, а
    не `LocalLayer`.
    """
    base = pult or models.local_template_layer()
    role_models = dict(base.role_models)
    role_providers = dict(base.role_providers)
    for role, entry in entries.items():
        role_models[role] = entry.model
        role_providers[role] = entry.provider
    used = set(base.tiers.values()) | set(role_models.values())
    allowed = {model_id for model_id in used
               if model_id in base.allow_experimental}
    allowed |= {entry.model for entry in entries.values()
                if catalog_data.models[entry.model].status
                == models.STATUS_EXPERIMENTAL}
    overrides = {model_id: override
                 for model_id, override in base.overrides.items()
                 if model_id in used}
    return models.LocalLayer(dict(base.tiers), overrides, allowed,
                             role_providers, role_models)


def _agent_roles() -> tuple:
    """(агентские роли карты исполнителей в её порядке, причина либо
    `None`) — роли, которые называет сводка прогона."""
    try:
        entries = roles.load()
    except roles.RolesError as exc:
        return [], str(exc)
    return [role for role, entry in entries.items()
            if isinstance(entry, dict) and entry.get("executor") == "agent"], None


def _roles_in_clone(agent_roles: list, clone, catalog_data) -> dict:
    """{роль -> (модель, провайдер) либо `None`} — чем пойдёт каждая
    агентская роль в слое клона. Разрешение — тем же
    `models.resolve_role`, которым пойдёт шаг роли в клоне, а не своей
    копией цепочки.

    Провайдер — запись `role_providers:` слоя клона, иначе провайдер
    разрешения: так же его выбирает `roles.provider` шага. Роль, которая
    не разрешается, — `None`: прогон это не останавливает, шаг этой роли
    в клоне откажет своей названной причиной, а сводка назовёт роль
    неразрешённой.
    """
    in_clone = {}
    for role in agent_roles:
        try:
            resolved = models.resolve_role(role, catalog_data, clone)
        except models.ModelsError:
            in_clone[role] = None
            continue
        in_clone[role] = (resolved.model,
                          clone.role_providers.get(role) or resolved.provider)
    return in_clone


def _plan_summary(in_clone: dict, source: str, roles_problem) -> str:
    """Сводка прогона (требование 4): «<роль> → <модель>» каждой агентской
    роли и источник слоя клона. Слой пульта и набор живут в файле вне git
    — по их сегодняшнему тексту прошлый прогон не восстановить, поэтому
    модели называются все, а не только переведённые набором."""
    if roles_problem is not None:
        named = f"карта исполнителей не прочитана ({roles_problem})"
    else:
        named = ", ".join(
            f"{role} → {pair[0] if pair is not None else 'не разрешена'}"
            for role, pair in in_clone.items())
    return f"{named}{_SUMMARY_SOURCE_SEP}{source}"


def _summary_models(summary: str | None) -> str | None:
    """Модели ролей из сводки прогона — без источника (требование 5).
    Сводка без разделителя (строка, записанная до этой задачи, называла
    только роли набора) возвращается целиком и с новой не совпадёт — это
    и нужно: сводки моделей ВСЕХ ролей у неё нет."""
    if not summary:
        return None
    return summary.split(_SUMMARY_SOURCE_SEP, 1)[0]


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


def _clone_local_layer_text(source: str, layer) -> str:
    """Текст локального слоя ЭФЕМЕРНОГО КЛОНА из разобранного слоя
    `_clone_layer` (SPEC 01M3PYMQ6N4SCAJ9WWTTKH6XNG, требования 1, 3):
    ярусы, разрешения `experimental`, тарифы, `role_providers:`,
    `role_models:`.

    Тариф снимается с локального слоя ПУЛЬТА ДО клона: стоимость шага в
    клоне обязана считаться по тарифу этого пульта, а не по прейскуранту
    каталога — иначе метрика стоимости прогона разошлась бы с тарифом, на
    который её же и сравнивают с бейзлайном.
    """
    lines = [
        "# Локальный слой ЭФЕМЕРНОГО КЛОНА канарейки — собран прогоном",
        "# (SPEC 01M3PYMQ6N4SCAJ9WWTTKH6XNG), источник: "
        + " ".join(source.split()) + ".",
        "# Живёт и умирает вместе с клоном: ни одна роль пульта не",
        "# переведена, roles.yaml ни здесь, ни в главной копии не тронут.",
        "",
        f"{models.TIERS_KEY}:",
    ]
    lines += [f"  {tier}: {_scalar_text(layer.tiers[tier])}"
              for tier in models.TIERS if tier in layer.tiers]

    if layer.allow_experimental:
        lines += ["", f"{models.ALLOW_EXPERIMENTAL_KEY}:"]
        lines += [f"  {model_id}: true"
                  for model_id in sorted(layer.allow_experimental)]

    if layer.overrides:
        lines += ["", f"{models.OVERRIDES_KEY}:"]
        for model_id in sorted(layer.overrides):
            override = layer.overrides[model_id]
            lines.append(f"  {model_id}:")
            lines += [f"    {kind}: {price!r}" for kind, price
                      in zip(models.PRICE_KINDS, override.tariff)]
            lines.append(f"    {models.CALIBRATED_AT_KEY}: "
                         f"{_scalar_text(override.calibrated_at)}")
            lines.append(f"    {models.SOURCE_KEY}: "
                         f"{_scalar_text(override.source)}")

    for key, mapping in ((models.ROLE_PROVIDERS_KEY, layer.role_providers),
                         (models.ROLE_MODELS_KEY, layer.role_models)):
        if mapping:
            lines += ["", f"{key}:"]
            lines += [f"  {role}: {_scalar_text(mapping[role])}"
                      for role in sorted(mapping)]
    return "\n".join(lines) + "\n"


def _codex_clone_auth(plan: CanarySetPlan) -> CodexCloneAuth | None:
    """Вход Codex для эфемерного клона — либо ИМЕНОВАННЫЙ ОТКАЗ (SPEC
    01M3HST1381E1FZCYAN2TSB1F3, требование 3). Прежняя форма входа через
    боевой дом пульта: штатный `cmd_canary` её больше не зовёт (SPEC
    01M3V4ZPB6HFDJ36MTDAQG5VNT — `_locked_canary_profile` и
    `_canary_profile_auth`), оставлена для формы `codex_auth` без
    профиля. `None` — ни одна роль
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

    Половин у подготовки ДВЕ, и отказ называет обе: окружения двух вызовов
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
                 f"одна из двух половин подготовки входа в клон — "
                 f"{codex_provider.HOME_ENV} развёрнутого дома клона "
                 f"(`canary._ephemeral_clone` снимает переопределение, "
                 f"`CodexProvider.environment` отдаёт; шагу клона отдано "
                 f"{codex_provider.HOME_ENV}="
                 f"{config.ROLE_HOME / codex_provider.DEPLOYED_HOME_DIR}) "
                 f"и/или указатель связки ключей "
                 f"(`canary._install_codex_pointer` кладёт его в "
                 f"{config.ROLE_HOME / _KEYCHAIN_POINTER_REL}) — до "
                 f"починки прогон на наборе с ролями "
                 f"{codex_provider.CLI_NAME} невозможен.")
    sys.exit(f"canary: вход Codex не подтверждён ни окружением шага "
             f"эфемерного клона, ни домом роли пульта — шаг роли упал бы "
             f"авторизацией за деньги. {check.name}: {check.detail}")


def _refuse_unless_profile_logged_in(role: str, pult_role_home: Path,
                                     profile: Path) -> None:
    """Проверяет вход отдельного профиля канарейки окружением шага КЛОНА
    и отказывает до платного шага (SPEC 01M3V4ZPB6HFDJ36MTDAQG5VNT, AC-5).

    Те же два адресата, что у `_refuse_unless_clone_logged_in`, но
    сравнение идёт с ТЕМ ЖЕ `CODEX_HOME` профиля, а не с боевым каталогом
    пульта: вход боевого дома ничего не говорит о входе профиля (AC-10).
    Профиль подтверждён окружением пульта, а клоном нет — расходятся
    только `HOME`/`ZDOTDIR` клона и скопированный в него указатель связки
    ключей, то есть сломана подготовка клона: дефект пульта, повторный
    `codex login` его не чинит.
    """
    from . import doctor
    check = doctor.check_codex_chatgpt_auth(role)
    if check.status == "ok":
        return
    if _pult_home_login_confirmed(role, pult_role_home, profile):
        sys.exit(f"canary: вход Codex в отдельный профиль {profile} "
                 f"окружением пульта подтверждён, а проверка {check.name} "
                 f"окружением шага эфемерного клона — нет. Это дефект "
                 f"пульта, а не несделанный шаг Оператора: повторный вход "
                 f"этого не изменит. Сломана подготовка дома клона — "
                 f"`HOME`/`ZDOTDIR` клона {config.ROLE_HOME} и/или "
                 f"указатель связки ключей (`canary._install_codex_pointer` "
                 f"кладёт его в {config.ROLE_HOME / _KEYCHAIN_POINTER_REL}) "
                 f"— до починки прогон на наборе с ролями "
                 f"{codex_provider.CLI_NAME} невозможен.")
    sys.exit(f"canary: вход Codex в отдельный профиль {profile} не "
             f"подтверждён до платного шага: {check.name}: {check.detail}. "
             f"Оператору нужен `codex login` с этим CODEX_HOME")


def _pult_home_login_confirmed(role: str, pult_role_home: Path,
                               codex_home: Path | None = None) -> bool:
    """Подтверждён ли вход Codex домом роли ПУЛЬТА — тем же узлом
    `doctor`, но с окружением, которое собралось бы вне блока клона
    (SPEC 01M3M55070T5NJFYM3QQJH4B9V, требование 6).

    Снимается переадресация `config.ROLE_HOME`, а переопределение
    `CODEX_HOME` ставится в `codex_home`: `None` — боевой каталог дома
    роли пульта, путь — отдельный профиль канарейки, тот же, что у
    проверки клона. Узел берёт все три имени у
    `CodexProvider.environment`, и ответ обязан относиться к тому дому,
    каким входил Оператор, а не к гибриду. Оба восстановления — в
    `finally`: вызывающий на обеих ветках уходит `sys.exit`, а внешний
    `finally` блока клона до этого ещё не добрался, и оставленные
    пультовские пути увели бы уборку клона не туда.
    """
    from . import doctor
    saved_role_home = config.ROLE_HOME
    saved_override = codex_provider.set_codex_home_override(codex_home)
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
    готовый текст локального слоя КЛОНА, собранный из слоя пульта и
    набора ролей (`_clone_local_layer_text`, SPEC
    01M3PYMQ6N4SCAJ9WWTTKH6XNG): кладётся ПОСЛЕ `catalog.cmd_init()`,
    поверх положенного им шаблона. Именно после, а не до: порядок «сначала
    слой, потом init» работал бы только за счёт того, что
    `models.ensure_local_template` не трогает существующий файл, — связь
    неочевидная, и первая же правка того умолчания положила бы шаблон
    поверх собранного слоя молча. `None` (по умолчанию) — слой клона
    остаётся ровно шаблоном, который кладёт `cmd_init` (слой пульта не
    прочитан, набора нет).

    При `codex_auth.profile` `CODEX_HOME` отдельного постоянного профиля
    сначала получает проверка входа, затем профиль восстанавливается из
    референса в дереве клона (файлы проверяемого SHA). Неуспех любого из
    двух отказывает до `yield`, то есть до платного шага.
    Старая форма `codex_auth` без `profile` оставлена для прямых вызывающих
    и существующих тестов: она использует развёрнутый дом клона.
    Подготовка идёт после `catalog.cmd_init()` и внутри `try`, чтобы
    курируемый дом существовал и исключение всегда убирало временный клон.

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
    dest = _owned_temp_dir("artel-canary-")
    origin_dir = _owned_temp_dir("artel-canary-origin-")
    saved = {attr: getattr(config, attr) for attr in _CLONE_CONFIG_ATTRS}
    saved_codex_home = codex_provider.codex_home_override()
    saved_skip_full_suite = config.CANARY_SKIP_FULL_SUITE
    config.CANARY_SKIP_FULL_SUITE = True
    try:
        clone = _clone_into_owned(["git", "clone", "-q"], outer_root, dest)
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
        mirror = _clone_into_owned(
            ["git", "clone", "-q", "--bare", "--shared"], dest, origin_dir)
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
        _build_artel_project_area(origin_dir)
        catalog.cmd_init()
        if local_layer_text is not None:
            config.MODELS_LOCAL.parent.mkdir(parents=True, exist_ok=True)
            config.MODELS_LOCAL.write_text(local_layer_text, encoding="utf-8")
        if codex_auth is not None:
            if codex_auth.pointer is not None:
                _install_codex_pointer(codex_auth.pointer)
            if codex_auth.profile is None:
                codex_provider.set_codex_home_override(None)
                _refuse_unless_clone_logged_in(codex_auth.role, saved["ROLE_HOME"])
            else:
                # Вход — раньше восстановления: несделанный вход Оператора
                # должен называться своим отказом, а не уступать место
                # отказу подготовки профиля.
                codex_provider.set_codex_home_override(codex_auth.profile)
                _refuse_unless_profile_logged_in(
                    codex_auth.role, saved["ROLE_HOME"], codex_auth.profile)
                try:
                    _restore_canary_profile(
                        codex_auth.profile,
                        dest.joinpath(*codex_provider.HOME_REFERENCE_DIR))
                except OSError as exc:
                    sys.exit(f"canary: профиль Codex канарейки не "
                             f"восстановлен: {codex_auth.profile}: {exc}")
        yield dest
    finally:
        # suite-run создаёт собственную сессию и не входит в группу ведения.
        # Его pid сохраняется в хозяйстве именно этого клона.
        for run_path in (dest / ".artel" / "logs" / "suite-run").glob("*/run.json"):
            try:
                pid = int(json.loads(run_path.read_text(encoding="utf-8"))["pid"])
            except (OSError, ValueError, KeyError, TypeError):
                continue
            if pid > 0:
                liveness.terminate_process_group(pid)
        config.CANARY_SKIP_FULL_SUITE = saved_skip_full_suite
        codex_provider.set_codex_home_override(saved_codex_home)
        for attr, value in saved.items():
            setattr(config, attr, value)
        shutil.rmtree(dest, ignore_errors=True)
        shutil.rmtree(origin_dir, ignore_errors=True)


# Каталог клонирования внутри временного каталога канарейки: `git clone`
# отказывает в непустой каталог, а маркер владельца в нём уже лежит.
_CLONE_STAGE = ".artel-canary-stage"


def _owned_temp_dir(prefix: str) -> Path:
    """Временный каталог канарейки с маркером владельца с момента создания
    (SPEC 01M4G8MNEPECNX1TCEDW4T4RPX, требования 4 и 6).

    Уборка сирот `doctor --fix` (`doctor/orphans.py`) удаляет каталог
    `artel-canary-*` без маркера живого владельца. Маркер, записанный
    только после `git clone`, оставлял окно длиной в клонирование: уборка
    параллельного процесса удаляла пустой каталог, и клон в него падал
    «could not lock config file». Маркер пишется сразу за `mkdtemp` — до
    любого вызова git."""
    path = Path(tempfile.mkdtemp(prefix=prefix))
    (path / liveness.CANARY_OWNER_MARKER).write_text(
        str(os.getpid()), encoding="utf-8")
    return path


def _clone_into_owned(command: list, source: Path,
                      dest: Path) -> subprocess.CompletedProcess:
    """`command source dest` для каталога `dest` с маркером владельца:
    git клонирует в подкаталог `dest`, затем содержимое поднимается в сам
    `dest`. Подкаталог — не верхний уровень временного каталога, уборка
    сирот его не рассматривает, а `dest` всё это время защищён маркером."""
    stage = dest / _CLONE_STAGE
    result = subprocess.run([*command, str(source), str(stage)],
                            capture_output=True, text=True)
    if result.returncode == 0:
        for entry in stage.iterdir():
            entry.rename(dest / entry.name)
        stage.rmdir()
    return result


def _build_artel_project_area(origin_dir: Path) -> None:
    """Область проекта артели во временном каталоге клона (SPEC
    01M42PENCS26D0656X8FR7DFA7, требование 7, AC-12): `projects/artel/repo`
    — клон origin-заглушки, а не `url` записи `targets.yaml` (тот ведёт в
    боевой `origin` пульта, куда канарейка не ходит, требование 3 SPEC
    01M1NEEWH5K1XPFRDGRMPYSBXJ). Хуки — пина клона (`config.ROOT` уже
    переадресован на него). Рабочие копии задач заводит дальше тот же
    код, что у боевого пульта (`workspace.ensure` из `catalog.cmd_new`
    процесса клона). Боевая `.artel/projects/artel` не трогается."""
    repo = workspace.repo(config.DEFAULT_TARGET)
    repo.parent.mkdir(parents=True, exist_ok=True)
    res = gitcmd.in_repo(repo.parent, "clone", "-q", str(origin_dir), repo.name)
    if res is None or res.returncode != 0:
        raise RuntimeError(
            f"canary: клон области проекта артели не создан: "
            f"{(res.stderr or '').strip() if res is not None else 'git не ответил'}")
    error = workspace.set_clone_hooks(repo)
    if error is not None:
        raise RuntimeError(f"canary: хуки клона области проекта: {error}")


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
    # Вердикт `fail` аудита SPEC проходит гейт только явным флагом
    # Оператора (SPEC 01M4MQAGRWMWR0GFDM9086P3TD, требование 19): автогейт
    # канарейки его не принимает — задача снимается как неоконченная,
    # прогон красный.
    verdict = spec_audit.last_verdict(conn, task_id)
    if verdict == "fail":
        _kill_inconclusive(
            conn, task_id,
            f"canary: аудит SPEC — последний вердикт fail, возвраты "
            f"аналитику исчерпаны; автогейт SPEC канарейки этот вердикт не "
            f"проводит")
        return
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
    (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ, требование 6, AC-6 — механизм
    введён им) — повторяет эффект ветки `elif state ==
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

    Сам текст ответа — `_SYNTHETIC_ANSWER_TEXT`, один на все роли и все
    эскалации прогона: происхождение механизма (номер SPEC выше) живёт
    ЗДЕСЬ, а не в тексте, который читает роль, — иначе роль принимает
    ответ за ответ по другой задаче (SPEC 01M3MHBNMT1VDXSRQNV1GX30BV,
    требование 3).
    """
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8")
    try:
        tmp.write(_SYNTHETIC_ANSWER_TEXT)
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


_STATE_PREFIX = "state -> "
_ESCALATED_ACTION = _STATE_PREFIX + "escalated"
UNKNOWN_ESCALATION_ROLE = "unknown"


def escalation_roles(steps) -> list[str]:
    """Роли эскалаций журнала задачи клона по порядку (SPEC
    01M4VC31NFCS6JZ0VE8HNJ7FYM, требование 1): одна позиция на каждый
    `state -> escalated`.

    Роль — по состоянию, в которое задача вошла последним переходом до
    эскалации (без перехода — начальное `spec_writing`: задачу заводят
    сразу в нём, перехода журнал не пишет), и только если до следующего
    перехода стоит маркер эскалации по артефакту роли. Маркер не соседний:
    `store.set_state` сам пишет фиксацию за переходом, и лишь затем
    вызывающий — маркер. Эскалация без маркера — эскалация пульта
    (бюджет, инцидент, лимит ревью), её роль `unknown` из любого состояния.
    """
    actions = [r["action"] for r in steps]
    roles_out = []
    source = "spec_writing"
    for i, action in enumerate(actions):
        if not action.startswith(_STATE_PREFIX):
            continue
        if action != _ESCALATED_ACTION:
            source = action[len(_STATE_PREFIX):]
            continue
        role = UNKNOWN_ESCALATION_ROLE
        for later in actions[i + 1:]:
            if later.startswith(_STATE_PREFIX):
                break
            if later == fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER:
                role = _source_state_role(source)
                break
        roles_out.append(role)
    return roles_out


def _source_state_role(state: str) -> str:
    if state == "spec_writing":
        return "analyst"
    return config.STATE_ROLE.get(state, UNKNOWN_ESCALATION_ROLE)


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
_AUTOGATE_REFUSAL_ACTION = "автогейт acceptance не пройден"

# Потолок строк выдержки журнала (требование 2, AC-6) — с запасом под
# итоговую строку метрик и строку пути диагностики, которые печатаются
# ниже: суммарный вывод по задаче не должен вылезать за 20 строк
# целиком, не только сама выдержка.
_JOURNAL_EXCERPT_LIMIT = 18


def _journal_excerpt_lines(steps, limit: int = _JOURNAL_EXCERPT_LIMIT) -> list:
    """Выдержка журнала задачи (требование 2, AC-6): переходы состояний
    (`state -> ...`) и записи «переход отклонён»/«auto остановлен»/
    «автогейт acceptance не пройден» —
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
    last_refusal = None
    for row in steps:
        action = row["action"]
        if not (action.startswith("state -> ")
               or action.startswith(store.REFUSAL_ACTION_PREFIX)
               or action in (_AUTO_STOPPED_ACTION, _AUTOGATE_REFUSAL_ACTION)):
            continue
        detail = " ".join((row["detail"] or "").split())
        suffix = f" — {detail}" if detail else ""
        lines.append(f"{row['ts']} {row['actor']}: {action}{suffix}")
        if action == _AUTOGATE_REFUSAL_ACTION:
            last_refusal = len(lines) - 1
    if limit > 0 and last_refusal is not None and last_refusal < len(lines) - limit:
        tail = lines[-(limit - 1):] if limit > 1 else []
        return [lines[last_refusal], *tail]
    return lines[-limit:]


def _acceptance_from_steps(steps) -> tuple[str | None, str | None, bool]:
    """Способ приёмки, причина отказа и факт входа в acceptance из журнала клона."""
    reached = False
    route = None
    refusal = None
    for row in steps:
        action = row["action"]
        if action == "state -> acceptance":
            reached = True
        elif action == _AUTOGATE_REFUSAL_ACTION:
            refusal = row["detail"] or ""
        elif action == "state -> merge_gate" and reached:
            if row["actor"] == "autogate":
                route = "autogate"
            elif row["actor"] == "canary":
                route = "manual"
    return route, refusal, reached


def _acceptance_summary(route: str | None, refusal: str | None,
                        reached: bool) -> str:
    if refusal is not None:
        reason = " ".join(refusal.split())[:500]
        if route == "manual":
            return f"  приёмка вручную: {reason}"
        return f"  причина отказа автогейта: {reason}"
    if reached and route != "autogate":
        return "  автогейт не запускался"
    return ""


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
    """Сохраняет диагностику незелёного/расходящегося исхода или отказа
    автогейта приёмки канареечной
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
        text, _reason = artifact_branch.show(task_id, branch, f"tasks/{task_id}/{name}")
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
    """Фаза 1 из 3 (требование 6) `_run_one_task`: ОДНА канареечная задача
    в собственном эфемерном клоне на checkout'е `explicit_target_sha`
    (требование 1/2), с диагностикой, сохранённой, пока клон ещё жив.
    Возвращает всё, что нужно двум следующим фазам — `task_id`, `title`,
    `expected`, `steps`, `metrics`, `actual`, `mismatch`, `normal_outcome`,
    `diag_dir`.

    Заводит и ведёт задачу НЕ этот процесс (SPEC 01M3PKSWPETC49WFTFZ69GH3F2,
    требования 1, 3): здесь только запуск процесса клона
    (`_drive_in_clone`) и разбор его результата (`_read_drive_result`).
    Форма возвращаемого кортежа прежняя — её держат подмены фазы 1 в
    `tests/test_canary_codex_clone_auth.py` и залоченной планке
    01M3GKJFN90ATK2KECNDZXPPP6, — поэтому коммит, чьим кодом велась задача,
    едет к фазе 3 в `metrics` (`code_sha`, рядом — проверяемый
    `target_sha`), а не новым элементом кортежа. Его расхождение с
    проверяемым коммитом (требование 5) делает исход не штатным: вердикт
    не `green`, диагностика сохраняется, базовая линия не трогается.

    Сбой процесса клона (требование 7) — `CanaryDriveFailed` после
    сохранения его вывода в каталог диагностики, изнутри блока клона: клон
    и origin-заглушку убирает тот же `finally`, что и всегда. Коммит без
    входа `CANARY_DRIVE_ENTRY` (требование 6) — именованный отказ до
    заведения задачи.

    `layer_text` (SPEC 01M3FQ2Z2PY0E9T5F5WQ207NP5, требования 4-5; SPEC
    01M3PYMQ6N4SCAJ9WWTTKH6XNG, требование 1) — локальный слой клона,
    собранный из слоя пульта и набора ролей; `None` — слой клона остаётся
    шаблоном `models.LOCAL_TEMPLATE`, как его кладёт `catalog.cmd_init()`.

    `codex_auth` для набора Codex несёт адрес отдельного профиля и
    указатель связки ключей; `None` — роли Codex в наборе нет.

    Вывод процесса клона на экран пульта не идёт — только в файл, который
    попадает в диагностику: между строкой «заведена» (печатается
    вызывающим ПОСЛЕ выхода из этой фазы) и остальным выводом иначе лёг бы
    десяток строк `store.set_state`/`cleanup.cmd_kill`, как и до переноса.
    """
    raw = template_path.read_text(encoding="utf-8")
    title = template_path.stem
    expected = _expected_escalation(raw)
    # Проверяемый коммит — снаружи клона и до него: без явного sha клон
    # стоит на HEAD главной копии, а изнутри блока `gitcmd` смотрел бы уже
    # в сам клон.
    target_sha = (explicit_target_sha if explicit_target_sha is not None
                  else gitcmd.head_sha())

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
    with clone_ctx as dest:
        if not (dest / CANARY_DRIVE_ENTRY).is_file():
            sys.exit(
                f"canary: коммит {target_sha} не несёт входа "
                f"{CANARY_DRIVE_ENTRY} — он не умеет вести учебную задачу "
                "своим кодом (ADR-0021, этап 0). Вести её кодом пина "
                "канарейка не будет: такой прогон проверял бы не этот "
                "коммит. Учебная задача не заведена.")
        returncode, log_text, result_path = _drive_in_clone(dest,
                                                            template_path)
        result, problem = _read_drive_result(result_path)
        if returncode is None:
            problem = (f"не завершился за {CANARY_DRIVE_TIMEOUT_SEC} с и "
                       "снят вместе со своей группой процессов")
        elif returncode != 0:
            problem = f"завершился с кодом {returncode}"
        if problem is not None:
            task_id = result["task_id"] if result is not None else None
            diag_dir = _save_drive_failure(outer_root, run_stamp,
                                           task_id or title, log_text,
                                           problem)
            raise CanaryDriveFailed(title, expected, problem, diag_dir, task_id)

        task_id = result["task_id"]
        steps = result["steps"]
        metrics = result["metrics"]
        metrics["code_sha"] = result["head"]
        metrics["target_sha"] = target_sha
        actual = bool(result["escalated"])
        mismatch = expected is not None and expected != actual
        # «Поделена» (01M29284PTCJXGERV5262E9XMM, требование 4) — штатный
        # исход наравне со «штатно»: родитель, поделённый на подзадачи,
        # не сбой прогона, диагностика ему не нужна. Задача, которую вёл
        # код другого коммита, штатной не бывает (требование 5).
        normal_outcome = (metrics["kill_note"] in ("штатно", "поделена")
                          and result["head"] == target_sha)
        diag_dir = None
        _route, autogate_refusal, _reached = _acceptance_from_steps(steps)
        if (_needs_diagnostics(normal_outcome, mismatch)
                or autogate_refusal is not None):
            diag_dir = _save_diagnostics(outer_root, run_stamp, task_id, steps)
            (diag_dir / _DRIVE_LOG_NAME).write_text(log_text, encoding="utf-8")

    return (task_id, title, expected, steps, metrics, actual, mismatch,
           normal_outcome, diag_dir)


class _SignalDeferral:
    """Откладывает SIGTERM, SIGHUP и SIGINT от создания до `release()`
    (SPEC 01M583RM59DHDRDH877AERAVMD, требования 1-4, 8).

    Не маска `pthread_sigmask` и не `SIG_IGN`: оба наследуются процессом
    ведения через fork и exec, и SIGTERM снятия группы не снял бы его до
    SIGKILL. Обработчик-функция Python при exec сбрасывается в действие по
    умолчанию. Уже игнорируемый на входе сигнал не перехватывается — он и
    так прогон не обрывает. Вне главного потока обработчик не ставится:
    Python этого не позволяет, а сигнал туда и не доставляется.
    """

    SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)

    def __init__(self):
        self.previous = {}
        self.pending = None
        if threading.current_thread() is not threading.main_thread():
            return
        for signum in self.SIGNALS:
            handler = signal.getsignal(signum)
            if handler in (signal.SIG_IGN, None):
                continue
            self.previous[signum] = handler
            signal.signal(signum, self._defer)

    def _defer(self, signum, _frame):
        if self.pending is None:
            self.pending = signum

    def release(self) -> None:
        """Возвращает прежние обработчики и поднимает отложенный сигнал ими
        же — тем исключением, что дал бы сигнал во время ожидания."""
        for signum, handler in self.previous.items():
            signal.signal(signum, handler)
        self.previous = {}
        if self.pending is not None:
            signum, self.pending = self.pending, None
            signal.raise_signal(signum)


def _drive_in_clone(dest: Path, template_path: Path) -> tuple:
    """Запускает процесс ведения из клона `dest` и ждёт его не дольше
    `CANARY_DRIVE_TIMEOUT_SEC` (SPEC 01M3PKSWPETC49WFTFZ69GH3F2, требования
    1, 7). Возвращает `(код выхода | None, вывод процесса, путь файла
    результата)`; `None` — процесс снят по времени.

    Своя группа процессов (`start_new_session`): шаги ролей — потомки
    процесса клона, и по таймауту снимается вся группа, а не один родитель,
    оставивший бы агентов работать на удалённый клон. Интерпретатор —
    интерпретатор пульта (`sys.executable`), venv — значение процесса пульта
    внутри блока клона. Адрес отдельного `CODEX_HOME` передаётся процессу
    клона явно, только когда выбран набор с Codex.

    Вывод пишется в файл, а не в канал: ведение длится часами, и канал,
    который никто не читает до конца процесса, заполнился бы и повесил его.
    """
    work = dest / ".artel"
    work.mkdir(parents=True, exist_ok=True)
    result_path = work / _DRIVE_RESULT_NAME
    log_path = work / _DRIVE_LOG_NAME
    argv = [sys.executable, "-m", CANARY_DRIVE_MODULE,
            "--template", str(template_path), "--result", str(result_path),
            "--venv-dir", str(config.VENV_DIR)]
    codex_home = codex_provider.codex_home_override()
    if codex_home == _canary_profile_home() / ".codex":
        argv += ["--codex-home", str(codex_home)]
    # Без буферизации: вывод в файл у Python блочно буферизован, а снятие
    # по таймауту сигналом буфер не сбрасывает — диагностика зависания
    # осталась бы без последних строк ведения.
    env = {**os.environ, "PYTHONUNBUFFERED": "1",
           config.CANARY_SKIP_FULL_SUITE_ENV:
               "1" if config.CANARY_SKIP_FULL_SUITE else "0"}
    with open(log_path, "w", encoding="utf-8") as log:
        # Сигнал между созданием процесса и `proc =` ушёл бы наверх мимо
        # снятия группы ниже, оставив ведение сиротой удалённого клона
        # (SPEC 01M583RM59DHDRDH877AERAVMD): он откладывается до места, где
        # группа уже известна.
        deferral = _SignalDeferral()
        try:
            proc = subprocess.Popen(argv, cwd=dest, stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT,
                                    env=env, start_new_session=True)
        except OSError as exc:
            deferral.release()
            return 127, f"canary: процесс клона не запущен: {exc}\n", result_path
        except BaseException:
            deferral.release()
            raise
        try:
            deferral.release()
            returncode = proc.wait(timeout=CANARY_DRIVE_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            liveness.terminate_process_group(proc.pid)
            proc.wait()
            returncode = None
        except BaseException:
            # Своя сессия не получает SIGINT терминала: прерванный пульт
            # (Ctrl-C, `SystemExit` обработчика сигнала) иначе оставил бы
            # агентов роли работать на клон, который `finally` уже удаляет.
            liveness.terminate_process_group(proc.pid)
            proc.wait()
            raise
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    return returncode, log_text, result_path


def _read_drive_result(path: Path) -> tuple:
    """`(результат, None)` — файл несёт один разборчивый JSON-объект
    результата процесса клона; `(None, причина)` — иначе (требование 7).

    Проверяется всё, что читают следующие фазы: без проверки здесь
    неполный объект уронил бы пульт `KeyError` уже после уборки клона —
    без диагностики и без строки прогона."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"не записал результат {path.name} ({exc.strerror or exc})"
    try:
        data = json.loads(text)
    except ValueError as exc:
        return None, f"записал неразборчивый результат: {exc}"
    if not isinstance(data, dict):
        return None, "записал результат не JSON-объектом"
    missing = [key for key, kind in (("task_id", str), ("head", str),
                                     ("escalated", bool), ("metrics", dict),
                                     ("steps", list))
               if not isinstance(data.get(key), kind)]
    if not missing:
        missing = [f"metrics.{key}" for key in _DRIVE_METRIC_FIELDS
                   if key not in data["metrics"]]
    if not missing and not all(
            isinstance(step, dict)
            and all(field in step for field in ("ts", "actor", "action",
                                                "detail"))
            for step in data["steps"]):
        missing = ["steps[].ts/actor/action/detail"]
    if missing:
        return None, ("записал результат без полей: " + ", ".join(missing))
    return data, None


def _save_drive_failure(outer_root: Path, run_stamp: str, name: str,
                        log_text: str, reason: str) -> Path:
    """Диагностика сбоя процесса клона (требование 7): его вывод и причина
    — под каталог прогона снаружи клона, пока клон ещё жив. `name` — id
    задачи, если процесс успел его сообщить, иначе имя шаблона: id задачи
    при сбое бывает неизвестен, а каталог обязан быть свой у каждой задачи
    прогона."""
    diag_dir = _diagnostics_dir(outer_root, run_stamp, name)
    diag_dir.mkdir(parents=True, exist_ok=True)
    (diag_dir / _DRIVE_LOG_NAME).write_text(log_text, encoding="utf-8")
    (diag_dir / "failure.txt").write_text(
        f"процесс клона {reason}\n", encoding="utf-8")
    return diag_dir


def _record_canary_run(outer_conn, run_stamp: str, title: str, task_id: str,
                       metrics: dict, expected: bool | None, actual: bool,
                       mismatch: bool, normal_outcome: bool,
                       explicit_target_sha: str | None,
                       target_sha: str, sha_label: str | None,
                       plan: CanarySetPlan,
                       acceptance_route: str | None = None,
                       autogate_refusal: str | None = None,
                       escalation_roles: list[str] | None = None) -> tuple:
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

    С переносом ведения в процесс клона (SPEC 01M3PKSWPETC49WFTFZ69GH3F2,
    требование 5) `main_sha` — коммит, чьим кодом задача ДЕЙСТВИТЕЛЬНО
    велась (`metrics["code_sha"]`, HEAD клона, сообщённый процессом), а
    не тот, который пульт собирался проверить: зелёная строка прогона —
    допуск `pin-update`, и утверждать она обязана исполненный код. Он же
    возвращается для сводки. При штатном прогоне оба sha равны; их
    расхождение фаза 1 уже сделала не штатным исходом, поэтому вердикт
    здесь считается прежней формулой. Метрики без `code_sha` (подмена
    фазы 1 в тестах) — прежнее поведение: проверяемый sha.

    `escalation_roles` (SPEC 01M4VC31NFCS6JZ0VE8HNJ7FYM, требование 1) —
    роли эскалаций, вычисленные пультом из `steps` результата клона
    (`escalation_roles(steps)`), не из `metrics`: результат клона кода до
    этой задачи ролей не несёт, а строка его прогона их получить обязана.
    """
    if explicit_target_sha is None:
        target_sha = gitcmd.head_sha()
    if sha_label is None:
        sha_label = _sha_label(target_sha, None)
    main_sha = metrics.get("code_sha") or target_sha
    if main_sha != target_sha:
        sha_label = _sha_label(main_sha, None)
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
        set_name=plan.name, models_summary=plan.summary or None,
        acceptance_route=acceptance_route,
        autogate_refusal=autogate_refusal,
        escalation_roles=escalation_roles)
    return main_sha, sha_label


def _baseline_deviation_note(outer_conn, task_id: str, title: str,
                             metrics: dict, normal_outcome: bool,
                             mismatch: bool, ratio: float,
                             set_name: str = config.CANARY_DEFAULT_SET,
                             models_summary: str | None = None) -> str:
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

    Та же пара на ДРУГИХ моделях ролей (SPEC 01M3PYMQ6N4SCAJ9WWTTKH6XNG,
    требование 5) — несравнимая базовая линия: слой пульта сменил модель
    яруса, а имя набора осталось прежним. Модели прогона
    (`models_summary`) сверяются с последним штатным прогоном пары, кроме
    ЭТОГО (его строку `_record_canary_run` уже записала); строка без
    сводки моделей всех ролей — тоже несравнимость. Тогда отклонения не
    считаются, алерт не поднимается, линия перезаписывается числами
    прогона, а примечание называет причину — вердикт прогона от этого не
    меняется. `models_summary=None` (вызов без плана) — сверки моделей
    нет, поведение прежнее.
    """
    if _needs_diagnostics(normal_outcome, mismatch):
        return ""
    baseline = store.canary_baseline(outer_conn, title, set_name)
    if baseline is None:
        store.set_canary_baseline(outer_conn, title, metrics["steps"],
                                  metrics["cost_usd"],
                                  metrics["review_iterations"], set_name)
        return "  [бейзлайн создан]"
    if models_summary is not None:
        current = _summary_models(models_summary)
        previous = _previous_run_models(outer_conn, title, set_name, task_id)
        if previous != current:
            store.set_canary_baseline(outer_conn, title, metrics["steps"],
                                      metrics["cost_usd"],
                                      metrics["review_iterations"], set_name)
            return ("  [ВНИМАНИЕ: базовая линия несравнима — модели ролей "
                    f"сменились (было: {previous or 'сводки моделей нет'}; "
                    f"стало: {current}); отклонения не считаются, базовая "
                    "линия перезаписана числами этого прогона]")
    warnings = _task_deviation_warnings(metrics, baseline, ratio)
    if not warnings:
        return ""
    for w in warnings:
        alerts.raise_alert(
            outer_conn, task_id, "threshold", "canary",
            f"канарейка {title} ({task_id}), набор {set_name}: {w}")
    return "  [ВНИМАНИЕ: отклонение от бейзлайна: " + "; ".join(warnings) + "]"


def _previous_run_models(outer_conn, title: str, set_name: str,
                         task_id: str) -> str | None:
    """Модели ролей последнего штатного (зелёного) прогона пары (шаблон,
    набор), кроме задачи `task_id` — строка текущего прогона к этому
    моменту уже записана, и сверка с ней находила бы «те же модели»
    всегда. `None` — такого прогона нет либо сводки моделей у него нет."""
    for row in store.green_canary_runs(outer_conn, set_name):
        if row["title"] == title and row["task_id"] != task_id:
            return _summary_models(row["models_summary"])
    return None


def _run_one_task(template_path: Path, run_stamp: str, ratio: float,
                  target_sha: str | None = None,
                  sha_label: str | None = None,
                  plan: CanarySetPlan | None = None,
                  codex_auth: CodexCloneAuth | None = None) -> None:
    """Полный цикл одной канареечной задачи: заводит, ведёт в собственном
    эфемерном клоне на checkout'е `target_sha` (требование 1/2), пишет
    метрики/бейзлайн в БД пульта СНАРУЖИ клона (требование 5, 9) и
    печатает итог с подписью «код клона <sha>» — коммита, сообщённого
    процессом клона (SPEC 01M3PYMQ6N4SCAJ9WWTTKH6XNG, требование 4;
    `sha_label` принимается ради прежних вызывающих, но в сводку больше не
    идёт). Разбита на три фазы (требование 6, SPEC
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
    (`gitcmd.head_sha()` главной копии в момент вызова).

    «Штатный исход без расхождения» (ANSWER-1.md, вариант Б) — случай,
    где бейзлайн/сравнение отклонений применяются (требование 3,
    AC-7/AC-8). Диагностика в нём сохраняется только при отказе
    автогейта приёмки: `_kill_outcome_note` отличает штатный kill на
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
    собранный `_canary_profile_auth` ДО клона под замком
    `_locked_canary_profile` (SPEC 01M3V4ZPB6HFDJ36MTDAQG5VNT: отдельный
    постоянный профиль); `None` — ни одна роль прогона не идёт провайдером
    Codex.
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
    try:
        (task_id, title, expected, steps, metrics, actual, mismatch,
         normal_outcome, diag_dir) = _run_task_in_ephemeral_clone(
            template_path, run_stamp, explicit_target_sha, outer_root,
            plan.layer_text, **phase_one_extra)
    except CanaryDriveFailed as failure:
        _report_drive_failure(failure, run_stamp, plan)
        return

    print(f"[canary] {task_id} заведена из {template_path.name}")

    acceptance_route, autogate_refusal, reached_acceptance = (
        _acceptance_from_steps(steps))
    outer_conn = store.db()
    target_sha, _label = _record_canary_run(
        outer_conn, run_stamp, title, task_id, metrics, expected, actual,
        mismatch, normal_outcome, explicit_target_sha, target_sha, sha_label,
        plan, acceptance_route, autogate_refusal,
        escalation_roles=escalation_roles(steps))

    note = _baseline_deviation_note(outer_conn, task_id, title, metrics,
                                    normal_outcome, mismatch, ratio, plan.name,
                                    plan.summary or None)

    mismatch_note = ""
    if mismatch:
        mismatch_note = (
            "  [РАСХОЖДЕНИЕ: маркер ожидал "
            f"{'эскалацию' if expected else 'без эскалации'}, по факту "
            f"{'эскалация была' if actual else 'эскалации не было'}]")

    # Требование 5 (SPEC 01M3PKSWPETC49WFTFZ69GH3F2): задачу вёл код не того
    # коммита, который проверялся, — причина и оба коммита в строке сводки.
    code_sha = metrics.get("code_sha")
    checked_sha = metrics.get("target_sha")
    if code_sha and checked_sha and code_sha != checked_sha:
        mismatch_note += (
            f"  [РАСХОЖДЕНИЕ КОММИТА: задачу вёл код {code_sha}, а "
            f"проверялся {checked_sha} — прогон не зелёный]")

    # Подпись кода — коммит, сообщённый процессом клона (SPEC
    # 01M3PYMQ6N4SCAJ9WWTTKH6XNG, требование 4): задачу ведёт код клона, и
    # «код пина» при совпадении с HEAD главной копии вводил бы в
    # заблуждение. `sha_label` фазы 3 в сводку больше не идёт.
    clone_code_label = f"код клона {code_sha or target_sha}"
    outcome_note = f" ({metrics['kill_note']})" if metrics["kill_note"] else ""
    test_author_note = "да" if metrics["test_author_visited"] else "нет"
    acceptance_note = _acceptance_summary(
        acceptance_route, autogate_refusal, reached_acceptance)
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
         f"sha={target_sha} ({clone_code_label})  "
         f"набор={plan.name}{_summary_note(plan)}  "
         f"test_author={test_author_note}{acceptance_note}{mismatch_note}{note}")
    if diag_dir is not None:
        print(f"  диагностика: {diag_dir}")


def _report_drive_failure(failure: CanaryDriveFailed, run_stamp: str,
                          plan: CanarySetPlan) -> None:
    """Красная строка `canary_runs` и сводка задачи, чей процесс клона не
    дал результата (SPEC 01M3PKSWPETC49WFTFZ69GH3F2, требование 7).

    Строка пишется, а не пропускается: история прогонов обязана показывать
    и такой прогон, иначе сбой ведения выглядел бы в ней как прогон,
    которого не было. Метрик у неё нет — нули; `main_sha` пуст: какой код
    вёл задачу, процесс не сообщил, и утверждать это за него пульт не
    вправе. Базовая линия не трогается. Остальные задачи прогона идут
    дальше — пульт не падает."""
    expected = failure.expected
    store.insert_canary_run(
        store.db(), run_stamp, failure.title, failure.task_id, 0, 0.0, 0, 0,
        _DRIVE_FAILED_OUTCOME,
        "yes" if expected else ("no" if expected is False else None),
        False, False, main_sha=None, verdict="red",
        set_name=plan.name, models_summary=plan.summary or None)
    who = failure.task_id or failure.title
    print(f"[canary] {who}: учебная задача шаблона {failure.title} не "
          f"доведена — процесс клона {failure.reason}; прогон красный")
    print(f"  диагностика: {failure.diag_dir}")


def _summary_note(plan: CanarySetPlan) -> str:
    """Сводка моделей ролей прогона в скобках (SPEC
    01M3PYMQ6N4SCAJ9WWTTKH6XNG, требование 4) — у `cmd_canary` она есть
    всегда, и у набора по умолчанию тоже: слой пульта — файл вне git, и
    по его сегодняшнему тексту модели прошлого прогона не восстановить.
    Пусто только у плана вызывающих без плана (`_DEFAULT_SET_PLAN`)."""
    return f" ({plan.summary})" if plan.summary else ""


def _target_origin_note(explicit_sha: str | None, target_sha: str,
                        origin_sha: str | None) -> str:
    """Откуда взят проверяемый sha — для первой строки прогона. Не
    «код пина»: сравнение с HEAD главной копии здесь ни о чём не говорит,
    задачу ведёт код клона (SPEC 01M3PYMQ6N4SCAJ9WWTTKH6XNG, требование
    4), и чей он — называет строка итога задачи."""
    if explicit_sha is not None:
        return "явный --sha"
    if origin_sha is not None and target_sha == origin_sha:
        return "голова origin/main"
    return "HEAD главной копии — origin не ответил"


# Реестр живого прогона (SPEC 01M5C6QA6S3RY9PS4H9ZJ58WQ0, требования 1-3):
# правило «пока идёт канарейка, main не двигать» держится не дисциплиной
# сессии, а записью, которую читают окно тишины `note`/`doc-commit`, гейт
# мержа и обходы окна. Потребители импортируют этот модуль лениво: он сам
# тянет `pool_seal` -> `notes` и `fsm`.
DURING_CANARY_FLAG = fsm.DURING_CANARY_FLAG
LIVE_RUN_SWEPT_ACTION = "канарейка: запись реестра живого прогона убрана"
DURING_CANARY_ACTION = "команда во время канарейки"
_LIVE_RECORD_SUFFIX = ".json"
_LIVE_MARK_SUFFIX = ".lock"
# Метка без записи (SPEC 01M5FA4NR91PCF47SZT6V0Q9HS, требование 1):
# нечитаемая метка моложе порога — прогон, ещё не записавший в неё pid.
_LIVE_MARK_UNREADABLE_GRACE_SEC = 60
LIVE_MARK_ABSENT_NOTE = "(запись реестра отсутствует)"
LIVE_RUN_DROPPED_ACTION = "канарейка: запись реестра снята Оператором"
RUN_STAMP_RE = re.compile(r"[0-9]{8}T[0-9]{6}Z")


def _live_dir() -> Path:
    return config.ROOT / ".artel" / config.CANARY_LIVE_DIRNAME


def _stale_cycles():
    """Модуль `doctor/stale_cycles` — не имя пакета `doctor`: фасад
    реэкспортирует одноимённую функцию `stale_cycles`. Лениво: `doctor`
    импортирует этот модуль."""
    return importlib.import_module(".doctor.stale_cycles", __package__)


def _moment_text(moment: datetime | None) -> str | None:
    return None if moment is None else moment.isoformat()


def _parse_moment(text) -> datetime | None:
    if not isinstance(text, str):
        return None
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else moment.replace(
        tzinfo=timezone.utc)


@contextmanager
def _live_run_record(run_stamp: str, target_sha: str, set_name: str,
                     task_count: int):
    """Запись реестра на время прогона и метка `run_stamp` рядом с ней.

    Метка создаётся исключительно (`O_EXCL`) ДО записи — повтор
    `run_stamp` отказывает без «прочитать, потом записать», в том числе
    между двумя процессами; при отказе чужие метка и запись не трогаются.
    Пути запоминаются здесь: во время ведения `_ephemeral_clone` уводит
    `config.ROOT` на клон, а снять надо файлы пульта. Снятие — `finally`:
    штатный конец, исключение и сигнал (`_interrupt_on_signal` снаружи
    превращает его в исключение)."""
    directory = _live_dir()
    directory.mkdir(parents=True, exist_ok=True)
    pid = os.getpid()
    mark = directory / f"{run_stamp}{_LIVE_MARK_SUFFIX}"
    record = directory / f"{run_stamp}-{pid}{_LIVE_RECORD_SUFFIX}"
    try:
        fd = os.open(mark, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        sys.exit(f"canary: прогон {run_stamp} уже идёт")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(f"{pid}\n")
        started = _stale_cycles().process_start_time(pid)
        payload = {"pid": pid, "process_start": _moment_text(started),
                   "run_stamp": run_stamp, "sha": target_sha,
                   "set_name": set_name,
                   "started_at": datetime.now(timezone.utc).isoformat(),
                   "tasks": task_count}
        tmp = record.with_name(record.name + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, record)
        yield record
    finally:
        record.unlink(missing_ok=True)
        record.with_name(record.name + ".tmp").unlink(missing_ok=True)
        mark.unlink(missing_ok=True)


def _live_verdict(entry: dict | None) -> str | None:
    """`None` — запись живая; иначе — почему нет (строка журнала)."""
    if entry is None:
        return "запись не читается"
    try:
        pid = int(entry["pid"])
        tasks = int(entry["tasks"])
    except (KeyError, TypeError, ValueError):
        return "запись не читается"
    started_at = _parse_moment(entry.get("started_at"))
    if started_at is None:
        return "запись не читается"
    if not liveness._pid_alive(pid):
        return f"pid {pid} не жив"
    ceiling = CANARY_DRIVE_TIMEOUT_SEC * tasks + 3600
    age = (datetime.now(timezone.utc) - started_at).total_seconds()
    if age >= ceiling:
        return f"возраст {int(age)} с не меньше потолка {int(ceiling)} с"
    recorded = _parse_moment(entry.get("process_start"))
    if recorded is None:
        return None
    module = _stale_cycles()
    current = module.process_start_time(pid)
    # Неопределимое при сверке время старта — безопасная сторона: окно
    # держится, запись остаётся.
    if current is None:
        return None
    if abs(current - recorded) > module._LSTART_SPAN:
        return (f"pid {pid} — другой процесс: старт {current.isoformat()}, "
                f"записан {recorded.isoformat()}")
    return None


def _record_mark(path: Path) -> Path:
    stamp = path.name.split("-", 1)[0]
    return path.with_name(f"{stamp}{_LIVE_MARK_SUFFIX}")


def _mark_follows_record(mark: Path, entry: dict | None) -> bool:
    """Метка уходит вместе с мёртвой записью: она пустая либо несёт pid
    записи. Метку чужого (живого) прогона того же `run_stamp` не трогаем."""
    try:
        owner = mark.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    pid = (entry or {}).get("pid")
    return pid is None or owner in ("", str(pid))


def _drop_live_record(path: Path, entry: dict | None, why: str) -> None:
    path.unlink(missing_ok=True)
    mark = _record_mark(path)
    if _mark_follows_record(mark, entry):
        mark.unlink(missing_ok=True)
    store.journal(store.db(), None, "orchestrator", LIVE_RUN_SWEPT_ACTION,
                  f"{path.name}: {why}")


def live_runs() -> list[dict]:
    """Живые прогоны канарейки по реестру (требование 2), по имени записи.

    Живая — pid жив, время старта процесса совпало с записанным в пределах
    `_LSTART_SPAN` (`process_start_time` — тот же помощник, что при
    записи; не определилось при сверке — живая; не определилось при
    записи — сверка только по pid и возрасту) и возраст меньше
    `CANARY_DRIVE_TIMEOUT_SEC` × число задач + час. Остальные записи
    убираются вместе с меткой, каждая — строкой журнала пульта без задачи."""
    directory = _live_dir()
    if not directory.is_dir():
        return []
    alive = []
    for path in sorted(directory.glob(f"*{_LIVE_RECORD_SUFFIX}")):
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
        except (OSError, ValueError):
            entry = None
        if not isinstance(entry, dict):
            entry = None
        why = _live_verdict(entry)
        if why is None:
            alive.append(entry)
        else:
            _drop_live_record(path, entry, why)
    return alive


def _mark_state(mark: Path) -> dict | None:
    """Метка без записи (SPEC 01M5FA4NR91PCF47SZT6V0Q9HS, требование 1):
    `why` — `None`, если прогон живой, иначе почему нет. `None` — метки
    уже нет."""
    try:
        text = mark.read_text(encoding="utf-8")
        age = time.time() - mark.stat().st_mtime
    except FileNotFoundError:
        return None
    except OSError:
        text, age = "", 0.0
    try:
        pid = int(text.strip())
    except ValueError:
        pid = None
    if pid is not None and pid <= 0:
        pid = None
    # Нечитаемая метка свежее порога — прогон между созданием метки и
    # записью в неё pid: безопасная сторона, окно держится.
    if pid is None:
        why = (None if age < _LIVE_MARK_UNREADABLE_GRACE_SEC
               else f"метка не читается, возраст {int(age)} с")
    elif not liveness._pid_alive(pid):
        why = f"pid {pid} не жив"
    else:
        why = None
    return {"path": mark, "run_stamp": mark.name[:-len(_LIVE_MARK_SUFFIX)],
            "pid": pid, "age": age, "why": why}


def _record_stamps(directory: Path) -> set:
    return {p.name.split("-", 1)[0]
            for p in directory.glob(f"*{_LIVE_RECORD_SUFFIX}")}


def live_marks() -> list[dict]:
    """Живые метки без записи (требование 1), по имени метки. Читается
    после уборки записей (`live_runs`): метка, рядом с которой осталась
    запись того же `run_stamp`, не трогается. Мёртвая метка (pid не жив,
    нечитаемая старше 60 с) убирается строкой журнала пульта без задачи."""
    directory = _live_dir()
    if not directory.is_dir():
        return []
    with_records = _record_stamps(directory)
    alive = []
    for mark in sorted(directory.glob(f"*{_LIVE_MARK_SUFFIX}")):
        if mark.name[:-len(_LIVE_MARK_SUFFIX)] in with_records:
            continue
        state = _mark_state(mark)
        if state is None:
            continue
        if state["why"] is None:
            alive.append(state)
            continue
        mark.unlink(missing_ok=True)
        store.journal(store.db(), None, "orchestrator", LIVE_RUN_SWEPT_ACTION,
                      f"{mark.name}: {state['why']}")
    return alive


def _read_live_record(path: Path) -> dict | None:
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return entry if isinstance(entry, dict) else None


def registry_view() -> tuple[list, list]:
    """Реестр без уборки (проверка `doctor`, требование 4): записи
    `(путь, запись, почему не живая | None)` и метки без живой записи
    (`_mark_state`). Метка, которую уборка унесла бы вместе с мёртвой
    записью, — мёртвая."""
    directory = _live_dir()
    if not directory.is_dir():
        return [], []
    records = []
    for path in sorted(directory.glob(f"*{_LIVE_RECORD_SUFFIX}")):
        entry = _read_live_record(path)
        records.append((path, entry, _live_verdict(entry)))
    alive_stamps = {path.name.split("-", 1)[0]
                    for path, _entry, why in records if why is None}
    doomed = {_record_mark(path).name for path, entry, why in records
              if why is not None and _mark_follows_record(_record_mark(path), entry)}
    marks = []
    for mark in sorted(directory.glob(f"*{_LIVE_MARK_SUFFIX}")):
        if mark.name[:-len(_LIVE_MARK_SUFFIX)] in alive_stamps:
            continue
        state = _mark_state(mark)
        if state is None:
            continue
        if mark.name in doomed:
            state["why"] = "уходит вместе с мёртвой записью"
        marks.append(state)
    return records, marks


def record_age(entry: dict) -> float:
    started_at = _parse_moment(entry.get("started_at"))
    if started_at is None:
        return 0.0
    return (datetime.now(timezone.utc) - started_at).total_seconds()


def hours_text(seconds: float) -> str:
    return f"{seconds / 3600:.1f} ч"


def live_run_note(default_set_only: bool = False) -> str | None:
    """«идёт канарейка <run_stamp> на <sha7>» первого живого прогона;
    `default_set_only` — только прогоны набора по умолчанию (мерж,
    требование 7). Записи — первыми; метка без записи — «идёт канарейка
    <run_stamp> (запись реестра отсутствует)», её набор неизвестен и
    считается набором по умолчанию (SPEC 01M5FA4NR91PCF47SZT6V0Q9HS,
    требование 1). `None` — такого прогона нет."""
    runs = live_runs()
    marks = live_marks()
    for entry in runs:
        if default_set_only and entry.get("set_name") != config.CANARY_DEFAULT_SET:
            continue
        return (f"идёт канарейка {entry.get('run_stamp')} на "
                f"{str(entry.get('sha') or '')[:7]}")
    for mark in marks:
        return f"идёт канарейка {mark['run_stamp']} {LIVE_MARK_ABSENT_NOTE}"
    return None


def _record_line(entry: dict) -> str:
    age = record_age(entry)
    ceiling = CANARY_DRIVE_TIMEOUT_SEC * int(entry["tasks"]) + 3600
    parts = [f"{entry.get('run_stamp')}: pid {entry.get('pid')}"]
    if entry.get("parent_pid") is not None:
        parts.append(f"parent_pid {entry['parent_pid']}")
    template = entry.get("template") or ", ".join(
        str(name) for name in entry.get("templates") or [])
    if template:
        parts.append(f"шаблон {template}")
    parts += [f"sha {str(entry.get('sha') or '')[:7]}",
              f"набор {entry.get('set_name')}",
              f"начало {entry.get('started_at')}",
              f"возраст {hours_text(age)}",
              f"до потолка {hours_text(ceiling - age)}"]
    return ", ".join(parts)


def _mark_line(mark: dict) -> str:
    pid = mark["pid"] if mark["pid"] is not None else "не читается"
    return (f"{mark['run_stamp']}: {LIVE_MARK_ABSENT_NOTE}, pid {pid}, "
            f"возраст {hours_text(mark['age'])}")


def _drop_reason(entry: dict | None) -> str | None:
    """Почему запись снимается `canary live --drop` (требование 3);
    `None` — свежая запись живого процесса, строгий вариант её не снимает."""
    if entry is None:
        return "запись не читается"
    if record_age(entry) >= CANARY_DRIVE_TIMEOUT_SEC:
        return f"старше {CANARY_DRIVE_TIMEOUT_SEC // 3600} ч"
    if _parse_moment(entry.get("process_start")) is None:
        return "время старта процесса не определилось при записи"
    try:
        pid = int(entry["pid"])
    except (KeyError, TypeError, ValueError):
        return "запись не читается"
    if _stale_cycles().process_start_time(pid) is None:
        return "время старта процесса не определилось при сверке"
    return None


def cmd_canary_live(drop: str | None = None, reason: str | None = None) -> None:
    """`canary live` — реестр живых прогонов; `canary live --drop
    <run_stamp> "<основание>"` — снятие зависшего (SPEC
    01M5FA4NR91PCF47SZT6V0Q9HS, требования 2-3). Аргументы проверяет
    вызывающий (`artel._cmd_canary_live`) до чтения реестра. Перед показом
    и снятием мёртвое убирается прежним путём чтения реестра. Процессам
    прогона сигналы не шлются."""
    runs = live_runs()
    marks = live_marks()
    if drop is None:
        if not runs and not marks:
            print("живых прогонов канарейки нет")
            return
        print("живые прогоны канарейки:")
        for entry in runs:
            print(f"  {_record_line(entry)}")
        for mark in marks:
            print(f"  {_mark_line(mark)}")
        return
    directory = _live_dir()
    mark = directory / f"{drop}{_LIVE_MARK_SUFFIX}"
    records = sorted(directory.glob(f"{drop}-*{_LIVE_RECORD_SUFFIX}"))
    if not records and not mark.exists():
        print(f"canary live: в реестре нет {drop}")
        return
    removed, pids, kept = [], [], []
    for path in records:
        entry = _read_live_record(path)
        why = _drop_reason(entry)
        if why is None:
            kept.append(entry)
            continue
        path.unlink(missing_ok=True)
        removed.append(f"{path.name} ({why})")
        pids.append((entry or {}).get("pid"))
    if not kept and mark.exists():
        state = _mark_state(mark)
        mark.unlink(missing_ok=True)
        removed.append(f"{mark.name} (метка без записи)")
        pids.append((state or {}).get("pid"))
    if not removed:
        entry = kept[0]
        sys.exit(f"canary live: прогон {drop} жив (pid {entry.get('pid')}, "
                 f"возраст {hours_text(record_age(entry))}) — снимать нечего; "
                 f"дождись итога или используй {DURING_CANARY_FLAG} у "
                 f"конкретной команды")
    warnings = []
    for pid in pids:
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            continue
        warning = f"процесс {pid} жив — прогон продолжается без защиты окна"
        if pid > 0 and liveness._pid_alive(pid) and warning not in warnings:
            warnings.append(warning)
    detail = "; ".join([", ".join(removed), f"основание: {reason}", *warnings])
    store.journal(store.db(), None, "operator", LIVE_RUN_DROPPED_ACTION, detail)
    print(f"canary live: снято {', '.join(removed)}; основание: {reason}")
    for warning in warnings:
        print(f"canary live: {warning}")


CANARY_RUNS_DEFAULT_COUNT = 10


def _runs_value(value) -> str:
    return "—" if value is None else str(value)


def _runs_money(value) -> str:
    return "—" if value is None else f"{value:.2f}"


def _runs_header(stamp: str, rows: list) -> str:
    first = rows[0]
    sha = "—" if first["main_sha"] is None else first["main_sha"][:8]
    green = sum(1 for row in rows if row["verdict"] == "green")
    total = sum(row["cost_usd"] or 0 for row in rows)
    return (f"{stamp}  набор={_runs_value(first['set_name'])}  sha={sha}  "
            f"задач={len(rows)}  зелёных={green}  ${total:.2f}")


def _runs_task_lines(stamp: str, row) -> list:
    line = (f"  {row['title']}  {row['task_id']}  "
            f"вердикт={_runs_value(row['verdict'])}  "
            f"исход={_runs_value(row['outcome'])}  "
            f"${_runs_money(row['cost_usd'])}  "
            f"шагов={_runs_value(row['steps'])}  "
            f"ревью-итераций={_runs_value(row['review_iterations'])}  "
            f"эскалаций={_runs_value(row['escalations'])}")
    if row["escalation_roles"]:
        line += f" (роли: {row['escalation_roles']})"
    if row["marker_mismatch"] == 1:
        line += "  [расхождение маркера]"
    lines = [line]
    summary = _acceptance_summary(row["acceptance_route"],
                                  row["autogate_refusal"], False).lstrip()
    if summary:
        lines.append(f"    {summary}")
    if _diagnostics_dir(config.ROOT, stamp, row["task_id"]).is_dir():
        lines.append(f"    диагностика: .artel/canary/{stamp}/{row['task_id']}")
    return lines


def cmd_canary_runs(since: str | None = None,
                    run_stamp: str | None = None) -> None:
    """`canary runs [--since <ГГГГ-ММ-ДД> | <run_stamp>]` — история
    прошедших прогонов из `canary_runs` (SPEC 01M5KEYG8G1WXHSR4BDKBSH6JP).
    Аргументы проверяет вызывающий (`artel._cmd_canary_runs`) до чтения БД.
    Только чтение через `store`: реестр живых прогонов не читается — строка
    `canary_runs` пишется по итогу прогона, живой прогон в ней не виден."""
    groups: dict = {}
    for row in store.all_canary_runs(store.db()):
        groups.setdefault(row["run_stamp"], []).append(row)
    # `run_stamp` — метка UTC старта: строковый порядок хронологический.
    stamps = sorted(groups, reverse=True)
    if run_stamp is not None:
        if run_stamp not in groups:
            sys.exit(f"canary runs: прогона {run_stamp} нет")
        stamps = [run_stamp]
    elif since is not None:
        border = f"{since} 00:00:00Z"
        stamps = [stamp for stamp in stamps
                  if min(row["created_at"] or "" for row in groups[stamp]) >= border]
    else:
        stamps = stamps[:CANARY_RUNS_DEFAULT_COUNT]
    if not stamps:
        print("прогонов канарейки нет")
        return
    for stamp in stamps:
        rows = groups[stamp]
        print(_runs_header(stamp, rows))
        for row in rows:
            for line in _runs_task_lines(stamp, row):
                print(line)


def during_canary_reason_refusal(command: str) -> str:
    """Отказ флага без основания (требование 6) — общий у всех команд."""
    return (f"{DURING_CANARY_FLAG} требует основание следующим аргументом: "
            f'artel.py {command} {DURING_CANARY_FLAG} "<основание>"')


def refuse_main_move_during_canary(command: str, during_canary: str | None,
                                   ) -> None:
    """Обход окна, двигающий main (требование 8): при живом прогоне любого
    набора без `--during-canary` — отказ `sys.exit`; с флагом — строка
    журнала пульта с основанием, команда идёт дальше. Без живого прогона —
    ничего, флаг принимается молча (требование 10)."""
    note = live_run_note()
    if note is None:
        return
    if during_canary is None:
        sys.exit(f"{note}: команда сдвинет main — дождись итога или повтори "
                 f'с {DURING_CANARY_FLAG} "<основание>"')
    store.journal(store.db(), None, "operator", DURING_CANARY_ACTION,
                  f"{command}: {note}; основание: {during_canary}")


class CanaryInterrupted(BaseException):
    def __init__(self, signum: int):
        self.signum = signum


@contextmanager
def _interrupt_on_signal(signums=(signal.SIGTERM, signal.SIGHUP)):
    # `signums` — родитель параллельного прогона добавляет SIGINT: иначе
    # Ctrl-C пришёл бы `KeyboardInterrupt`, неотличимым от исключения не по
    # сигналу, и код выхода «128 + номер сигнала» был бы потерян.
    previous = {signum: signal.getsignal(signum) for signum in signums}

    def interrupt(signum, _frame):
        # Повторный сигнал не должен прервать finally посреди уборки.
        signal.signal(signum, signal.SIG_IGN)
        raise CanaryInterrupted(signum)

    try:
        for signum in previous:
            signal.signal(signum, interrupt)
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def cmd_canary(*, k: int, sha: str | None = None,
               set_name: str = config.CANARY_DEFAULT_SET,
               templates: list | None = None,
               on_run_stamp=None, parallel: bool = False) -> str:
    """`set_name` (SPEC 01M3FQ2Z2PY0E9T5F5WQ207NP5, требование 1) — имя
    набора ролей прогона из `canary_sets:` локального слоя; значение по
    умолчанию — набор по умолчанию, то есть прогон «как пульт».

    `templates` (01M3HJQV2QV9BXNXSH3F8STAYH, требования 1-4) — стабильные
    имена шаблонов пула (имя файла без `.md`) в порядке прогона: прогон
    берёт из пула ровно их, без случайной выборки. `None` (по умолчанию) —
    выбор прежний, случайная выборка `k` шаблонов из пула, байт-в-байт как
    до этой задачи: развилка ровно одна и стоит здесь, прежняя ветка не
    переписана.

    `on_run_stamp` (SPEC 01M5C6QA6S3RY9PS4H9ZJ58WQ0, требования 1, 9) —
    приёмник `run_stamp` прогона: зовётся `on_run_stamp(run_stamp)` после
    записи реестра и до первого клона, чтобы вызывающий (файл результата
    отвязанного запуска) знал свой прогон и на обрыве. Возврат —
    `run_stamp`.

    `parallel` (SPEC 01M5H24PZXZTBM03SF6V576S5P) — задачи прогона идут
    отдельными процессами `canary run-task` (`_cmd_canary_parallel`).
    Развилка одна и стоит после разбора набора: прежняя ветка ниже не
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
    if parallel:
        return _cmd_canary_parallel(pool_dir, templates, plan, sha,
                                    on_run_stamp)
    # Вход Codex для клона — здесь же, на той же стадии (SPEC
    # 01M3HST1381E1FZCYAN2TSB1F3, требование 3): за неподготовленный
    # отдельный профиль пульт тоже не платит ни сетью, ни `git clone`, ни
    # заведённой задачей. Профиль канарейки (SPEC 01M3V4ZPB6HFDJ36MTDAQG5VNT)
    # держится замком `_locked_canary_profile` до конца прогона, адрес входа
    # собирает `_canary_profile_auth`; `_codex_clone_auth` штатно не
    # зовётся. Без ролей Codex профиль не трогается вовсе.
    profile_context = (_locked_canary_profile() if plan.codex_roles
                       else nullcontext(None))
    with profile_context as profile_home:
        codex_auth = (_canary_profile_auth(plan, profile_home)
                      if profile_home is not None else None)

        target_sha, origin_sha = _resolve_target_sha(sha)
        sha_label = _target_origin_note(sha, target_sha, origin_sha)

        run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        # Реестр — внутри перехвата сигналов: сигнал на любом участке
        # прогона, включая саму запись, снимает запись и метку `finally`
        # менеджера (SPEC 01M5C6QA6S3RY9PS4H9ZJ58WQ0, требование 1).
        try:
            with _interrupt_on_signal(), _live_run_record(
                    run_stamp, target_sha, plan.name, len(templates)):
                if on_run_stamp is not None:
                    on_run_stamp(run_stamp)
                # Требование 5: имена выбранных шаблонов в порядке прогона — в
                # САМОЙ первой строке вывода, до первого эфемерного клона.
                # Иначе состав прогона Оператор узнавал бы по мере того, как
                # задачи одна за другой доходят до конца, то есть через
                # десятки минут, а при падении первого же клона — не узнал бы
                # вовсе.
                print(f"[canary] прогон {run_stamp}: {len(templates)} задач из "
                      f"пула {pool_dir} в порядке прогона: "
                      f"{', '.join(p.stem for p in templates)}; целевой sha "
                      f"{target_sha} ({sha_label}), набор "
                      f"{plan.name}{_summary_note(plan)}")
                for template_path in templates:
                    try:
                        _run_one_task(template_path, run_stamp,
                                      config.CANARY_DEVIATION_RATIO,
                                      target_sha, sha_label, plan, codex_auth)
                    except CanaryInterrupted as exc:
                        note = (f"оборвана сигналом "
                                f"{signal.Signals(exc.signum).name}")
                        store.insert_canary_run(
                            store.db(), run_stamp, template_path.stem, None,
                            0, 0.0, 0, 0, note, None, False, False,
                            main_sha=target_sha, verdict="red",
                            set_name=plan.name,
                            models_summary=plan.summary or None)
                        raise SystemExit(128 + exc.signum) from None
        except CanaryInterrupted as exc:
            # Сигнал вне ведения задачи (запись реестра, первая строка) —
            # тот же код выхода, строки прогона нет: ни одна задача не шла.
            raise SystemExit(128 + exc.signum) from None
        print(f"[canary] прогон {run_stamp} завершён")
        return run_stamp


# Параллельный прогон (SPEC 01M5H24PZXZTBM03SF6V576S5P). Задачи — отдельными
# процессами: `_ephemeral_clone` переадресует модульные пути `config`
# процесса, двух клонов в одном процессе не бывает. Предел — два: замок
# полных прогонов тестов (`suite_lock.directory`) считается от каталога
# журналов, а в клоне тот переадресован, и прогоны клонов друг друга не ждут.
PARALLEL_CHILD_LIMIT = 2
# Срок между SIGTERM группам дочерних и SIGKILL. Дочерний по SIGTERM сам
# снимает группу ведения в клоне (`liveness.terminate_process_group`, срок
# `GROUP_TERMINATE_GRACE_SEC`) и пишет строку «оборвана сигналом» — срок
# берётся с запасом больше двух таких.
PARALLEL_STOP_GRACE_SEC = 60
# Попытки записи строки «оборвана сигналом» дочерним. Попытка — до трёх
# ожиданий блокировки по 5 с (миграция в `store.db()`, обновление таблиц
# канарейки, вставка): все попытки и снятие группы ведения обязаны уложиться
# в `PARALLEL_STOP_GRACE_SEC` (SPEC 01M5MVG2B1YGVPTZWKB18EVGHZ, AC-5).
CHILD_ROW_WRITE_ATTEMPTS = 3
_PARALLEL_SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)


class _Child:
    """Запущенный дочерний процесс параллельного прогона."""

    def __init__(self, template_path: Path, proc, log_path: Path):
        self.template_path = template_path
        self.title = template_path.stem
        self.proc = proc
        self.log_path = log_path
        self.killed = False


def _child_argv(run_stamp: str, template_path: Path, target_sha: str,
                plan: CanarySetPlan) -> list:
    """argv дочернего: подкоманда `canary run-task` интерпретатором пульта
    без буферизации — как `artel._detach_canary`: вывод идёт в файл, и
    снятие сигналом не должно терять последние строки."""
    return [sys.executable, "-u",
            str(Path(__file__).resolve().with_name("artel.py")),
            "canary", "run-task", "--stamp", run_stamp,
            "--template", str(template_path), "--sha", target_sha,
            "--set", plan.name, "--summary", plan.summary or ""]


def _wait_child(proc) -> int:
    """Ожидание завершения дочернего — код выхода (отрицательный — номер
    сигнала). Зовётся потоком-ожидателем родителя."""
    return proc.wait()


def _has_run_row(run_stamp: str, title: str) -> bool:
    return any(row["run_stamp"] == run_stamp and row["title"] == title
               for row in store.all_canary_runs(store.db()))


def _report_child_failure(run_stamp: str, title: str, plan: CanarySetPlan,
                          reason: str) -> None:
    """Красная строка родителя за шаблон без своей строки прогона — по
    образцу `_report_drive_failure`: нули, коммит пуст; задачи и маркера
    ожидания эскалации родитель не знает. Причина — в выводе, не в БД."""
    store.insert_canary_run(
        store.db(), run_stamp, title, None, 0, 0.0, 0, 0,
        _DRIVE_FAILED_OUTCOME, None, False, False, main_sha=None,
        verdict="red", set_name=plan.name,
        models_summary=plan.summary or None)
    print(f"[canary] {title}: учебная задача шаблона {title} не доведена — "
          f"{reason}; прогон красный")


def _signal_group(child: _Child, signum: int) -> None:
    # Пожатый (потоком-ожидателем) процесс — его номер группы уже может
    # носить чужая группа.
    if child.proc.returncode is not None:
        return
    try:
        os.killpg(child.proc.pid, signum)
    except (ProcessLookupError, PermissionError):
        pass


def _stop_children(children: list) -> None:
    """SIGTERM группам всех сразу, общий срок `PARALLEL_STOP_GRACE_SEC`,
    SIGKILL не успевшим, ожидание всех. Зовётся под `_SignalDeferral`."""
    for child in children:
        _signal_group(child, signal.SIGTERM)
    deadline = time.monotonic() + PARALLEL_STOP_GRACE_SEC
    for child in children:
        try:
            child.proc.wait(timeout=max(0.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
    for child in children:
        if child.proc.returncode is None:
            child.killed = True
            _signal_group(child, signal.SIGKILL)
    for child in children:
        child.proc.wait()


def _finish_child(child: _Child, run_stamp: str, plan: CanarySetPlan,
                  live_dir: Path, reason: str | None = None) -> bool:
    """Итог завершившегося дочернего: блок вывода целиком, снятие его
    записи реестра (снятый SIGKILL сам её не убрал; метка — родителя и
    остаётся), красная строка, если своей строки шаблон не записал.
    `True` — задача прошла: код 0 и строка прогона есть."""
    code = child.proc.returncode
    print(f"[canary] {child.title}: процесс {child.proc.pid} завершён с кодом "
          f"{code}, журнал {child.log_path}")
    try:
        text = child.log_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        text = f"журнал не читается: {exc}\n"
    if text:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
    sys.stdout.flush()
    record = live_dir / f"{run_stamp}-{child.proc.pid}{_LIVE_RECORD_SUFFIX}"
    record.unlink(missing_ok=True)
    record.with_name(record.name + ".tmp").unlink(missing_ok=True)
    if _has_run_row(run_stamp, child.title):
        return code == 0 and reason is None and not child.killed
    if child.killed:
        killed = (f"снят SIGKILL после {PARALLEL_STOP_GRACE_SEC} с; группа "
                  f"ведения в клоне могла остаться — проверь doctor")
        reason = killed if reason is None else f"{reason}; {killed}"
    elif reason is None:
        reason = f"процесс задачи завершился с кодом {code} без строки прогона"
    _report_child_failure(run_stamp, child.title, plan, reason)
    return False


def _start_child(template_path: Path, run_stamp: str, target_sha: str,
                 plan: CanarySetPlan) -> _Child:
    """Журнал открывает родитель: файл переживает прогон и читается целиком
    по завершении процесса. Своя группа — чтобы снять и ведение в клоне;
    без оболочки — дочерний сверяет метку с `os.getppid()`."""
    directory = config.LOGS / "canary"
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / f"{run_stamp}-{template_path.stem}.log"
    with open(log_path, "wb", buffering=0) as log:
        proc = subprocess.Popen(
            _child_argv(run_stamp, template_path, target_sha, plan),
            cwd=config.ROOT, stdin=subprocess.DEVNULL, stdout=log,
            stderr=subprocess.STDOUT, start_new_session=True)
    return _Child(template_path, proc, log_path)


def _run_children(templates: list, run_stamp: str, target_sha: str,
                  plan: CanarySetPlan) -> bool:
    """Очередь дочерних: не больше `PARALLEL_CHILD_LIMIT` живых, следующий —
    по завершении любого; исход дочернего очередь не останавливает. `True`
    — все задачи прошли.

    Каждого дочернего ждёт свой поток через `_wait_child`, исход — в общую
    очередь; главный поток ждёт её, и сигнал (`CanaryInterrupted`) его
    прерывает. Запуск и разбор исхода — под `_SignalDeferral`: дочерний,
    созданный, но ещё не учтённый, сигнал оставил бы сиротой.

    На любом выходе, кроме штатного, живые дочерние снимаются
    `_stop_children` под откладыванием сигналов; пришедший во время
    остановки сигнал заново не поднимается: если родитель выходил не по
    сигналу, выход становится `CanaryInterrupted` этого сигнала, иначе
    код выхода — первого."""
    live_dir = _live_dir()
    pending = list(templates)
    running: list = []
    outcomes = queue.Queue()
    passed = True

    def wait(child: _Child) -> None:
        try:
            outcomes.put((child, _wait_child(child.proc), None))
        except BaseException as exc:  # noqa: BLE001 — исход в главный поток
            outcomes.put((child, None, exc))

    try:
        while pending or running:
            while pending and len(running) < PARALLEL_CHILD_LIMIT:
                template_path = pending.pop(0)
                deferral = _SignalDeferral()
                try:
                    try:
                        child = _start_child(template_path, run_stamp,
                                             target_sha, plan)
                    except Exception as exc:  # noqa: BLE001 — красная строка
                        passed = False
                        _report_child_failure(
                            run_stamp, template_path.stem, plan,
                            f"процесс задачи не запущен: {exc}")
                        continue
                    running.append(child)
                    threading.Thread(target=wait, args=(child,),
                                     daemon=True).start()
                finally:
                    deferral.release()
            if not running:
                continue
            child, _code, error = outcomes.get()
            if error is not None and not isinstance(error, Exception):
                raise error
            deferral = _SignalDeferral()
            try:
                reason = None
                if error is not None:
                    reason = f"ожидание процесса задачи прервано: {error}"
                    _stop_children([child])
                running.remove(child)
                passed = _finish_child(child, run_stamp, plan, live_dir,
                                       reason) and passed
            finally:
                deferral.release()
    except BaseException as exc:
        if not running:
            raise
        deferral = _SignalDeferral()
        try:
            _stop_children(running)
            for child in running:
                _finish_child(child, run_stamp, plan, live_dir)
        finally:
            late, deferral.pending = deferral.pending, None
            deferral.release()
        if late is not None and not isinstance(exc, CanaryInterrupted):
            raise CanaryInterrupted(late) from exc
        raise
    return passed


def _cmd_canary_parallel(pool_dir: Path, templates: list, plan: CanarySetPlan,
                         sha: str | None, on_run_stamp) -> str:
    """Родитель параллельного прогона (SPEC 01M5H24PZXZTBM03SF6V576S5P,
    требования 2-6): один раз — проверки, проверяемый sha, `run_stamp`,
    запись реестра и первая строка; задачи — дочерними `canary run-task`
    (`_run_children`). Запись и метка снимаются прежним `_live_run_record`
    после завершения всех дочерних: пока жив хоть один, окно тишины держит
    и запись родителя."""
    if plan.codex_roles:
        sys.exit(f"canary: --parallel недоступен для набора {plan.name}: роли "
                 f"{', '.join(plan.codex_roles)} на провайдере codex — "
                 f"профиль Codex канарейки один на машину; веди прогон без "
                 f"--parallel")
    names = [p.stem for p in templates]
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        sys.exit(f"canary: --parallel: имена шаблонов повторяются: "
                 f"{', '.join(repeated)} — журнал и строка прогона ключуются "
                 f"именем шаблона")
    target_sha, origin_sha = _resolve_target_sha(sha)
    sha_label = _target_origin_note(sha, target_sha, origin_sha)
    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    try:
        with _interrupt_on_signal(_PARALLEL_SIGNALS), _live_run_record(
                run_stamp, target_sha, plan.name, len(templates)):
            if on_run_stamp is not None:
                on_run_stamp(run_stamp)
            print(f"[canary] прогон {run_stamp}: {len(templates)} задач из "
                  f"пула {pool_dir} в порядке прогона: "
                  f"{', '.join(names)}; целевой sha {target_sha} "
                  f"({sha_label}), набор {plan.name}{_summary_note(plan)} "
                  f"параллельно: не более {PARALLEL_CHILD_LIMIT} процессов",
                  flush=True)
            passed = _run_children(templates, run_stamp, target_sha, plan)
    except CanaryInterrupted as exc:
        raise SystemExit(128 + exc.signum) from None
    print(f"[canary] прогон {run_stamp} завершён")
    if not passed:
        sys.exit(f"canary: прогон {run_stamp} красный — не все задачи "
                 f"завершились с кодом 0 со строкой прогона")
    return run_stamp


def _write_child_record(record: Path, run_stamp: str, target_sha: str,
                        set_name: str, template: str) -> None:
    """Запись дочернего процесса прогона (SPEC 01M5FZ9G7ME2F1T5TYEWSVNA1R,
    требование 3) приёмом `_live_run_record`: временный `.json.tmp` вне
    маски `*.json`, затем атомарная замена. Метку не создаёт — она
    родителя."""
    pid = os.getpid()
    started = _stale_cycles().process_start_time(pid)
    payload = {"pid": pid, "process_start": _moment_text(started),
               "run_stamp": run_stamp, "sha": target_sha,
               "set_name": set_name,
               "started_at": datetime.now(timezone.utc).isoformat(),
               "tasks": 1, "parent_pid": os.getppid(), "template": template}
    tmp = record.with_name(record.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, record)


def _mark_owned_by_parent(mark: Path) -> bool:
    try:
        owner = mark.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    return owner == str(os.getppid())


def _insert_interrupted_row(run_stamp: str, title: str, note: str,
                            target_sha: str, plan: CanarySetPlan) -> None:
    """Строка «оборвана сигналом» дочернего (SPEC 01M5MVG2B1YGVPTZWKB18EVGHZ,
    требование 2). Оба дочерних пишут её одновременно — `OperationalError`
    («database is locked») повторяется без паузы: ожидание уже даёт таймаут
    блокировки соединения, а все попытки обязаны уложиться в
    `PARALLEL_STOP_GRACE_SEC`. Соединение — новое в каждой попытке: сбой
    бывает и при его открытии (миграция). Иное исключение не повторяется."""
    for attempt in range(1, CHILD_ROW_WRITE_ATTEMPTS + 1):
        try:
            store.insert_canary_run(
                store.db(), run_stamp, title, None,
                0, 0.0, 0, 0, note, None, False, False,
                main_sha=target_sha, verdict="red",
                set_name=plan.name,
                models_summary=plan.summary or None)
            return
        except sqlite3.OperationalError:
            if attempt == CHILD_ROW_WRITE_ATTEMPTS:
                raise


def cmd_canary_run_task(*, run_stamp: str, template_path: Path,
                        target_sha: str, set_name: str, summary: str) -> None:
    """`canary run-task` — одна задача прогона `run_stamp` в отдельном
    процессе (SPEC 01M5FZ9G7ME2F1T5TYEWSVNA1R, требования 1-3). Внутренняя:
    её зовёт родитель параллельного прогона, который уже разрешил sha,
    выбрал шаблоны и держит метку `<run_stamp>.lock`; поэтому здесь нет ни
    обращения к origin, ни выбора шаблонов, ни своей метки.

    Двух эфемерных клонов в одном процессе не бывает (`_ephemeral_clone`
    переадресует модульные пути `config`), поэтому на процесс — ровно одна
    задача. Профиль Codex канарейки один на машину — набор с ролями Codex
    отдельным процессом не ведётся.

    Всё тело под `_interrupt_on_signal`: сигнал на любом участке снимает
    свою запись в `finally`; строку «оборвана сигналом» пишет только сигнал
    во время ведения задачи. Пути записи запомнены до клона — во время
    ведения `config.ROOT` уведён на клон.

    `target_sha` — полный sha, разрешённый родителем (SPEC
    01M5H24PZXZTBM03SF6V576S5P, требование 4): иное значение — отказ до
    записи реестра, клон с таким sha вёл бы не проверяемый коммит."""
    if not SHA_FORM.fullmatch(target_sha):
        sys.exit(f"canary run-task: --sha {target_sha} — не полный "
                 f"40-символьный sha")
    title = template_path.stem
    directory = _live_dir()
    record = directory / f"{run_stamp}-{os.getpid()}{_LIVE_RECORD_SUFFIX}"
    mark = directory / f"{run_stamp}{_LIVE_MARK_SUFFIX}"
    try:
        with _interrupt_on_signal():
            try:
                plan = _set_plan(set_name)
                if plan.codex_roles:
                    sys.exit(f"canary run-task: набор {plan.name} с ролями на "
                             f"провайдере codex не ведётся отдельным "
                             f"процессом — профиль Codex канарейки один на "
                             f"машину")
                directory.mkdir(parents=True, exist_ok=True)
                _write_child_record(record, run_stamp, target_sha, set_name,
                                    title)
                if not _mark_owned_by_parent(mark):
                    sys.exit(f"canary run-task: метка прогона {run_stamp} не "
                             f"принадлежит родителю {os.getppid()}")
                if plan.summary != summary:
                    store.insert_canary_run(
                        store.db(), run_stamp, title, None, 0, 0.0, 0, 0,
                        _DRIVE_FAILED_OUTCOME, None, False, False,
                        main_sha=None, verdict="red", set_name=set_name,
                        models_summary=summary or None)
                    sys.exit(f"canary run-task: {title}: набор изменился во "
                             f"время прогона — сводка набора {set_name} "
                             f"«{plan.summary}», передана «{summary}»; "
                             f"прогон красный")
                try:
                    _run_one_task(template_path, run_stamp,
                                  config.CANARY_DEVIATION_RATIO, target_sha,
                                  None, plan, None)
                except CanaryInterrupted as exc:
                    note = f"оборвана сигналом {signal.Signals(exc.signum).name}"
                    try:
                        _insert_interrupted_row(run_stamp, title, note,
                                                target_sha, plan)
                    except Exception as write_exc:  # noqa: BLE001 — в журнал
                        sys.stderr.write(
                            f"[canary] {title}: строка прогона не записана: "
                            f"{write_exc!r}\n{traceback.format_exc()}")
                        sys.stderr.flush()
                    raise SystemExit(128 + exc.signum) from None
            finally:
                record.unlink(missing_ok=True)
                record.with_name(record.name + ".tmp").unlink(missing_ok=True)
    except CanaryInterrupted as exc:
        raise SystemExit(128 + exc.signum) from None
