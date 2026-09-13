"""Запечатанный пул шаблонов канарейки (SPEC 01M1NSR5M5THYRC0RFWPMVE2DW).

Вынесен дословным переносом из `orchestrator/canary.py` (диапазон
canary.py:181–462 до этой задачи) — SPEC 01M2CN42RV0EBBP7HS4HP2VNY1,
находка ревизии №6 CR-2026-09-13-4 ★, ТЗ-черновик Р-4: `canary.py`
держал две несвязанные области (запечатанный пул и прогон синтетического
конвейера), единственной точкой сцепления между ними была `_pool_dir()`
— она и переехала сюда вместе с остальной механикой пула. `canary.py`
импортирует этот модуль и зовёт `pool_seal._pool_dir()` там, где раньше
звал одноимённую функцию у себя.

`canary pool-seal`/восстановление пула — отдельная от прогона конвейера
механика, живущая здесь: пул шифруется ОДНИМ файлом `canary/pool.sealed`
в репозитории пульта (`openssl enc -aes-256-cbc -pbkdf2` + отдельный тег
HMAC-SHA256 поверх шифртекста), ключ — в keychain пульта; `init`/`doctor
--restore` расшифровывают его обратно в `~/.artel-canary`, если каталог
отсутствует. Расшифровка недоступна ролям (`runner.in_role_environment`)
— см. секцию кода перед `_pool_dir` ниже.
"""
import hashlib
import hmac
import io
import os
import struct
import subprocess
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

from . import alerts, config, keychain, runner


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
