from src.core.services.scraper.transformers import parse_card_listings

HTML = """
<html>
  <body>
    <h1 class="card-name">Blue-Eyes White Dragon</h1>
    <div class="products-container">
      <div class="row">
        <a class="ItemSet display-title">Legend of Blue Eyes White Dragon</a>
        <span>Rarity: Ultra Rare</span>
        <span>Card #:</span>
        <span>LOB-001</span>
        <span>Near Mint</span>
        <span>Only 2 In Stock</span>
        <span>$19.99</span>
      </div>
    </div>
  </body>
</html>
"""


def test_transform_card_pages_returns_card_listings() -> None:
    listings = parse_card_listings(HTML, "Blue-Eyes White Dragon")

    assert len(listings) == 1

    listing = listings[0]
    assert listing.name == "Blue-Eyes White Dragon - Legend of Blue Eyes White Dragon"
    assert listing.set == "Legend of Blue Eyes White Dragon"
    assert listing.code == "LOB-001"
    assert listing.price == "$19.99"
    assert listing.rarity == "Ultra Rare"
    assert listing.condition == "Near Mint"
    assert listing.stock == 2
