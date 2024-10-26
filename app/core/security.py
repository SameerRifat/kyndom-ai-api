from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from functools import wraps
import os
from typing import Dict, Any
from datetime import datetime
import jwt
import json
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

security = HTTPBearer()

class NextAuthMiddleware:
    def __init__(self):
        self.secret = os.getenv("NEXTAUTH_SECRET")
        if not self.secret:
            raise ValueError("NEXTAUTH_SECRET environment variable is not set")

    async def verify_token(self, credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
        try:
            token = credentials.credentials
            if not token or token == "undefined":
                raise HTTPException(
                    status_code=401,
                    detail="No valid token provided"
                )
            
            # print(f"[Auth] Received token: {token}")
            
            # Check if the token is a JSON string
            try:
                # If it's a JSON string, parse it
                if token.startswith('{'):
                    session_data = json.loads(token)
                    # Convert the parsed session data into a JWT
                    payload = {
                        "sub": session_data["user"]["id"],
                        "email": session_data["user"]["email"],
                        "name": session_data["user"]["name"],
                        "picture": session_data["user"]["picture"],
                        "onboarded": session_data["user"].get("onboarded", False),
                        "iat": session_data["user"]["iat"],
                        "exp": session_data["user"]["exp"],
                        "jti": session_data["user"]["jti"]
                    }
                    # Create a new JWT token
                    token = jwt.encode(payload, self.secret, algorithm="HS256")
            except json.JSONDecodeError:
                # If it's not JSON, assume it's already a JWT
                pass
            
            # Decode and verify the JWT
            try:
                payload = jwt.decode(
                    token,
                    self.secret,
                    algorithms=["HS256"],
                    options={
                        "verify_aud": False,
                        "verify_iss": False,
                    }
                )
                
                # print(f"[Auth] Decoded payload: {payload}")
                
                # Convert to NextAuth session format
                session = {
                    "expires": datetime.fromtimestamp(payload["exp"]).isoformat() + "Z",
                    "user": {
                        "email": payload["email"],
                        "exp": payload["exp"],
                        "iat": payload["iat"],
                        "id": payload["sub"],
                        "jti": payload["jti"],
                        "name": payload["name"],
                        "onboarded": payload.get("onboarded", False),
                        "picture": payload.get("picture"),
                        "sub": payload["sub"]
                    }
                }
                
                # Validate required fields
                if not all([
                    session["user"]["email"],
                    session["user"]["id"],
                    session["user"]["exp"],
                    session["user"]["iat"],
                    session["user"]["jti"]
                ]):
                    raise HTTPException(
                        status_code=401,
                        detail="Missing required session fields"
                    )
                
                return session
                
            except ExpiredSignatureError:
                raise HTTPException(
                    status_code=401,
                    detail="Token has expired"
                )
            except InvalidTokenError as e:
                print(f"[Auth] JWT decode error: {str(e)}")
                raise HTTPException(
                    status_code=401,
                    detail=f"Invalid token format: {str(e)}"
                )
            
        except Exception as e:
            print(f"[Auth] Unexpected error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Authentication error: {str(e)}"
            )

    def requires_auth(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = next((arg for arg in args if isinstance(arg, Request)), 
                         kwargs.get('request'))
            
            if not request:
                raise HTTPException(
                    status_code=500,
                    detail="Request object not found"
                )

            auth_header = request.headers.get("Authorization")
            if not auth_header:
                raise HTTPException(
                    status_code=401,
                    detail="Authorization header missing"
                )

            try:
                scheme, token = auth_header.split()
                if scheme.lower() != 'bearer':
                    raise HTTPException(
                        status_code=401,
                        detail="Invalid authentication scheme"
                    )
                credentials = HTTPAuthorizationCredentials(scheme=scheme, credentials=token)
                
                session = await self.verify_token(credentials)
                request.state.session = session
                request.state.user = session["user"]
                
                return await func(*args, **kwargs)
                
            except ValueError:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid authorization header format"
                )
            
        return wrapper

# Initialize the middleware
auth_middleware = NextAuthMiddleware()