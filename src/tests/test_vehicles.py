# tests/test_vehicles.py
def test_create_vehicle_and_bid_flow(client, seller_headers, auth_headers):
    # seller crea vehículo
    payload = {
        "make": "Ford",
        "model": "Mustang",
        "year": 1969,
        "base_price": 200000,
        "lot_code": "TST-001",
        "images": [],
        "description": "Test car",
        "min_increment": 1000
    }
    r = client.post("/api/vehicles", json=payload, headers=seller_headers)
    assert r.status_code == 200
    v = r.get_json()["data"]
    vid = v["id"]
    assert v["basePrice"] == 200000

    # buyer login
    buyer_headers = auth_headers("buyer@test.local", "buyer123")

    # listar vehicles (debería incluir el creado)
    r = client.get("/api/vehicles")
    assert r.status_code == 200
    items = r.get_json()["data"]
    assert any(it["id"] == vid for it in items)

    # bid muy bajo → error 400 con min_required
    r = client.post(f"/api/vehicles/{vid}/bids",
                    json={"amount": 200000},  # igual a base, debería pedir +min_increment
                    headers=buyer_headers)
    assert r.status_code == 400
    data = r.get_json()
    assert data["error"]["min_required"] == 201000  # 200000 + 1000

    # bid válido
    r = client.post(f"/api/vehicles/{vid}/bids",
                    json={"amount": 201000},
                    headers=buyer_headers)
    assert r.status_code == 200
    b = r.get_json()["data"]
    assert b["amount"] == 201000

    # segundo bid demasiado bajo
    r = client.post(f"/api/vehicles/{vid}/bids",
                    json={"amount": 201100},  # ahora min debe ser 202000
                    headers=buyer_headers)
    assert r.status_code == 400
    assert r.get_json()["error"]["min_required"] == 202000
