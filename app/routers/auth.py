"""Authentication router for login and token management."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.domain.dto import LoginRequest, LoginResponse, RefreshTokenRequest
from app.repositories.users_repo import UsersRepository
from app.security import create_access_token, create_refresh_token, decode_token, validate_token_type, verify_password
from app.services.audit import AuditService

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate user and return JWT tokens.
    
    Args:
        credentials: Email and password
        db: Database session
        
    Returns:
        Access and refresh tokens
    """
    # Get user by email
    users_repo = UsersRepository(db)
    user = await users_repo.get_by_email(credentials.email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # Create tokens
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value,
    }

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Log the login
    audit_service = AuditService(db)
    await audit_service.log_login(user.id)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """
    Refresh access token using a refresh token.
    
    Args:
        request: Refresh token
        db: Database session
        
    Returns:
        New access and refresh tokens
    """
    # Validate token type
    if not validate_token_type(request.refresh_token, "refresh"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode refresh token
    try:
        payload = decode_token(request.refresh_token)
        user_id = payload.get("sub")
        email = payload.get("email")
        role = payload.get("role")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify user still exists and is active
    users_repo = UsersRepository(db)
    user = await users_repo.get_by_id(int(user_id))

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create new tokens
    token_data = {
        "sub": user_id,
        "email": email,
        "role": role,
    }

    access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)

    return LoginResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )


@router.post("/logout")
async def logout(db: AsyncSession = Depends(get_db)):
    """
    Logout endpoint (client should discard tokens).
    
    In a more sophisticated implementation, this would:
    - Blacklist the tokens
    - Clear server-side session
    - Notify other services
    
    For now, this is a placeholder that returns success.
    The client is responsible for discarding the tokens.
    """
    # In a production system, you might want to:
    # 1. Add the token to a blacklist (Redis, DB)
    # 2. Clear any server-side session data
    # 3. Log the logout event

    return {"message": "Logged out successfully"}
