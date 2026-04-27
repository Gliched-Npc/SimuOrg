def test_health_check(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "online", "message": "SimuOrg Engine is Running"}


def test_cors_headers(client):
    response = client.options(
        "/", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"}
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
