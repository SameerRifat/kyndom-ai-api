from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from functools import wraps
import os
from typing import Dict, Any
from datetime import datetime

security = HTTPBearer()

class AuthMiddleware:
    """Middleware for validating NextAuth.js JWT tokens"""
    def __init__(self):
        self.secret = os.getenv("NEXTAUTH_SECRET")
        if not self.secret:
            raise ValueError("NEXTAUTH_SECRET environment variable is not set")
        self.secret_bytes = self.secret.encode() if isinstance(self.secret, str) else self.secret

    async def verify_token(self, credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
        try:
            token = credentials.credentials
            print(f"[Auth] Received token: {token[:20]}...")
            
            # Decode JWT
            payload = jwt.decode(
                token,
                self.secret_bytes,
                algorithms=["HS256"],
                options={
                    "verify_aud": False,
                    "verify_iss": False,
                }
            )
            
            print(f"[Auth] Decoded payload: {payload}")
            
            # Validate required claims
            required_claims = ["sub", "email", "exp", "iat"]
            missing_claims = [claim for claim in required_claims if claim not in payload]
            if missing_claims:
                raise HTTPException(
                    status_code=401,
                    detail=f"Missing required claims: {missing_claims}"
                )
            
            # Check expiration
            if datetime.utcnow().timestamp() > payload["exp"]:
                raise HTTPException(
                    status_code=401,
                    detail="Token has expired"
                )
            
            return payload
            
        except JWTError as e:
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
        """Decorator for protecting FastAPI routes"""
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
                
                payload = await self.verify_token(credentials)
                request.state.user = payload
                
                return await func(*args, **kwargs)
                
            except ValueError:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid authorization header format"
                )
            
        return wrapper

# Initialize the middleware
auth_middleware = AuthMiddleware()

# from fastapi import Request, HTTPException, Depends
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# from functools import wraps
# import os
# from typing import Optional
# import logging
# from uuid import UUID

# logger = logging.getLogger(__name__)

# security = HTTPBearer()

# class AuthMiddleware:
#     """Middleware for validating NextAuth.js JTI tokens"""
#     def __init__(self):
#         self.secret = os.getenv("NEXTAUTH_SECRET")
#         if not self.secret:
#             raise ValueError("NEXTAUTH_SECRET environment variable is not set")

#     async def verify_token(self, credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
#         try:
#             token = credentials.credentials
#             logger.debug(f"Verifying JTI token: {token}")
#             print(f"token: {token}")
            
#             # Validate that the token is a valid UUID (JTI format)
#             try:
#                 UUID(token)
#                 return token
#             except ValueError:
#                 logger.error("Invalid JTI format")
#                 raise HTTPException(
#                     status_code=401,
#                     detail="Invalid token format"
#                 )
            
#         except Exception as e:
#             logger.error(f"Token verification failed: {str(e)}")
#             raise HTTPException(
#                 status_code=401,
#                 detail="Authentication failed"
#             )

#     def requires_auth(self, func):
#         """Decorator for protecting FastAPI routes"""
#         @wraps(func)
#         async def wrapper(*args, **kwargs):
#             request = next((arg for arg in args if isinstance(arg, Request)), 
#                          kwargs.get('request'))
            
#             if not request:
#                 raise HTTPException(
#                     status_code=500,
#                     detail="Request object not found"
#                 )

#             auth_header = request.headers.get("Authorization")
#             if not auth_header:
#                 logger.error("Authorization header missing")
#                 raise HTTPException(
#                     status_code=401,
#                     detail="Authorization header missing"
#                 )

#             try:
#                 scheme, token = auth_header.split()
#                 if scheme.lower() != 'bearer':
#                     logger.error(f"Invalid authentication scheme: {scheme}")
#                     raise HTTPException(
#                         status_code=401,
#                         detail="Invalid authentication scheme"
#                     )
#                 credentials = HTTPAuthorizationCredentials(scheme=scheme, credentials=token)
                
#                 # Verify the token (JTI)
#                 jti = await self.verify_token(credentials)
                
#                 # Store the JTI in request state
#                 request.state.jti = jti
                
#                 return await func(*args, **kwargs)
                
#             except ValueError as e:
#                 logger.error(f"Invalid authorization header format: {str(e)}")
#                 raise HTTPException(
#                     status_code=401,
#                     detail="Invalid authorization header format"
#                 )
#             except Exception as e:
#                 logger.error(f"Authentication error: {str(e)}")
#                 raise HTTPException(
#                     status_code=401,
#                     detail="Authentication failed"
#                 )
        
#         return wrapper

# # Initialize the middleware
# auth_middleware = AuthMiddleware()

################################################################################################

# from fastapi import Request, HTTPException, Depends
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# from jose import jwt, JWTError
# from functools import wraps
# import os
# from typing import Optional

# # Define the security scheme
# security = HTTPBearer()

# class AuthMiddleware:
#     """Middleware for validating NextAuth.js JWT tokens"""
#     def __init__(self):
#         self.secret = os.getenv("NEXTAUTH_SECRET")
#         if not self.secret:
#             raise ValueError("NEXTAUTH_SECRET environment variable is not set")

#     async def verify_token(self, credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
#         try:
#             token = credentials.credentials
#             print(f"token: {token}")
#             payload = jwt.decode(token, self.secret, algorithms=["HS256"])
            
#             # Verify the token has required claims
#             if not all(key in payload for key in ["sub", "email", "exp"]):
#                 raise HTTPException(
#                     status_code=401,
#                     detail="Invalid token structure"
#                 )
#             return payload
            
#         except JWTError:
#             raise HTTPException(
#                 status_code=401,
#                 detail="Invalid or expired token"
#             )

#     def requires_auth(self, func):
#         """Decorator for protecting FastAPI routes"""
#         @wraps(func)
#         async def wrapper(*args, **kwargs):
#             request = next((arg for arg in args if isinstance(arg, Request)), 
#                          kwargs.get('request'))
            
#             if not request:
#                 raise HTTPException(
#                     status_code=500,
#                     detail="Request object not found"
#                 )

#             auth_header = request.headers.get("Authorization")
#             if not auth_header:
#                 raise HTTPException(
#                     status_code=401,
#                     detail="Authorization header missing"
#                 )

#             try:
#                 scheme, token = auth_header.split()
#                 if scheme.lower() != 'bearer':
#                     raise HTTPException(
#                         status_code=401,
#                         detail="Invalid authentication scheme"
#                     )
#                 credentials = HTTPAuthorizationCredentials(scheme=scheme, credentials=token)
#             except ValueError:
#                 raise HTTPException(
#                     status_code=401,
#                     detail="Invalid authorization header format"
#                 )

#             await self.verify_token(credentials)
#             return await func(*args, **kwargs)
        
#         return wrapper

# # Initialize the middleware
# auth_middleware = AuthMiddleware()