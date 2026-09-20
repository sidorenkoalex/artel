"""AC-3: разбор каталога отказывает именованной ошибкой на каждом из
четырёх случаев по отдельности.

Сломанные каталоги — текстовые мутации НАСТОЯЩЕГО `models.yaml` рабочей
копии (`_models.with_*`), а не собственная копия схемы: форму записи
каталога SPEC фиксирует лишь частично, и планка, сочинившая остальное,
краснела бы на законном варианте разработчика.

Красен до реализации: каталога `models.yaml` в корне ещё нет (его создаёт
эта задача) — фикстура-мутация падает `FileNotFoundError` на его чтении; с
каталогом, но без `orchestrator/models.py`, следующим падал бы
`ModuleNotFoundError` — оба звена приносит эта же задача.
"""
import unittest

import _models
from _sandbox import CatalogSandbox


class CatalogNamedErrorsTest(CatalogSandbox):
    """Каталог во временном корне пульта, по одной поломке за прогон."""

    def refusal(self, text: str) -> Exception:
        """Исключение разбора каталога `text`; разбор не отказал —
        провал теста с текстом критерия."""
        self.write_catalog(text)
        try:
            parsed = _models.load_catalog(self.catalog_path)
        except Exception as exc:  # noqa: BLE001 — предмет проверки
            return exc
        self.fail(f"разбор сломанного каталога не отказал, вернул: {parsed!r}")

    def assert_named(self, exc: Exception, *named: str) -> None:
        """Ошибка именованная (класс самого разбора, не голый встроенный
        отказ) и называет предмет нарушения."""
        self.assertNotEqual(
            type(exc).__module__, "builtins",
            f"отказ не именован — встроенное исключение "
            f"{type(exc).__name__}: {exc}")
        for name in named:
            self.assertIn(name, str(exc))

    def test_ac3_unknown_provider_is_refused_by_name(self):
        """Раздел провайдера, которого нет в реестре провайдеров пульта, —
        именованный отказ, называющий провайдера.

        Ловит мутацию: имя раздела не сверяется с реестром вовсе — каталог
        с опечаткой в имени провайдера («cluade») разбирается молча, а
        падает потом шаг роли, у которого модель вдруг «не найдена».
        """
        exc = self.refusal(_models.with_unknown_provider())

        self.assert_named(exc, _models.UNKNOWN_PROVIDER)

    def test_ac3_model_without_price_is_refused_by_name(self):
        """Модель без прейскуранта — именованный отказ, называющий модель.

        Ловит мутацию: отсутствующий прейскурант трактуется как пустой
        словарь (`entry.get(...) or {}`) — модель без цен доезжает до
        разрешения цепочки и отдаёт тариф-ноль вместо отказа схемы.
        """
        exc = self.refusal(_models.without_price(_models.FABLE))

        self.assert_named(exc, _models.FABLE)

    def test_ac3_incomplete_price_is_refused_by_name(self):
        """Прейскурант, где задан не весь набор из четырёх видов токенов, —
        именованный отказ, называющий модель.

        Ловит мутацию: полнота прейскуранта проверяется «хотя бы одна
        цена есть» вместо всех четырёх видов — запись без цены чтения
        кэша (самого объёмного вида токенов шага) проходит схему.
        """
        exc = self.refusal(
            _models.with_partial_price(_models.SONNET, "cache_read"))

        self.assert_named(exc, _models.SONNET)

    def test_ac3_zero_price_is_refused_by_name(self):
        """Ноль в любой из четырёх цен — именованный отказ, называющий
        модель.

        Ловит мутацию: ноль проходит проверку «цена задана» (`is not
        None`/`>= 0`) — незаполненная строка прейскуранта молча означала
        бы «бесплатно», и расход шага считался бы по нулевому тарифу.
        """
        exc = self.refusal(_models.with_zero_price(_models.OPUS, "input"))

        self.assert_named(exc, _models.OPUS)

    def test_ac3_four_cases_are_told_apart_by_the_refusal_text(self):
        """Четыре случая различимы по тексту: каждый называет свой вид
        нарушения, а не общую фразу «каталог не разобран».

        Ловит мутацию: все четыре проверки схемы свёрнуты в один текст
        отказа — Оператор видит «каталог моделей не разобран» и идёт
        искать, что именно в файле не так, вручную.
        """
        texts = [
            str(self.refusal(_models.with_unknown_provider())),
            str(self.refusal(_models.without_price(_models.FABLE))),
            str(self.refusal(_models.with_partial_price(_models.SONNET,
                                                        "cache_read"))),
            str(self.refusal(_models.with_zero_price(_models.OPUS, "input"))),
        ]

        self.assertEqual(len(set(texts)), 4,
                         "тексты отказов не различают вид нарушения:\n"
                         + "\n".join(texts))


if __name__ == "__main__":
    unittest.main()
