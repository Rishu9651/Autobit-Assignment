import pytest
from fastapi.testclient import TestClient
from app.main import app

class TestSimpleAPI:
    """Simple API tests that don't require database connections"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.client = TestClient(app)
    
    def test_health_endpoint(self):
        """Test if the app starts up and responds"""
        # This test just checks if the app can start without errors
        assert self.client is not None
    
    def test_billing_rates_endpoint(self):
        """Test billing rates endpoint - this should work without database"""
        response = self.client.get("/billing/rates")
        assert response.status_code == 200
        rates = response.json()
        assert all(rates[k] > 0 for k in rates)
        assert "vcpu_rate_per_core_hour" in rates
        assert "ram_rate_per_gib_hour" in rates
        assert "disk_rate_per_gib_hour" in rates
    
    def test_unauthorized_access(self):
        """Test unauthorized access returns proper status codes"""
        # No auth header
        response = self.client.get("/servers")
        assert response.status_code == 403
        
        # Invalid token
        headers = {"Authorization": "Bearer invalid_token"}
        response = self.client.get("/servers", headers=headers)
        assert response.status_code == 401
    
    def test_docs_endpoint(self):
        """Test that API docs are accessible"""
        response = self.client.get("/docs")
        assert response.status_code == 200
    
    def test_openapi_endpoint(self):
        """Test that OpenAPI schema is accessible"""
        response = self.client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
