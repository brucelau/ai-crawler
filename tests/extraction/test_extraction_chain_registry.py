from ai_crawler.core.extraction import SITE_EXTRACTION_CHAINS


def test_menards_has_registered_extraction_chain():
    assert "menards" in SITE_EXTRACTION_CHAINS
