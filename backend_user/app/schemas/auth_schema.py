from pydantic import BaseModel,Field

class AuthCreate(BaseModel):
    id : str
    pwd : str
    name : str

class AuthLogin(BaseModel):
    id : str
    pwd : str
    
class AuthPublic(BaseModel):
    id : str
    name : str | None = None

class AuthUpdate(BaseModel):
    id : str
    pwd : str
    name : str