from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.routers import product_router
from app.schemas.product_schema import ProductPublic


client = TestClient(app)


def make_product(product_id: str = "product-1") -> ProductPublic:
    return ProductPublic(
        id=product_id,
        name="바지",
        price=10000,
        created_at=datetime.fromisoformat("2026-07-22T10:30:00+09:00"),
    )


def test_create_product_returns_created_product(monkeypatch):
    monkeypatch.setattr(product_router, "product_create", lambda product: make_product())

    response = client.post(
        "/product/create",
        json={"name": "바지", "price": 10000},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["id"] == "product-1"


def test_get_product_returns_404_when_missing(monkeypatch):
    monkeypatch.setattr(product_router, "product_get", lambda product_id: None)

    response = client.get("/product/get/missing-product")

    assert response.status_code == 404
    assert response.json()["detail"] == "상품 ID missing-product를 찾을 수 없습니다."


def test_get_all_products_returns_product_list(monkeypatch):
    monkeypatch.setattr(
        product_router,
        "product_get_all",
        lambda: [make_product("product-1"), make_product("product-2")],
    )

    response = client.get("/product/getall")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert len(response.json()["data"]) == 2


def test_update_product_uses_path_product_id(monkeypatch):
    received = {}

    def fake_update(product_id, product):
        received["product_id"] = product_id
        received["name"] = product.name
        received["price"] = product.price
        return make_product(product_id)

    monkeypatch.setattr(product_router, "product_update", fake_update)

    response = client.put(
        "/product/product-1",
        json={"name": "청바지", "price": 20000},
    )

    assert response.status_code == 200
    assert response.json()["data"]["id"] == "product-1"
    assert received == {
        "product_id": "product-1",
        "name": "청바지",
        "price": 20000,
    }


def test_delete_product_returns_deleted_product(monkeypatch):
    monkeypatch.setattr(product_router, "product_delete", lambda product_id: make_product(product_id))

    response = client.delete("/product/delete/product-1")

    assert response.status_code == 200
    assert response.json()["data"]["id"] == "product-1"
