from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from .. import database, models, schemas

# Konfigurasi Keamanan 
SECRET_KEY = "ganti_dengan_string_rahasia_yang_sangat_panjang" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Fungsi untuk verifikasi password 
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# Tambahkan fungsi hashing ini di bagian atas (di bawah pwd_context)
def get_password_hash(password):
    return pwd_context.hash(password)

# Tambahkan endpoint ini di bagian bawah file
@router.post("/register", response_model=schemas.UserResponse)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Cek apakah username sudah dipakai
    db_user = db.query(models.UserAccount).filter(models.UserAccount.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username sudah terdaftar")
    
    # Buat user baru dengan password yang di-hash (penting!)
    hashed_pwd = get_password_hash(user.password)
    
    # Buat ID unik sederhana
    new_id = f"USR-{datetime.now().strftime('%f')}"
    
    new_user = models.UserAccount(
        user_id=new_id,
        username=user.username,
        password_hash=hashed_pwd,
        role=user.role
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# Endpoint Login untuk mendapatkan Token [cite: 314]
@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.UserAccount).filter(models.UserAccount.username == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau password salah",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Buat Token JWT [cite: 314]
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": user.username, "role": user.role, "exp": datetime.utcnow() + access_token_expires}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return {"access_token": encoded_jwt, "token_type": "bearer"}