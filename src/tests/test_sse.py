# tests/test_sse.py
def test_sse_endpoint_available(client, seller_headers):
    # crea un vehículo para probar el canal
    payload = {
        "make": "Dodge",
        "model": "Charger",
        "year": 1970,
        "base_price": 150000,
        "lot_code": "TST-002",
        "images": []
    }
    r = client.post("/api/vehicles", json=payload, headers=seller_headers)
    assert r.status_code == 200
    vid = r.get_json()["data"]["id"]

    # verifica que el endpoint SSE exista y devuelva el mime correcto
    r = client.get(f"/api/sse/vehicles/{vid}")
    # Nota: el test client no mantiene el stream, pero sí valida headers
    assert r.status_code == 200
    assert r.mimetype == "text/event-stream"
