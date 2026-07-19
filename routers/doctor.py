import jwt
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from database import get_db
import models
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

# URL JWKS Clerk untuk memvalidasi token
CLERK_JWKS_URL = os.getenv(
    "CLERK_JWKS_URL",
    "https://eternal-goshawk-36.clerk.accounts.dev/.well-known/jwks.json",
)
CLERK_ISSUER = os.getenv(
    "CLERK_JWT_ISSUER",
    "https://eternal-goshawk-36.clerk.accounts.dev",
)

# Cache JWKS agar tidak fetch setiap request
jwks_client = jwt.PyJWKClient(CLERK_JWKS_URL)


def get_current_clerk_user(authorization: str = Header(None)):
    """
    Dependency untuk memverifikasi token JWT Clerk dari header Authorization.
    Mengembalikan payload JWT jika valid.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or invalid token format"
        )

    token = authorization.split(" ")[1]

    try:
        # 1. Dapatkan Public Key dari JWKS yang cocok dengan header kid token
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # 2. Decode dan verifikasi token
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=None,  # Clerk access token tidak selalu menyertakan aud
            issuer=CLERK_ISSUER,
            options={"verify_aud": False},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=401, detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal token validation error"
        )


@router.get("/doctor")
def get_doctor_profile(
    current_user: dict = Depends(get_current_clerk_user),
    db: Session = Depends(get_db),
):
    """
    Endpoint untuk mencocokkan user Clerk (dari Next.js Dashboard)
    dengan id_user lokal di database SQLite/MySQL FastAPI.

    Menerima JWT Clerk via header Authorization: Bearer <clerk_jwt>.
    Mengembalikan id_user, name, dan email dari database lokal.
    """
    # Payload Clerk berisi claim seperti 'sub' (clerk ID) dan 'email'
    clerk_user_id = current_user.get("sub")
    email = current_user.get("email")  # atau claim kustom lainnya

    # Cari di database lokal berdasarkan email terlebih dahulu
    user = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        # Jika belum ada, return 404
        raise HTTPException(
            status_code=404,
            detail=f"User dengan email {email} belum terdaftar di database lokal",
        )

    return {
        "id_user": user.id,   # ID integer lokal FastAPI
        "name": user.name,    # Nama di database lokal
        "email": user.email,  # Email
    }
