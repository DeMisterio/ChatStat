import os
from pathlib import Path
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import httpx

router = APIRouter(prefix="/api/hf-token", tags=["hf-token"])

TOKEN_FILE = Path(__file__).parent / ".hf_token"

class TokenInput(BaseModel):
    token: str

def load_hf_token_on_startup():
    """Loads the token from disk into environment variables safely."""
    if TOKEN_FILE.exists():
        try:
            with open(TOKEN_FILE, "r") as f:
                token = f.read().strip()
                if token:
                    os.environ["HF_TOKEN"] = token
                    try:
                        # Depending on the version, login can be explicitly called.
                        # HF_TOKEN is naturally picked up by most recent huggingface_hub modules.
                        from huggingface_hub import login
                        login(token=token, add_to_git_credential=False)
                    except ImportError:
                        pass
        except Exception as e:
            print(f"Failed to load HF token on startup: {e}")

@router.post("/validate")
async def validate_token(data: TokenInput):
    """Validates the token against HuggingFace API before saving."""
    token = data.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token cannot be empty")
        
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://huggingface.co/api/whoami-v2",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )
            if resp.status_code == 200:
                user_info = resp.json()
                username = user_info.get("name", "User")
                return {"message": f"Привет, {username}!"}
            elif resp.status_code == 401:
                raise HTTPException(status_code=401, detail="Неверный токен HuggingFace")
            else:
                raise HTTPException(status_code=500, detail=f"Ошибка соединения с HuggingFace (код {resp.status_code})")
    except httpx.RequestError:
        raise HTTPException(status_code=500, detail="Не удалось подключиться к серверам HuggingFace")

@router.post("")
async def save_token(data: TokenInput):
    """Saves the token securely to disk and sets the environment variable."""
    token = data.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token cannot be empty")
        
    try:
        with open(TOKEN_FILE, "w") as f:
            f.write(token)
            
        os.chmod(TOKEN_FILE, 0o600)
        os.environ["HF_TOKEN"] = token
        
        try:
            from huggingface_hub import login
            login(token=token, add_to_git_credential=False)
        except ImportError:
            pass
            
        return {"message": "Токен успешно сохранён"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения токена: {str(e)}")

@router.get("/status")
async def get_token_status():
    """Returns the masked token status."""
    token = os.environ.get("HF_TOKEN")
    if not token and TOKEN_FILE.exists():
        try:
            with open(TOKEN_FILE, "r") as f:
                token = f.read().strip()
        except:
            pass
            
    if token:
        masked = f"{token[:3]}***...***{token[-4:]}" if len(token) > 10 else "***"
        return {"is_set": True, "masked_token": masked}
    return {"is_set": False}

@router.delete("")
async def delete_token():
    """Deletes the locally stored token."""
    if TOKEN_FILE.exists():
        try:
            os.remove(TOKEN_FILE)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Не удалось удалить файл токена: {e}")
            
    if "HF_TOKEN" in os.environ:
        del os.environ["HF_TOKEN"]
        
    try:
        from huggingface_hub import logout
        logout()
    except ImportError:
        pass
        
    return {"message": "Токен удалён"}
