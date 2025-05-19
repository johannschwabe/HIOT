import datetime
import logging
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas import Sensor, SensorCreate, HumiditySensor, Measurement, MeasurementCreate, HumidityMeasurement
from api.session import get_db

logger = logging.getLogger("humidity-api")

app = FastAPI(title="IoT Humidity Sensor API")


@app.get("/humiditySensors/", response_model=list[Sensor])
def read_sensors(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    sensors = db.query(HumiditySensor).offset(skip).limit(limit).all()
    return sensors


@app.get("/humiditySensor/{sensor_id}", response_model=Sensor)
def read_sensor(sensor_id: int, db: Session = Depends(get_db)):
    sensor = db.query(HumiditySensor).filter(HumiditySensor.id == sensor_id).first()
    if sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")
    return sensor


@app.post("/humidityMeasurements/", response_model=Measurement)
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


@app.get("/humidityMeasurements/sensor/{sensor_id}", response_model=list[Measurement])
def read_sensor_measurements(sensor_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    measurements = db.query(HumidityMeasurement).filter(
        HumidityMeasurement.sensor_id == sensor_id
    ).offset(skip).limit(limit).all()

    return measurements


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/humiditySensors/rename", response_model=Sensor)
def rename_humidity_sensor(sensor_id: int, new_name: str, db: Session = Depends(get_db)):
    db_sensor = db.query(HumiditySensor).filter(HumiditySensor.id == sensor_id).first()
    if db_sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")

    db.query(HumiditySensor).filter(HumiditySensor.id == sensor_id).update({"name": new_name})
    db.commit()
    return db.query(HumiditySensor).filter(HumiditySensor.id == sensor_id).first()