"""AC-1, AC-3, AC-4 (SPEC.md, требования 1-2) — команда `canary
pool-seal`: берёт открытый пул из `~/.artel-canary`, кладёт его
зашифрованным `openssl`-файлом `canary/pool.sealed` в репозиторий
пульта, ничего сама не коммитит, печатает число шаблонов и отпечаток
содержимого.

AC-1: `openssl enc` эмпирически не умеет AEAD-шифры (проверено 05.09
на LibreSSL и OpenSSL 3, см. `## Эскалация` части 1 этого файла в
истории git) — ANSWER-1 п.1 решил спор вариантом (a): шифрование
`openssl enc -aes-256-cbc -pbkdf2` (без AEAD) плюс отдельный тег
HMAC-SHA256 по шифртексту через `openssl dgst -sha256 -hmac`
(encrypt-then-MAC руками); при восстановлении тег сверяется ДО
расшифровки через `hmac.compare_digest`, файл с неверным тегом не
расшифровывается. SPEC (требование 1, AC-1) уже несёт это решение
буквально — тесты ниже закрепляют его дословно, не подгонкой.

Красен до реализации: команды `canary pool-seal` сегодня нет — `canary`
принимает только каталог ТЗ v1 (`orchestrator/canary.py::cmd_canary`,
позиционный `tz_dir`) и в текущем дереве ещё не несёт код пула v2
(часть 1, 01M1NEEWH5K1XPFRDGRMPYSBXJ, в этой рабочей копии не смержена
— см. TZ.md/контекст SPEC), так что `pool-seal` как первый позиционный
аргумент либо трактуется как каталог ТЗ и падает на «каталог не
найден», либо (после мержа части 1) — «в пуле нет файлов *.md»; в
обоих случаях `canary/pool.sealed` не появляется, и `test_ac1_.../
test_ac4_...` падают на `assertTrue(self.sealed_path.exists())`/
`assertRegex` соответственно. `test_ac1_tampered_hmac_tag_refuses_
decryption_before_reading_ciphertext` падает даже раньше: без
`pool.sealed` порчи одного байта устраивать негде, `self.sealed_path.
read_bytes()` в подготовке теста падает `FileNotFoundError` — та же
причина, просто проявляется на шаге подготовки, не на финальном
`assertFalse`.

`test_ac3_pool_seal_does_not_commit_the_sealed_file_itself` — честное
исключение, ЗЕЛЁНОЕ С РОЖДЕНИЯ вакуозно: «pool-seal не вызывает git»
тривиально верно и ДО того, как pool-seal вообще существует (звать
git неоткуда — команды нет), так что этот тест начинает нести
содержательную проверку только с момента появления самой команды
(тогда мутация «разработчик добавил `git add`/`git commit` внутрь
pool-seal» покраснила бы `self.git_spy.calls`), не раньше — тот же
класс неотличимости «нет фичи» от «фича есть и корректно не коммитит»,
что и в других файлах этой планки (см. `test_pool_restore.py`, AC-7).
"""
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import PoolBaseSandbox  # noqa: E402

TEMPLATE_A = "# Шаблон А\n\nСекретный маркер тела: alpha-marker-77213.\n"
TEMPLATE_B = "# Шаблон Б\n\nСекретный маркер тела: beta-marker-90542.\n"
TEMPLATE_C = "# Шаблон В\n\nСекретный маркер тела: gamma-marker-31488.\n"


class PoolSealTest(PoolBaseSandbox):

    def setUp(self):
        super().setUp()
        self.write_pool_templates({
            "a.md": TEMPLATE_A, "b.md": TEMPLATE_B, "c.md": TEMPLATE_C})

    def test_ac1_pool_seal_writes_one_encrypted_file_via_external_openssl(self):
        """`canary pool-seal` кладёт РОВНО ОДИН файл `canary/pool.sealed`
        в корне репозитория пульта; его байты не несут открытого текста
        шаблонов (реально зашифрован); шифрование — внешней командой
        `openssl enc -aes-256-cbc -pbkdf2` (не AEAD — `openssl enc`
        эмпирически не умеет AEAD-шифры, ANSWER-1 п.1), а целостность
        шифртекста добирается ОТДЕЛЬНЫМ вызовом `openssl dgst -sha256
        -hmac` (encrypt-then-MAC руками, то же решение) — не питоновской
        крипто-библиотекой в обход требования 1 SPEC.

        Ловит мутацию: разработчик кладёт пул НЕзашифрованным (простое
        копирование каталога или конкатенация файлов) — `assertNotIn`
        по маркерам тела шаблонов ловит открытый текст; шифрование
        питоновской библиотекой (`cryptography`/`hashlib`+ручной XOR)
        вместо внешней команды, либо шифрует, но не считает отдельный
        HMAC-тег (оставляя пул без целостности) — `run_mock` не увидел
        бы соответствующего вызова `openssl enc`/`openssl dgst`, либо
        не нашёл бы в его аргументах `-aes-256-cbc`/`-pbkdf2`/`-sha256`/
        `-hmac`.
        """
        with mock.patch.object(subprocess, "run",
                              wraps=subprocess.run) as run_mock:
            output = self.seal()

        self.assertTrue(
            self.sealed_path.exists(),
            f"canary/pool.sealed не создан после pool-seal: {output}")
        self.assertTrue(self.sealed_path.is_file())
        # Ровно один файл пула в репозитории — не каталог с копиями.
        canary_repo_dir = self.sealed_path.parent
        self.assertEqual(
            [p.name for p in canary_repo_dir.iterdir() if p.is_file()
             and p.name != "guids.txt"],
            ["pool.sealed"],
            f"в {canary_repo_dir} лежит не один файл пула: "
            f"{sorted(canary_repo_dir.iterdir())}")

        sealed_bytes = self.sealed_path.read_bytes()
        for marker in ("alpha-marker-77213", "beta-marker-90542",
                      "gamma-marker-31488"):
            self.assertNotIn(
                marker.encode("utf-8"), sealed_bytes,
                f"canary/pool.sealed несёт открытый текст шаблона "
                f"({marker!r}) — пул не зашифрован")

        openssl_argvs = [
            c.args[0] for c in run_mock.call_args_list
            if c.args and isinstance(c.args[0], (list, tuple))
            and c.args[0] and Path(str(c.args[0][0])).name == "openssl"]
        self.assertTrue(
            openssl_argvs,
            f"pool-seal не вызвал внешнюю команду `openssl` (требование 1 "
            f"SPEC): зафиксированные вызовы subprocess.run: "
            f"{run_mock.call_args_list}")

        enc_argvs = [argv for argv in openssl_argvs if "enc" in argv]
        self.assertTrue(
            enc_argvs,
            f"pool-seal не вызвал `openssl enc`: {openssl_argvs}")
        enc_argv = " ".join(str(a) for a in enc_argvs[0])
        self.assertIn(
            "-aes-256-cbc", enc_argv,
            f"pool-seal не использует `-aes-256-cbc` (ANSWER-1 п.1 — "
            f"`openssl enc` не умеет AEAD-шифры): {enc_argv}")
        self.assertIn(
            "-pbkdf2", enc_argv,
            f"pool-seal не использует `-pbkdf2`: {enc_argv}")

        dgst_argvs = [argv for argv in openssl_argvs if "dgst" in argv]
        self.assertTrue(
            dgst_argvs,
            f"pool-seal не вызвал `openssl dgst` для тега HMAC "
            f"(ANSWER-1 п.1 — encrypt-then-MAC руками): {openssl_argvs}")
        dgst_argv = " ".join(str(a) for a in dgst_argvs[0])
        self.assertIn("-sha256", dgst_argv, f"тег не SHA-256: {dgst_argv}")
        self.assertIn("-hmac", dgst_argv, f"тег не HMAC: {dgst_argv}")

    def test_ac3_pool_seal_does_not_commit_the_sealed_file_itself(self):
        """`pool-seal` кладёт файл на диск, но НЕ коммитит его сама —
        требование 2 SPEC явно отделяет запись файла от коммита
        («коммит — Оператора, штатным путём»).

        Ловит мутацию: разработчик добавляет `git add`/`git commit`
        внутрь `pool-seal` «для удобства» — `self.git_spy.calls`
        (`tests.sandbox.SpyRun`, перехватывает `subprocess.run` —
        ОБЩИЙ атрибут модуля `subprocess`, тот же для `gitcmd` и для
        вызова `openssl` этой же командой, поэтому здесь фильтруются
        именно git-вызовы, а не вообще любой `subprocess.run`)
        перестанет быть пустым.
        """
        self.seal()
        git_calls = [c for c in self.git_spy.calls
                    if c and Path(str(c[0])).name == "git"]
        self.assertEqual(
            git_calls, [],
            f"pool-seal вызвал git самостоятельно: {git_calls} — коммит "
            f"принадлежит Оператору (требование 2 SPEC), не команде")

    def test_ac4_pool_seal_prints_template_count_and_content_fingerprint(self):
        """Вывод `pool-seal` называет число шаблонов пула (3 в этой
        песочнице) и несёт отпечаток (хэш) содержимого — строку из
        восьми и более hex-символов, не само число шаблонов.

        Ловит мутацию: разработчик печатает только число либо только
        отпечаток (забыл вторую половину требования 2) — один из двух
        `assertTrue`/`assertRegex` ниже падает.
        """
        output = self.seal()
        self.assertRegex(
            output, r"(?<!\d)3(?!\d)",
            f"вывод pool-seal не называет число шаблонов пула (3): {output!r}")
        hex_tokens = re.findall(r"[0-9a-f]{8,}", output.lower())
        self.assertTrue(
            hex_tokens,
            f"вывод pool-seal не несёт отпечатка (hex-хэша) содержимого "
            f"пула: {output!r}")

    def test_ac1_tampered_hmac_tag_refuses_decryption_before_reading_ciphertext(self):
        """Пул запечатан, каталог `~/.artel-canary` стёрт (тот же
        сценарий восстановления, что AC-5); ОДИН байт файла `canary/
        pool.sealed` испорчен ПОСЛЕ печати. Восстановление (`init`)
        обязано сверить тег HMAC-SHA256 ДО попытки расшифровки
        (`hmac.compare_digest`, ANSWER-1 п.1), обнаружить несовпадение
        и НЕ расшифровывать (AC-1: «файл с неверным тегом не
        расшифровывается», именованный отказ). Порча одного байта в
        ЛЮБОМ месте файла обязана сделать тег недействительным
        независимо от того, в каком порядке разработчик разложил тег и
        шифртекст внутри единственного файла пула (AC-1: «один
        зашифрованный файл»).

        Ловит мутацию: разработчик расшифровывает файл БЕЗ проверки
        тега, либо читает тег, но не влияет решением на расшифровку
        (сравнение есть, но результат игнорируется, либо `==` вместо
        `hmac.compare_digest`, что здесь эквивалентно наблюдаемому
        поведению) — тогда `~/.artel-canary` после `init` появился бы
        (пусть даже с мусором вместо исходных шаблонов) вместо того,
        чтобы остаться отсутствующим.
        """
        self.write_pool_templates({"a.md": "тело А\n", "b.md": "тело Б\n"})
        self.seal()
        shutil.rmtree(self.pool_dir)

        sealed_bytes = bytearray(self.sealed_path.read_bytes())
        self.assertTrue(sealed_bytes, "canary/pool.sealed пуст после seal")
        sealed_bytes[-1] ^= 0xFF
        self.sealed_path.write_bytes(bytes(sealed_bytes))

        output = self.restore_via_init()

        self.assertFalse(
            self.pool_dir.exists(),
            f"`init` расшифровал пул с повреждённым тегом HMAC (файл "
            f"canary/pool.sealed испорчен на 1 байт) — AC-1 нарушен: "
            f"{output!r}")
        lowered = output.lower()
        self.assertTrue(
            any(kw in lowered for kw in ("тег", "hmac")),
            f"отказ `init` на повреждённом теге не называет причину "
            f"явно (именованный отказ, AC-1): {output!r}")


if __name__ == "__main__":
    unittest.main()
