"""AC-17 (SPEC.md) — ключ шифрования пула не появляется ни в
репозитории пульта, ни в окружении роли (`role_env`); проверяется по
образцу T049 (`docs/reference/role-home.md`, требование 10: грep по
секретным паттернам), здесь — автоматизированным грепом реального
значения ключа-заглушки песочницы вместо ручной проверки Оператора: в
этой песочнице (в отличие от T049, где секрета с известным значением
нет) точное значение ключа известно теcту (`_sandbox.FAKE_POOL_KEY`),
и грep по нему детерминирован.

Красен до реализации: `pool-seal` не существует (см. `test_pool_seal.py`)
— `keychain.token` не запрашивается ни разу, дерево репозитория не
меняется, оба грепа в этом файле находят ноль совпадений уже сегодня
(ключ негде было бы утечь) — тест ЗЕЛЁНЫЙ С РОЖДЕНИЯ по этой причине
(см. маркер модуля ниже), не «красный до реализации»: до того, как
код вообще касается ключа, утечки быть не может.

Зелёный с рождения: до реализации `pool-seal`/восстановления ключ
никем не запрашивается и никуда не пишется — грепу нечего найти в
любом случае; тест начинает нести содержательную проверку РОВНО с
момента, когда разработчик подключает `keychain.token` к реальному
шифрованию (тот же порядок событий, что и было бы у ЗЕЛЁНОГО теста на
сохранение существующего поведения).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import runner  # noqa: E402
from _sandbox import FAKE_POOL_KEY, PoolBaseSandbox  # noqa: E402


class PoolKeyNotLeakedTest(PoolBaseSandbox):

    def test_ac17_pool_key_absent_from_repo_tree_and_from_role_env(self):
        """После `pool-seal` ни один файл дерева `config.ROOT`
        (репозиторий пульта, включая свежесозданные `canary/pool.sealed`
        и `canary/guids.txt`) не несёт значение ключа буквально, и
        `runner.role_env()` (единственная точка, формирующая окружение
        процесса роли) не несёт его ни в одном значении переменной.

        Ловит мутацию: разработчик по ошибке пишет ключ рядом с
        `pool.sealed` (например, отладочным файлом или в `guids.txt`
        как комментарий) — первый греп находит его; передача ключа
        роли через `os.environ` вместо изоляции по `role_env` —
        находит второй.
        """
        self.write_pool_templates({"a.md": "тело А\n", "b.md": "тело Б\n"})
        self.seal()

        key_bytes = FAKE_POOL_KEY.encode("utf-8")
        leaking_files = []
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            try:
                content = path.read_bytes()
            except OSError:
                continue
            if key_bytes in content:
                leaking_files.append(str(path.relative_to(self.root)))
        self.assertEqual(
            leaking_files, [],
            f"ключ шифрования пула найден в репозитории пульта: "
            f"{leaking_files}")

        env = runner.role_env()
        leaking_vars = [name for name, value in env.items()
                        if FAKE_POOL_KEY in str(value)]
        self.assertEqual(
            leaking_vars, [],
            f"ключ шифрования пула найден в окружении роли (role_env): "
            f"{leaking_vars}")


if __name__ == "__main__":
    unittest.main()
