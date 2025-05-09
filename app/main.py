# app/main.py
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "iot_db")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# SQLAlchemy setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Models
class HumiditySensor(Base):
    __tablename__ = "humidity_sensors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    last_connection = Column(DateTime, default=datetime.datetime.utcnow)


class HumidityMeasurement(Base):
    __tablename__ = "humidity_measurements"

    id = Column(Integer, primary_key=True, index=True)
    sensor_id = Column(Integer, ForeignKey("humidity_sensors.id"))
    raw_value = Column(Float, nullable=False)
    humidity = Column(Float, nullable=False)
    date = Column(DateTime, default=datetime.datetime.utcnow)


# Create tables
Base.metadata.create_all(bind=engine)


# Pydantic models
class SensorBase(BaseModel):
    name: str


class SensorCreate(SensorBase):
    pass


class Sensor(SensorBase):
    id: int
    last_connection: datetime.datetime

    class Config:
        orm_mode = True


class MeasurementBase(BaseModel):
    raw_value: float
    humidity: float


class MeasurementCreate(MeasurementBase):
    sensor_id: int


class Measurement(MeasurementBase):
    id: int
    sensor_id: int
    date: datetime.datetime

    class Config:
        orm_mode = True


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app = FastAPI(title="IoT Humidity Sensor API")


# Routes
@app.post("/sensors/", response_model=Sensor)
def create_sensor(sensor: SensorCreate, db: Session = Depends(get_db)):
    db_sensor = HumiditySensor(name=sensor.name)
    db.add(db_sensor)
    db.commit()
    db.refresh(db_sensor)
    return db_sensor


@app.get("/sensors/", response_model=list[Sensor])
def read_sensors(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    sensors = db.query(HumiditySensor).offset(skip).limit(limit).all()
    return sensors


@app.get("/sensors/{sensor_id}", response_model=Sensor)
def read_sensor(sensor_id: int, db: Session = Depends(get_db)):
    sensor = db.query(HumiditySensor).filter(HumiditySensor.id == sensor_id).first()
    if sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")
    return sensor


@app.post("/measurements/", response_model=Measurement)
def create_measurement(measurement: MeasurementCreate, db: Session = Depends(get_db)):
    # Check if sensor exists
    sensor = db.query(HumiditySensor).filter(HumiditySensor.id == measurement.sensor_id).first()
    if sensor is None:
        db_sensor = HumiditySensor(name="Unknown")
        db.add(db_sensor)
        db.commit()
        db.refresh(db_sensor)
        sensor = db_sensor

    # Update last connection time
    sensor.last_connection = datetime.datetime.utcnow()

    # Create measurement
    db_measurement = HumidityMeasurement(
        sensor_id=measurement.sensor_id,
        raw_value=measurement.raw_value,
        humidity=measurement.humidity
    )

    db.add(db_measurement)
    db.commit()
    db.refresh(db_measurement)

    return db_measurement


@app.get("/measurements/", response_model=list[Measurement])
def read_measurements(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    measurements = db.query(HumidityMeasurement).offset(skip).limit(limit).all()
    return measurements


@app.get("/measurements/sensor/{sensor_id}", response_model=list[Measurement])
def read_sensor_measurements(sensor_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    measurements = db.query(HumidityMeasurement).filter(
        HumidityMeasurement.sensor_id == sensor_id
    ).offset(skip).limit(limit).all()

    return measurements


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)