from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from utils.config import password_context

def hash_password(password: str) -> str:
    """Función simple para hashear contraseñas"""
    return password_context.hash(password)

class User(BaseModel):
    id: Optional[int] = None
    email: str
    username: str
    hashed_password: str
    created_at: str = datetime.now().isoformat()
    subscription_level: str = "free"  # free, premium, institutional
    api_calls_today: int = 0
    last_reset: str = datetime.now().isoformat()
    
    def verify_password(self, password: str) -> bool:
        """Verificar si la contraseña coincide"""
        return password_context.verify(password, self.hashed_password)
    
    def reset_api_counter(self):
        """Resetear el contador de API calls si es un nuevo día"""
        now = datetime.now()
        last_reset = datetime.fromisoformat(self.last_reset)
        
        if now.date() > last_reset.date():
            self.api_calls_today = 0
            self.last_reset = now.isoformat()
