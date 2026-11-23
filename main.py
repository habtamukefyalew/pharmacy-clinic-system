from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import datetime, os

os.makedirs("static", exist_ok=True)

SQLALCHEMY_DATABASE_URL = "sqlite:///./pharmacy.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class MedicineModel(Base):
    __tablename__ = "medicines"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    category = Column(String, default="General")
    buy_price = Column(Float, default=0.0)
    sell_price = Column(Float, default=0.0)
    stock = Column(Integer, default=0)
    expiry_date = Column(String, default="2027-12-30")

class SaleModel(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, default="Walk-in Customer")
    medicine_name = Column(String)
    quantity = Column(Integer)
    unit_price = Column(Float)
    total_price = Column(Float)
    profit = Column(Float)
    payment_method = Column(String, default="Cash")
    sale_time = Column(String)

class PatientModel(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String)
    phone = Column(String)
    age_gender = Column(String)
    diagnosis = Column(String)
    prescription = Column(String)
    visit_date = Column(String)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="TanaCloud Pharmacy & Clinic Management System")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# የመጀመሪያ ናሙና መድኃኒቶችን መሙላት (ዳታቤዙ ባዶ ከሆነ)
def seed_initial_data():
    db = SessionLocal()
    if db.query(MedicineModel).count() == 0:
        samples = [
            MedicineModel(name="Amoxicillin 500mg (Capsules)", category="Antibiotic", buy_price=180, sell_price=250, stock=45, expiry_date="2027-08-15"),
            MedicineModel(name="Paracetamol 500mg (Tablets)", category="Painkiller", buy_price=55, sell_price=95, stock=7, expiry_date="2026-12-20"),
            MedicineModel(name="Artemether-Lumefantrine (Coartem)", category="Antimalarial", buy_price=210, sell_price=320, stock=30, expiry_date="2027-06-10"),
            MedicineModel(name="Ceftriaxone 1g Injection", category="Injection", buy_price=140, sell_price=220, stock=18, expiry_date="2027-04-05"),
            MedicineModel(name="Omeprazole 20mg", category="Gastric", buy_price=90, sell_price=150, stock=60, expiry_date="2028-01-12")
        ]
        db.add_all(samples)
        db.commit()
    db.close()

seed_initial_data()

@app.get("/")
def root():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "TanaCloud Pharmacy & Clinic System API is Running"}

@app.get("/api/medicines")
def list_medicines(db: Session = Depends(get_db)):
    return db.query(MedicineModel).order_by(MedicineModel.id.desc()).all()

@app.post("/api/medicines")
def create_medicine(item: dict, db: Session = Depends(get_db)):
    name = (item.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="የመድኃኒቱን ስም ያስገቡ!")
    existing = db.query(MedicineModel).filter(MedicineModel.name.ilike(name)).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"⚠️ '{name}' ቀድሞውኑ በክምችት ውስጥ ተመዝግቧል!")
    med = MedicineModel(
        name=name,
        category=item.get("category", "General"),
        buy_price=float(item.get("buy_price", 0)),
        sell_price=float(item.get("sell_price", 0)),
        stock=int(item.get("stock", 0)),
        expiry_date=item.get("expiry_date", "2027-12-30")
    )
    db.add(med)
    db.commit()
    db.refresh(med)
    return med

@app.put("/api/medicines/{med_id}")
def update_medicine(med_id: int, item: dict, db: Session = Depends(get_db)):
    med = db.query(MedicineModel).filter(MedicineModel.id == med_id).first()
    if not med:
        raise HTTPException(status_code=404, detail="መድኃኒቱ አልተገኘም!")
    if "stock" in item:
        med.stock = int(item["stock"])
    if "sell_price" in item:
        med.sell_price = float(item["sell_price"])
    if "expiry_date" in item:
        med.expiry_date = str(item["expiry_date"])
    db.commit()
    return med

@app.delete("/api/medicines/{med_id}")
def delete_medicine(med_id: int, db: Session = Depends(get_db)):
    med = db.query(MedicineModel).filter(MedicineModel.id == med_id).first()
    if not med:
        raise HTTPException(status_code=404, detail="መድኃኒቱ አልተገኘም!")
    db.delete(med)
    db.commit()
    return {"status": "deleted"}

@app.post("/api/sales")
def record_sale(payload: dict, db: Session = Depends(get_db)):
    med_id = int(payload.get("medicine_id", 0))
    qty = int(payload.get("quantity", 1))
    customer = (payload.get("customer_name") or "Walk-in Customer").strip()
    pay_method = (payload.get("payment_method") or "Cash").strip()

    med = db.query(MedicineModel).filter(MedicineModel.id == med_id).first()
    if not med:
        raise HTTPException(status_code=404, detail="መድኃኒቱ አልተገኘም!")
    if qty <= 0:
        raise HTTPException(status_code=400, detail="ብዛቱ ከ 0 መብለጥ አለበት!")
    if med.stock < qty:
        raise HTTPException(status_code=400, detail=f"⚠️ በቂ ክምችት የለም! ያለው ብዛት {med.stock} ብቻ ነው።")

    med.stock -= qty
    total = round(med.sell_price * qty, 2)
    profit = round((med.sell_price - med.buy_price) * qty, 2)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    sale = SaleModel(
        customer_name=customer,
        medicine_name=med.name,
        quantity=qty,
        unit_price=med.sell_price,
        total_price=total,
        profit=profit,
        payment_method=pay_method,
        sale_time=now_str
    )
    db.add(sale)
    db.commit()
    db.refresh(sale)
    return sale

@app.get("/api/sales")
def list_sales(db: Session = Depends(get_db)):
    return db.query(SaleModel).order_by(SaleModel.id.desc()).all()

@app.get("/api/patients")
def list_patients(db: Session = Depends(get_db)):
    return db.query(PatientModel).order_by(PatientModel.id.desc()).all()

@app.post("/api/patients")
def add_patient(payload: dict, db: Session = Depends(get_db)):
    full_name = (payload.get("full_name") or "").strip()
    if not full_name:
        raise HTTPException(status_code=400, detail="የታካሚውን ሙሉ ስም ያስገቡ!")
    patient = PatientModel(
        full_name=full_name,
        phone=(payload.get("phone") or "-").strip(),
        age_gender=(payload.get("age_gender") or "-").strip(),
        diagnosis=(payload.get("diagnosis") or "-").strip(),
        prescription=(payload.get("prescription") or "-").strip(),
        visit_date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient