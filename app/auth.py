from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings
from app.models import TokenData, UserInDB
from app.database import get_database
import httpx
import json

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT token scheme
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def verify_token(token: str) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id)
    except JWTError:
        raise credentials_exception
    
    return token_data


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db=Depends(get_database)
) -> UserInDB:
    token_data = verify_token(credentials.credentials)
    
    user = await db.users.find_one({"id": token_data.user_id})
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return UserInDB(**user)


async def authenticate_user(email: str, password: str, db) -> Optional[UserInDB]:
    user = await db.users.find_one({"email": email, "provider": "email"})
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return UserInDB(**user)


async def get_user_by_email(email: str, db) -> Optional[UserInDB]:
    user = await db.users.find_one({"email": email})
    if user:
        return UserInDB(**user)
    return None


async def create_user(user_data: dict, db) -> UserInDB:
    user = UserInDB(**user_data)
    await db.users.insert_one(user.dict())
    return user


async def get_google_user_info(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Google access token"
            )
        return response.json()


async def get_github_user_info(access_token: str) -> dict:
    """Get user info from GitHub OAuth"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid GitHub access token"
            )
        return response.json()


async def get_or_create_oauth_user(provider: str, provider_id: str, email: str, name: str, db) -> UserInDB:
    """Get or create a user from OAuth provider"""
    # Check if user already exists
    user = await db.users.find_one({
        "provider": provider,
        "provider_id": provider_id
    })
    
    if user:
        return UserInDB(**user)
    
    # Check if email already exists with different provider
    existing_user = await db.users.find_one({"email": email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered with different provider"
        )
    
    # Create new user
    user_data = {
        "email": email,
        "name": name,
        "provider": provider,
        "provider_id": provider_id,
        "password_hash": None
    }
    
    return await create_user(user_data, db)
