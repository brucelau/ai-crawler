from dataclasses import asdict, dataclass


@dataclass
class Product:
    source: str = ""
    url: str = ""
    title: str = ""
    price: str = ""
    currency: str = ""
    rating: float = 0.0
    review_count: int = 0
    brand: str = ""
    description: str = ""
    images: list = None
    availability: str = ""
    asin: str = ""
    seller: str = ""
    shipping: str = ""
    category: str = ""
    extracted_at: str = ""

    def __post_init__(self):
        if self.images is None:
            self.images = []

    def to_dict(self) -> dict:
        return asdict(self)
