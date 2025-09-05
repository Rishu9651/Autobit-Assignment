import pytest
from datetime import datetime, timedelta
from app.auth import create_access_token, verify_token, get_password_hash, verify_password

class TestAuth:
    """Unit tests for authentication functions"""
    
    def test_password_hashing(self):
        """Test password hashing and verification"""
        password = "testpassword123"
        hashed = get_password_hash(password)
        
        # Hash should be different from original password
        assert hashed != password
        assert len(hashed) > 0
        
        # Verification should work
        assert verify_password(password, hashed) == True
        assert verify_password("wrongpassword", hashed) == False
    
    def test_jwt_token_creation(self):
        """Test JWT token creation"""
        user_id = "test_user_123"
        token = create_access_token(
            data={"sub": user_id},
            expires_delta=timedelta(minutes=30)
        )
        
        assert token is not None
        assert len(token) > 0
        assert isinstance(token, str)
    
    def test_jwt_token_verification(self):
        """Test JWT token verification"""
        user_id = "test_user_123"
        token = create_access_token(
            data={"sub": user_id},
            expires_delta=timedelta(minutes=30)
        )
        
        # Verify token
        token_data = verify_token(token)
        assert token_data is not None
        assert token_data.user_id == user_id
    
    def test_jwt_token_expiration(self):
        """Test JWT token expiration"""
        user_id = "test_user_123"
        # Create token with very short expiration
        token = create_access_token(
            data={"sub": user_id},
            expires_delta=timedelta(seconds=-1)  # Already expired
        )
        
        # Token should be invalid - should raise HTTPException
        from fastapi import HTTPException
        try:
            verify_token(token)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 401
    
    def test_invalid_token(self):
        """Test invalid token handling"""
        invalid_token = "invalid.jwt.token"
        from fastapi import HTTPException
        try:
            verify_token(invalid_token)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 401
