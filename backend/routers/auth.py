from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import jwt
from datetime import datetime, timedelta
import hashlib

router = APIRouter()
security = HTTPBearer()

# Secret key para JWT - EN PRODUCCIÓN USAR VARIABLE DE ENTORNO
SECRET_KEY = "bullbearbroker_secret_key_2024"
ALGORITHM = "HS256"

# Función para hashear contraseñas
def hash_password(password: str) -> str:
    """Función simple para hashear contraseñas"""
    return hashlib.sha256(password.encode()).hexdigest()

# Modelo de usuario simplificado (sin Pydantic para evitar dependencias)
class User:
    def __init__(self, email: str, username: str, hashed_password: str):
        self.id = None
        self.email = email
        self.username = username
        self.hashed_password = hashed_password
        self.created_at = datetime.now().isoformat()
        self.subscription_level = "free"
        self.api_calls_today = 0
        self.last_reset = datetime.now().isoformat()
    
    def verify_password(self, password: str) -> bool:
        """Verificar si la contraseña coincide"""
        return self.hashed_password == hash_password(password)
    
    def reset_api_counter(self):
        """Resetear el contador de API calls si es un nuevo día"""
        now = datetime.now()
        last_reset = datetime.fromisoformat(self.last_reset)
        
        if now.date() > last_reset.date():
            self.api_calls_today = 0
            self.last_reset = now.isoformat()

# Base de datos temporal en memoria - luego reemplazaremos con PostgreSQL
users_db = {}

# Simulación de base de datos para desarrollo
def init_sample_users():
    """Crear algunos usuarios de ejemplo para testing"""
    sample_users = [
        {"email": "test@bullbear.com", "username": "testuser", "password": "password123"},
        {"email": "trader@bullbear.com", "username": "traderpro", "password": "trading123"}
    ]
    
    for user_data in sample_users:
        user = User(
            email=user_data["email"],
            username=user_data["username"],
            hashed_password=hash_password(user_data["password"])
        )
        users_db[user_data["email"]] = user

# Inicializar usuarios de muestra
init_sample_users()

def create_jwt_token(user: User) -> str:
    """Crear token JWT para el usuario"""
    payload = {
        "sub": user.email,
        "username": user.username,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/register")
async def register(user_data: dict):
    """Endpoint para registrar nuevo usuario"""
    try:
        if user_data["email"] in users_db:
            raise HTTPException(status_code=400, detail="Email ya está registrado")
        
        if len(user_data["password"]) < 6:
            raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")
        
        new_user = User(
            email=user_data["email"],
            username=user_data["username"],
            hashed_password=hash_password(user_data["password"])
        )
        
        users_db[user_data["email"]] = new_user
        token = create_jwt_token(new_user)
        
        return {
            "message": "Usuario registrado exitosamente",
            "token": token,
            "user": {
                "email": new_user.email,
                "username": new_user.username,
                "subscription_level": new_user.subscription_level
            }
        }
        
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Campo faltante: {str(e)}")

@router.post("/login")
async def login(credentials: dict):
    """Endpoint para login de usuario"""
    try:
        email = credentials["email"]
        password = credentials["password"]
        
        if email not in users_db:
            raise HTTPException(status_code=401, detail="Credenciales inválidas")
        
        user = users_db[email]
        
        if not user.verify_password(password):
            raise HTTPException(status_code=401, detail="Credenciales inválidas")
        
        token = create_jwt_token(user)
        
        return {
            "message": "Login exitoso",
            "token": token,
            "user": {
                "email": user.email,
                "username": user.username,
                "subscription_level": user.subscription_level
            }
        }
        
    except KeyError:
        raise HTTPException(status_code=400, detail="Email y password requeridos")

@router.get("/users/me")
async def get_current_user(token: HTTPAuthorizationCredentials = Depends(security)):
    """Obtener información del usuario actual"""
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload["sub"]
        
        if email not in users_db:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        user = users_db[email]
        return {
            "email": user.email,
            "username": user.username,
            "subscription_level": user.subscription_level,
            "api_calls_today": user.api_calls_today
        }
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")
