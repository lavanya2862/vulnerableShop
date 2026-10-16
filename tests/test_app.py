"""Baseline functional tests. These must pass both before and after remediation."""

from tests.conftest import PUBLIC_MARKER


def test_app_starts_and_docs_available(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").json()["info"]["title"] == "VulnerableShop"


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_products_returns_seed_data(client):
    response = client.get("/products")
    assert response.status_code == 200
    names = [p["name"] for p in response.json()]
    assert len(names) == 5
    assert "Aurora Phone X" in names


def test_get_product_by_id(client):
    response = client.get("/products/1")
    assert response.status_code == 200
    assert response.json()["name"] == "Aurora Phone X"


def test_get_missing_product_returns_404(client):
    assert client.get("/products/9999").status_code == 404


def test_create_product(client):
    payload = {"name": "Comet Tablet", "description": "Fictional tablet", "price": 329.0, "stock": 5}
    response = client.post("/products", json=payload)
    assert response.status_code == 201
    created = response.json()
    assert created["name"] == "Comet Tablet"
    assert client.get(f"/products/{created['id']}").json()["price"] == 329.0


def test_create_product_rejects_invalid_price(client):
    response = client.post("/products", json={"name": "Free Thing", "price": -1})
    assert response.status_code == 422


def test_search_returns_matching_products(client):
    response = client.get("/products/search", params={"q": "phone"})
    assert response.status_code == 200
    results = response.json()
    names = {p["name"] for p in results}
    assert {"Aurora Phone X", "Pebble Phone Case"} <= names
    assert "Quartz Laptop 14" not in names
    for product in results:
        assert "phone" in (product["name"] + product["description"]).lower()


def test_search_with_no_matches_returns_empty_list(client):
    response = client.get("/products/search", params={"q": "nonexistent-item"})
    assert response.status_code == 200
    assert response.json() == []


def test_user_orders(client):
    response = client.get("/users/1/orders")
    assert response.status_code == 200
    orders = response.json()
    assert len(orders) == 2
    assert orders[0]["product_name"] == "Aurora Phone X"


def test_orders_for_missing_user_returns_404(client):
    assert client.get("/users/9999/orders").status_code == 404


def test_fetch_url_allows_allowlisted_host(client, monkeypatch, mock_server_port):
    monkeypatch.setenv("VULNSHOP_ALLOWED_FETCH_HOSTS", f"localhost:{mock_server_port}")
    response = client.post("/fetch-url", json={"url": f"http://localhost:{mock_server_port}/public"})
    assert response.status_code == 200
    assert response.json()["content"] == PUBLIC_MARKER


def test_ping_accepts_valid_host(client):
    response = client.get("/diagnostics/ping", params={"host": "127.0.0.1"})
    # 503 is acceptable on runners without a ping binary.
    assert response.status_code in (200, 503)
    if response.status_code == 200:
        assert response.json()["host"] == "127.0.0.1"
