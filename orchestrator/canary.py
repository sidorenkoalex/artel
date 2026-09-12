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

Каждый шаблон пула, использованный боевым прогоном, обязан нести
метку `canary-guid: <значение>` (HTML-комментарием, тем же приёмом, что
и маркер эскалации выше) — требование 7: CI-джоб пульта (`.github/
workflows/ci.yml`, приложение к PLAN.md этой задачи — путь защищённый)
отклоняет коммит/PR, если эта метка обнаружена в `skills/`, `templates/`
или `docs/` пульта. Содержание/создание конкретных шаблонов — вне
объёма этой задачи («Не входит» SPEC); эта метка нужна коду задачи
только КАК ФОРМАТ-ДОКУМЕНТАЦИЯ для Оператора/ассистента, руками
пишущих пул, — сам код `canary.py` её не читает и не проверяет.

`canary pool-seal`/восстановление пула (SPEC 01M1NSR5M5THYRC0RFWPMVE2DW,
часть 2) — отдельная от прогона конвейера механика, живущая здесь же:
пул шифруется ОДНИМ файлом `canary/pool.sealed` в репозитории пульта
(`openssl enc -aes-256-cbc -pbkdf2` + отдельный тег HMAC-SHA256 поверх
шифртекста), ключ — в keychain пульта; `init`/`doctor --restore`
расшифровывают его обратно в `~/.artel-canary`, если каталог
отсутствует. Расшифровка недоступна ролям (`runner.in_role_environment`)
— см. секцию кода перед `_pool_dir` ниже.

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
import hashlib
import hmac
import io
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

from scripts import guard

from . import (alerts, answer, artifact_branch, artifact_source, artifacts,
              auto, catalog, cleanup, config, fsm, gitcmd, keychain, runner,
              store, workspace, yamlmini)

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


def _pool_dir() -> Path:
    return Path.home() / config.CANARY_POOL_DIRNAME


# --- пул канарейки в репозитории в зашифрованном виде (SPEC
#     01M1NSR5M5THYRC0RFWPMVE2DW) ------------------------------------------
#
# `canary pool-seal` берёт открытый пул `~/.artel-canary` и кладёт его
# ОДНИМ файлом `canary/pool.sealed` в репозиторий пульта (требование 1-2);
# `init`/`doctor --restore` расшифровывают его обратно, если каталог
# отсутствует (требование 3). Симметричное шифрование — внешней командой
# `openssl enc -aes-256-cbc -pbkdf2` (не AEAD — `openssl enc` эмпирически
# не умеет AEAD-шифры, ANSWER-1 п.1) плюс отдельный тег HMAC-SHA256 по
# шифртексту (`openssl dgst -sha256 -hmac`, encrypt-then-MAC руками);
# ключ HMAC — SHA-256 от ключа пула с суффиксом `:mac` (один слот
# keychain на оба назначения ключа, ANSWER-1 п.1). Формат `pool.sealed`:
# первые `_TAG_HEX_LEN` (64) байт — тег HMAC-SHA256 в hex ASCII, дальше —
# шифртекст целиком; тег сверяется `hmac.compare_digest` ДО обращения к
# `openssl enc -d` (AC-1: файл с неверным тегом не расшифровывается).
#
# Ключ пула — в keychain пульта тем же механизмом, что токены ролей
# (`orchestrator/keychain.py::token`, слот `config.CANARY_POOL_KEY_SLOT`,
# ANSWER-1 п.3), в репозиторий и в окружение роли не попадает (AC-17).
#
# Расшифровка — ЕДИНАЯ точка входа `_authorized_pool_payload` для ОБОИХ
# путей (`restore_pool_if_missing`, `pool_drift_warning`): роль
# запущенного процесса (`runner.in_role_environment`) проверяется здесь
# независимо от того, какая команда её вызвала (требование 5, AC-15 —
# «второй, независимый от permissions.deny рубеж», не только запрет
# самой команды в курируемом слое роли, `docs/reference/role-home/
# claude/settings.json`).

SEALED_REL = ("canary", "pool.sealed")
GUIDS_REL = ("canary", "guids.txt")
_TAG_HEX_LEN = 64  # длина hex-представления HMAC-SHA256 (32 байта -> 64 hex)


def sealed_path() -> Path:
    return config.ROOT.joinpath(*SEALED_REL)


def guids_path() -> Path:
    return config.ROOT.joinpath(*GUIDS_REL)


def _mac_key(pool_key: str) -> str:
    """Ключ HMAC, детерминированно выведенный из ключа пула (ANSWER-1
    п.1) — один слот keychain несёт материал для обоих назначений."""
    return hashlib.sha256((pool_key + ":mac").encode("utf-8")).hexdigest()


@contextmanager
def _secret_fd(secret: str):
    """Отдаёт значение через файловый дескриптор наследуемого пайпа
    (`fd:N` — `openssl enc -pass fd:N`), не аргументом командной строки:
    REVIEW.md итерации 1, R1-F1 — секрет-аргумент виден в выводе
    `ps`/`ps aux` любому процессу того же пользователя на время жизни
    подпроцесса. Проверено эмпирически на этой машине (`openssl enc
    -pass fd:N` роундтрипит корректно, LibreSSL)."""
    r, w = os.pipe()
    os.write(w, secret.encode("utf-8"))
    os.close(w)
    try:
        yield r
    finally:
        os.close(r)


def _hmac_tag_hex(data: bytes, mac_key: str) -> str:
    """`openssl dgst -hmac key` — единственный CLI-путь на этой машине,
    добавляющий тег HMAC-SHA256 внешней командой (ANSWER-1 п.1): в
    отличие от `openssl enc`, `dgst` не несёт `-passin`/`fd:`/`env:`-
    аналога для `-hmac` (проверено эмпирически: `openssl dgst -help` не
    называет такой опции; `openssl mac` — команда OpenSSL 3.x, на этой
    LibreSSL её нет вовсе), а локальный приёмочный тест `tasks/
    01M1NSR5M5THYRC0RFWPMVE2DW/acceptance_tests/test_pool_seal.py::
    test_ac1_...` (залочен) буквально требует подстроку `-hmac` в argv
    вызова. Значение `mac_key` поэтому неизбежно видно в `ps`/`ps aux`
    на время жизни этого подпроцесса (REVIEW.md итерации 1, R1-F1,
    открытый остаток) — сам ключ пула здесь не используется (только
    производный `_mac_key`), сужая практическую цену утечки до подделки
    тега целостности, не расшифровки пула."""
    proc = subprocess.run(
        ["openssl", "dgst", "-sha256", "-hmac", mac_key, "-r"],
        input=data, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"canary: openssl dgst отказал: "
            f"{proc.stderr.decode('utf-8', errors='replace').strip()}")
    return proc.stdout.decode("ascii").split()[0]


def _openssl_encrypt(data: bytes, key: str) -> bytes:
    with _secret_fd(key) as fd:
        proc = subprocess.run(
            ["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-pass", f"fd:{fd}"],
            input=data, capture_output=True, pass_fds=(fd,))
    if proc.returncode != 0:
        raise RuntimeError(
            f"canary: openssl enc отказал: "
            f"{proc.stderr.decode('utf-8', errors='replace').strip()}")
    return proc.stdout


def _openssl_decrypt(data: bytes, key: str) -> bytes | None:
    """None — openssl отказал (неверный ключ/битые данные): решает
    вызывающий, у которого есть контекст для именованного отказа."""
    with _secret_fd(key) as fd:
        proc = subprocess.run(
            ["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-pass",
             f"fd:{fd}"],
            input=data, capture_output=True, pass_fds=(fd,))
    if proc.returncode != 0:
        return None
    return proc.stdout


def _serialize_pool(files: list) -> bytes:
    """Байты пула: имя+содержимое КАЖДОГО файла, длиной-с-префиксом —
    свой формат вместо `tarfile`/`zipfile` (нет временных меток/прав
    доступа, которые сделали бы шифртекст менее предсказуемым без
    выигрыша: восстановление всё равно идёт по именам файлов, не по
    метаданным архива)."""
    buf = io.BytesIO()
    for f in files:
        name_bytes = f.name.encode("utf-8")
        content_bytes = f.read_bytes()
        buf.write(struct.pack(">I", len(name_bytes)))
        buf.write(name_bytes)
        buf.write(struct.pack(">Q", len(content_bytes)))
        buf.write(content_bytes)
    return buf.getvalue()


def _deserialize_pool(payload: bytes) -> dict:
    files = {}
    offset = 0
    total = len(payload)
    while offset < total:
        (name_len,) = struct.unpack_from(">I", payload, offset)
        offset += 4
        name = payload[offset:offset + name_len].decode("utf-8")
        offset += name_len
        (content_len,) = struct.unpack_from(">Q", payload, offset)
        offset += 8
        content = payload[offset:offset + content_len]
        offset += content_len
        files[name] = content
    return files


def _authorized_pool_payload(*, audit_conn=None):
    """Расшифровывает `canary/pool.sealed`, если вызов легитимен.
    Возвращает `(payload, refusal)` — ровно один из двух не `None`.
    `refusal is None` и `payload is None` вместе означает «расшифровывать
    нечего» (sealed ещё не создан) — не ошибка вызывающего.

    `audit_conn` — соединение БД для алерта аудита `kind=incident`
    (требование 5): передаётся только вызовом ВОССТАНОВЛЕНИЯ
    (`restore_pool_if_missing`), не рутинной сверкой расхождения
    (`pool_drift_warning`) — последняя не кладёт пул на диск, аудит
    относится к самой команде расшифровки, не к каждому internal-чтению
    ради сравнения.
    """
    if runner.in_role_environment():
        return None, (
            "canary: расшифровка пула отказана — вызов из окружения роли "
            "(role_env), требование 5 SPEC 01M1NSR5M5THYRC0RFWPMVE2DW")
    sealed = sealed_path()
    if not sealed.is_file():
        return None, None
    key = keychain.token(config.CANARY_POOL_KEY_SLOT)
    if not key:
        return None, (
            f"canary: расшифровка пула отказана — ключ не найден в "
            f"keychain (слот {config.CANARY_POOL_KEY_SLOT!r})")
    if audit_conn is not None:
        alerts.raise_alert(
            audit_conn, None, "incident", "canary.pool-decrypt",
            "вызов расшифровки пула канарейки (canary/pool.sealed), "
            "требование 5 SPEC 01M1NSR5M5THYRC0RFWPMVE2DW")
    sealed_bytes = sealed.read_bytes()
    if len(sealed_bytes) < _TAG_HEX_LEN:
        return None, "canary: canary/pool.sealed повреждён (короче тега HMAC)"
    tag_hex = sealed_bytes[:_TAG_HEX_LEN]
    ciphertext = sealed_bytes[_TAG_HEX_LEN:]
    expected_tag_hex = _hmac_tag_hex(ciphertext, _mac_key(key)).encode("ascii")
    if not hmac.compare_digest(tag_hex, expected_tag_hex):
        return None, (
            "canary: восстановление пула отказано — тег HMAC не совпал, "
            "файл canary/pool.sealed повреждён")
    payload = _openssl_decrypt(ciphertext, key)
    if payload is None:
        return None, (
            "canary: восстановление пула отказано — расшифровка openssl "
            "не удалась")
    return payload, None


def restore_pool_if_missing(conn) -> str | None:
    """`init`/`doctor --restore` (требование 3, AC-5/AC-6/AC-7): при
    отсутствии `~/.artel-canary` расшифровывает `canary/pool.sealed` в
    этот каталог; при наличии — no-op (`None`, без сообщения)."""
    pool_dir = _pool_dir()
    if pool_dir.exists():
        return None
    payload, refusal = _authorized_pool_payload(audit_conn=conn)
    if refusal is not None:
        return refusal
    if payload is None:
        return None
    files = _deserialize_pool(payload)
    pool_dir.mkdir(parents=True)
    for name, content in files.items():
        (pool_dir / name).write_bytes(content)
    return f"canary: пул восстановлен в {pool_dir} ({len(files)} шаблонов)"


def pool_drift_warning() -> str | None:
    """`doctor` (требование 3, AC-8): предупреждение, если открытый пул
    отличается от запечатанного. `None` — нечего сравнивать (пул/sealed
    отсутствуют, ключ недоступен, вызов из роли) или расхождения нет."""
    pool_dir = _pool_dir()
    if not pool_dir.is_dir() or not sealed_path().is_file():
        return None
    payload, refusal = _authorized_pool_payload()
    if refusal is not None or payload is None:
        return None
    sealed_files = _deserialize_pool(payload)
    # Тот же фильтр, что и `cmd_pool_seal`/`_sample_pool_templates`
    # (REVIEW.md итерации 1, R1-F2): без него посторонний файл в
    # `~/.artel-canary` без расширения `.md` (например, `.DS_Store`,
    # который macOS Finder кладёт в любой просмотренный каталог) даёт
    # ложное "незапечатанные правки" даже когда набор `*.md`-шаблонов
    # не менялся.
    current_files = {p.name: p.read_bytes() for p in pool_dir.iterdir()
                     if p.is_file() and p.suffix == ".md"}
    if sealed_files == current_files:
        return None
    return ("открытый пул канарейки (~/.artel-canary) разошёлся с "
           "запечатанным canary/pool.sealed — незапечатанные правки, "
           "нужен canary pool-seal")


def cmd_pool_seal() -> None:
    """`canary pool-seal` (требование 2, AC-3/AC-4): шифрует открытый пул
    `~/.artel-canary` в `canary/pool.sealed`, обновляет манифест GUID
    `canary/guids.txt` (требование 4, AC-9..AC-11); ничего не коммитит —
    коммит остаётся штатным путём Оператора (требование 2)."""
    pool_dir = _pool_dir()
    if not pool_dir.is_dir():
        sys.exit(f"canary pool-seal: каталог пула не найден: {pool_dir}")
    files = sorted(p for p in pool_dir.iterdir()
                   if p.is_file() and p.suffix == ".md")
    if not files:
        sys.exit(f"canary pool-seal: в пуле {pool_dir} нет файлов *.md")
    key = keychain.token(config.CANARY_POOL_KEY_SLOT)
    if not key:
        sys.exit(
            f"canary pool-seal: ключ пула не найден в keychain (слот "
            f"{config.CANARY_POOL_KEY_SLOT!r})")

    payload = _serialize_pool(files)
    ciphertext = _openssl_encrypt(payload, key)
    tag_hex = _hmac_tag_hex(ciphertext, _mac_key(key))
    sealed_bytes = tag_hex.encode("ascii") + ciphertext

    sealed = sealed_path()
    sealed.parent.mkdir(parents=True, exist_ok=True)
    sealed.write_bytes(sealed_bytes)

    # AC-10: значения манифеста — случайные строки, не содержимое/имена
    # шаблонов; AC-11: манифест ПЕРЕЗАПИСЫВАЕТСЯ набором ТЕКУЩИХ
    # шаблонов на каждом seal, не дописывается.
    guids = [str(uuid.uuid4()) for _ in files]
    guids_path().write_text("\n".join(guids) + "\n", encoding="utf-8")

    fingerprint = hashlib.sha256(payload).hexdigest()
    print(f"[canary] pool-seal: {len(files)} шаблонов, отпечаток "
         f"{fingerprint}")


def _sample_pool_templates(pool_dir: Path, k: int) -> list:
    """`k` случайных `*.md` шаблонов пула из доступных `N` (требование 1,
    AC-1) — не «все файлы каталога», как v1."""
    files = sorted(p for p in pool_dir.iterdir()
                   if p.is_file() and p.suffix == ".md")
    if not files:
        sys.exit(f"canary: в пуле {pool_dir} нет файлов *.md")
    if k > len(files):
        sys.exit(f"canary: --k={k} больше числа доступных шаблонов пула "
                 f"({len(files)})")
    return random.sample(files, k)


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
_CLONE_CONFIG_ATTRS = (
    "ROOT", "DB", "TASKS", "LOGS", "PROJECTS", "TARGETS",
    "ROLE_HOME", "ROLE_CONFIG_DIR", "BACKUP_MARKER", "WORKTREES",
)


@contextmanager
def _ephemeral_clone():
    """Заводит эфемерный клон пульта на время блока: собственный рабочий
    каталог, собственная БД состояния, собственный origin-заглушка
    (требование 2, AC-2) — и убирает его по выходу из блока, включая
    исключение (требование 4, AC-4). Патчит МОДУЛЬНЫЕ атрибуты
    `config.py`, через которые весь FSM-код читает пути пульта — не сам
    код FSM (см. модульный докстринг).

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

    `tempfile.mkdtemp`/`shutil.rmtree` — единственные стандартные
    способы завести/убрать временный каталог в CPython (перехватываются
    приёмочной песочницей этой задачи, `_EphemeralDirTracker`, тем же
    приёмом, каким `tempfile.TemporaryDirectory` изнутри их и зовёт).
    """
    outer_root = config.ROOT
    dest = Path(tempfile.mkdtemp(prefix="artel-canary-"))
    origin_dir = Path(tempfile.mkdtemp(prefix="artel-canary-origin-"))
    saved = {attr: getattr(config, attr) for attr in _CLONE_CONFIG_ATTRS}
    try:
        clone = subprocess.run(
            ["git", "clone", "-q", str(outer_root), str(dest)],
            capture_output=True, text=True)
        if clone.returncode != 0:
            raise RuntimeError(
                f"canary: эфемерный клон не создан: {clone.stderr.strip()}")
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
        yield dest
    finally:
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
    `action` несёт саму причину — требование 3/AC-3 идёт этим же путём)."""
    if _has_subtasks(conn, task_id):
        return "поделена"
    for r in reversed(steps):
        if r["actor"] != CANARY_MARK_ACTOR:
            continue
        if r["action"] in (_MERGE_GATE_KILL_ACTION, _VERIFYING_KILL_ACTION):
            return "штатно"
        if r["detail"] == _INCONCLUSIVE_KILL_DETAIL:
            return f"не сошлась: {r['action']}"
    return "не сошлась"


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


def _run_one_task(template_path: Path, run_stamp: str, ratio: float) -> None:
    """Полный цикл одной канареечной задачи: заводит, ведёт в собственном
    эфемерном клоне (требование 2), пишет метрики/бейзлайн в БД пульта
    СНАРУЖИ клона (требование 5, 9) и печатает итог.

    Создание задачи и её вождение — с подавленным stdout
    (`redirect_stdout`): между строкой «заведена» и остальным выводом
    иначе ложится десяток строк `store.set_state`/`cleanup.cmd_kill`.

    «Штатный исход без расхождения» (ANSWER-1.md, вариант Б) — ЕДИНСТВЕННЫЙ
    случай, где диагностика не сохраняется (требование 1, AC-4) и где
    бейзлайн/сравнение отклонений вообще применяются (требование 3,
    AC-7/AC-8): `_kill_outcome_note` отличает штатный kill на
    `merge_gate` (единственный штатный kill РЕАЛЬНОГО вождения —
    `verifying` теперь проходится синтетически, ANSWER-3.md 06.09; см.
    также недостижимую из `_drive_task` `_kill_at_verifying`, оставленную
    ради чужой планки, REVIEW.md итерации 2 R2-F1) от «не сошлась»,
    `mismatch` — расхождение маркера ожидания эскалации с фактом.
    """
    raw = template_path.read_text(encoding="utf-8")
    title = template_path.stem
    expected = _expected_escalation(raw)
    outer_root = config.ROOT

    with _ephemeral_clone():
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

    print(f"[canary] {task_id} заведена из {template_path.name}")

    outer_conn = store.db()
    # `config.ROOT` уже вне эфемерного клона (см. `_ephemeral_clone`) —
    # это HEAD главного пульта на момент прогона (ANSWER-1
    # 01M1NGFK3N6MRMYGCC09H975V3 п.2), не клона, в котором велась задача.
    main_sha = gitcmd.head_sha()
    # Возврат из merge_gate (06.09, п.2): вердикт зелёности выражен через
    # уже смерженное понятие штатного исхода прогона (`normal_outcome`/
    # `_needs_diagnostics`, вычислены выше), не через «дошла до состояния
    # merge_gate/verifying» — `verifying` с ADR-0015 не конечная точка
    # реального вождения вовсе (проходится синтетически, `_pass_verifying`).
    verdict = "green" if not _needs_diagnostics(normal_outcome, mismatch) else "red"
    store.insert_canary_run(
        outer_conn, run_stamp, title, task_id, metrics["steps"],
        metrics["cost_usd"], metrics["review_iterations"],
        len(metrics["escalations"]), metrics["outcome"],
        "yes" if expected else ("no" if expected is False else None),
        actual, mismatch, main_sha=main_sha, verdict=verdict)

    note = ""
    if not _needs_diagnostics(normal_outcome, mismatch):
        # Требование 3/AC-7/AC-8: бейзлайн заводится и сравнение отклонений
        # применяется ТОЛЬКО для штатного исхода без расхождения маркера —
        # прогон, снятый как «не сошлась», или с расхождением, в это
        # сравнение не попадает, даже если он первый для шаблона (копилка
        # 06.09: killed-прогон дважды за день ложно завёл бейзлайн).
        baseline = store.canary_baseline(outer_conn, title)
        if baseline is None:
            store.set_canary_baseline(outer_conn, title, metrics["steps"],
                                      metrics["cost_usd"],
                                      metrics["review_iterations"])
            note = "  [бейзлайн создан]"
        else:
            warnings = _task_deviation_warnings(metrics, baseline, ratio)
            if warnings:
                for w in warnings:
                    alerts.raise_alert(
                        outer_conn, task_id, "threshold", "canary",
                        f"канарейка {title} ({task_id}): {w}")
                note = "  [ВНИМАНИЕ: отклонение от бейзлайна: " + \
                    "; ".join(warnings) + "]"

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
    print(f"  {task_id}: шагов={metrics['steps']}  "
         f"${metrics['cost_usd']:.2f}  "
         f"ревью-итераций={metrics['review_iterations']}  "
         f"эскалаций={len(metrics['escalations'])}  "
         f"повторов developer={metrics['dev_retries']}  "
         f"исход={metrics['outcome']}{outcome_note}  "
         f"test_author={test_author_note}{mismatch_note}{note}")
    if diag_dir is not None:
        print(f"  диагностика: {diag_dir}")


def cmd_canary(*, k: int) -> None:
    pool_dir = _pool_dir()
    if not pool_dir.is_dir():
        sys.exit(f"canary: каталог пула не найден: {pool_dir}")
    if k <= 0:
        sys.exit("canary: --k должен быть положительным целым числом")
    templates = _sample_pool_templates(pool_dir, k)

    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    print(f"[canary] прогон {run_stamp}: {len(templates)} задач из пула "
         f"{pool_dir}")
    for template_path in templates:
        _run_one_task(template_path, run_stamp, config.CANARY_DEVIATION_RATIO)
    print(f"[canary] прогон {run_stamp} завершён")
