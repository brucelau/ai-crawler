from ai_crawler.spiders.base import EcommerceSpider, EcommerceItem, product_to_item
from ai_crawler.spiders.product import Product

EXTRACTORS = {
    site: {}
    for site in [
        "amazon",
        "walmart",
        "target",
        "ebay",
        "bestbuy",
        "lowes",
        "homedepot",
        "temu",
        "etsy",
        "wayfair",
        "kohls",
        "costco",
        "qvc",
        "michaels",
        "acehardware",
        "menards",
        "samsclub",
        "bunnings",
        "mercadolibre",
        "intexcorp",
        "meijer",
        "fivebelow",
        "dollargeneral",
        "action",
        "academy",
        "wowsports",
        "coppel",
        "aosom",
        "familydollar",
        "costway",
    ]
}

from ai_crawler.spiders.amazon import AmazonSearchSpider, AmazonDetailSpider
from ai_crawler.spiders.walmart import WalmartSpider
from ai_crawler.spiders.target import TargetSpider
from ai_crawler.spiders.ebay import EbaySpider
from ai_crawler.spiders.bestbuy import BestbuySpider
from ai_crawler.spiders.lowes import LowesSpider
from ai_crawler.spiders.homedepot import HomedepotSpider
from ai_crawler.spiders.temu import TemuSpider
from ai_crawler.spiders.etsy import EtsySpider
from ai_crawler.spiders.wayfair import WayfairSpider
from ai_crawler.spiders.kohls import KohlsSpider
from ai_crawler.spiders.costco import CostcoSpider
from ai_crawler.spiders.qvc import QvcSpider
from ai_crawler.spiders.michaels import MichaelsSpider
from ai_crawler.spiders.acehardware import AcehardwareSpider
from ai_crawler.spiders.menards import MenardsSpider
from ai_crawler.spiders.samsclub import SamsclubSpider
from ai_crawler.spiders.bunnings import BunningsSpider
from ai_crawler.spiders.mercadolibre import MercadolibreSpider
from ai_crawler.spiders.intexcorp import IntexcorpSpider
from ai_crawler.spiders.meijer import MeijerSpider
from ai_crawler.spiders.fivebelow import FivebelowSpider
from ai_crawler.spiders.dollargeneral import DollargeneralSpider
from ai_crawler.spiders.action import ActionSpider
from ai_crawler.spiders.academy import AcademySpider
from ai_crawler.spiders.wowsports import WowsportsSpider
from ai_crawler.spiders.coppel import CoppelSpider
from ai_crawler.spiders.aosom import AosomSpider
from ai_crawler.spiders.familydollar import FamilydollarSpider
from ai_crawler.spiders.costway import CostwaySpider
from ai_crawler.spiders.multi import MultiSiteSpider

__all__ = [
    "EcommerceSpider",
    "EcommerceItem",
    "Product",
    "product_to_item",
    "AmazonSearchSpider",
    "AmazonDetailSpider",
    "WalmartSpider",
    "TargetSpider",
    "EbaySpider",
    "BestbuySpider",
    "LowesSpider",
    "HomedepotSpider",
    "TemuSpider",
    "EtsySpider",
    "WayfairSpider",
    "KohlsSpider",
    "CostcoSpider",
    "QvcSpider",
    "MichaelsSpider",
    "AcehardwareSpider",
    "MenardsSpider",
    "SamsclubSpider",
    "BunningsSpider",
    "MercadolibreSpider",
    "IntexcorpSpider",
    "MeijerSpider",
    "FivebelowSpider",
    "DollargeneralSpider",
    "ActionSpider",
    "AcademySpider",
    "WowsportsSpider",
    "CoppelSpider",
    "AosomSpider",
    "FamilydollarSpider",
    "CostwaySpider",
    "MultiSiteSpider",
]
