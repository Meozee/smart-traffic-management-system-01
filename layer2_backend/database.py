from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base, UserAccount # Pastikan UserAccount sudah di-import

DATABASE_URL = "postgresql://miko_user:miko123@db:5432/stms_db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    # Membuat semua tabel (termasuk UserAccount yang baru kita tambah)
    Base.metadata.create_all(bind=engine)
    
    # Tambahkan User Admin secara manual untuk testing
    db = SessionLocal()
    # Cek apakah user admin sudah ada
    admin_exists = db.query(UserAccount).filter(UserAccount.username == "admin").first()
    
    if not admin_exists:
        # Peran (role) sesuai dokumen Capstone: supervisor/management/admin [cite: 226]
        new_admin = UserAccount(
            user_id="USR-001",
            username="admin",
            password_hash="ini_nanti_diganti_hash", # Untuk tes aja
            role="admin"
        )
        db.add(new_admin)
        db.commit()
        print("User Admin berhasil ditambahkan secara manual!")
    db.close()

if __name__ == "__main__":
    init_db()
    print("Tabel STMS berhasil diperbarui di Docker!")