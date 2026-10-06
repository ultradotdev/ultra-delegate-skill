from dataclasses import dataclass
from decimal import Decimal

from .errors import UnknownSku
from .money import to_money


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    unit_price: Decimal
    tax_rate: Decimal


class Catalog:
    def __init__(self):
        self._products = {}

    def add(self, sku, name, unit_price, tax_rate='0'):
        if sku in self._products:
            raise ValueError(f'duplicate sku {sku!r}')
        if isinstance(tax_rate, float):
            raise TypeError('use str or Decimal for tax rates, not float')
        product = Product(sku, name, to_money(unit_price), Decimal(tax_rate))
        self._products[sku] = product
        return product

    def get(self, sku):
        try:
            return self._products[sku]
        except KeyError:
            raise UnknownSku(sku) from None
