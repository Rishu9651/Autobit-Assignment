from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse
from app.models import (
    SignupRequest, LoginRequest, Token, User, UserInDB,
    ErrorResponse, SuccessResponse
)
from app.auth import (
    authenticate_user, create_user, get_user_by_email,
    create_access_token, get_current_user, get_or_create_oauth_user,
    get_google_user_info, get_github_user_info
)
from app.database import get_database
from app.config import settings
from datetime import timedelta
import httpx
import secrets

router = APIRouter(prefix="", tags=["Authentication"])


@router.post("/signup", response_model=Token)
async def signup(request: SignupRequest, db=Depends(get_database)):
    """Sign up a new user with email and password"""
    # Check if user already exists
    existing_user = await get_user_by_email(request.email, db)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    from app.auth import get_password_hash
    user_data = {
        "email": request.email,
        "name": request.name,
        "provider": "email",
        "provider_id": None,
        "password_hash": get_password_hash(request.password)
    }
    
    user = await create_user(user_data, db)
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.jwt_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.id}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=Token)
async def login(request: LoginRequest, db=Depends(get_database)):
    """Login with email and password"""
    user = await authenticate_user(request.email, request.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.jwt_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.id}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/oauth/google/callback")
async def google_oauth_callback(
    code: str,
    state: str = None,
    db=Depends(get_database)
):
    """Handle Google OAuth callback"""
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth not configured"
        )
    
    try:
        # Exchange code for access token
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": "http://localhost:8000/auth/oauth/google/callback"
                }
            )
            
            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange code for token"
                )
            
            token_data = token_response.json()
            access_token = token_data["access_token"]
        
        # Get user info from Google
        user_info = await get_google_user_info(access_token)
        
        # Get or create user
        user = await get_or_create_oauth_user(
            provider="google",
            provider_id=user_info["id"],
            email=user_info["email"],
            name=user_info["name"],
            db=db
        )
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.jwt_expire_minutes)
        jwt_token = create_access_token(
            data={"sub": user.id}, expires_delta=access_token_expires
        )
        
        return {"access_token": jwt_token, "token_type": "bearer"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth authentication failed: {str(e)}"
        )


@router.get("/oauth/github/callback")
async def github_oauth_callback(
    code: str,
    state: str = None,
    db=Depends(get_database)
):
    """Handle GitHub OAuth callback"""
    if not settings.github_client_id or not settings.github_client_secret:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="GitHub OAuth not configured"
        )
    
    try:
        
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code
                },
                headers={"Accept": "application/json"}
            )
            
            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange code for token"
                )
            
            token_data = token_response.json()
            access_token = token_data["access_token"]
        
        # Get user info from GitHub
        user_info = await get_github_user_info(access_token)
        
        # Get or create user
        user = await get_or_create_oauth_user(
            provider="github",
            provider_id=str(user_info["id"]),
            email=user_info.get("email") or f"{user_info['login']}@users.noreply.github.com",
            name=user_info.get("name") or user_info["login"],
            db=db
        )
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.jwt_expire_minutes)
        jwt_token = create_access_token(
            data={"sub": user.id}, expires_delta=access_token_expires
        )
        
        return {"access_token": jwt_token, "token_type": "bearer"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth authentication failed: {str(e)}"
        )


@router.get("/oauth/google")
async def google_oauth_start():
    """Start Google OAuth flow - redirect to Google"""
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth not configured"
        )
    state = secrets.token_urlsafe(32)
    google_oauth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.google_client_id}&"
        "redirect_uri=http://localhost:8000/auth/oauth/google/callback&"
        "response_type=code&"
        "scope=openid%20email%20profile&"
        f"state={state}"
    )
    return RedirectResponse(url=google_oauth_url)


@router.get("/oauth/github")
async def github_oauth_start():
    """Start GitHub OAuth flow - redirect to GitHub"""
    if not settings.github_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="GitHub OAuth not configured"
        )
    state = secrets.token_urlsafe(32)
    github_oauth_url = (
        "https://github.com/login/oauth/authorize?"
        f"client_id={settings.github_client_id}&"
        "redirect_uri=http://localhost:8000/auth/oauth/github/callback&"
        "scope=user:email&"
        f"state={state}"
    )
    return RedirectResponse(url=github_oauth_url)


@router.get("/me", response_model=User)
async def get_current_user_info(current_user: UserInDB = Depends(get_current_user)):
    """Get current user information"""
    return User(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        provider=current_user.provider,
        created_at=current_user.created_at
    )
