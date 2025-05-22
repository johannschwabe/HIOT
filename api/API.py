import datetime
import logging
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas import HumiditySensor, HumidityMeasurement, HumidityMeasurementCreateORM, HumiditySensorORM, \
    HumidityMeasurementORM
from api.session import get_db, Base, engine

logger = logging.getLogger("humidity-api")

Base.metadata.create_all(bind=engine)
app = FastAPI(title="IoT Humidity Sensor API")


@app.get("/humiditySensors/", response_model=list[HumiditySensorORM])
def read_sensors(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    sensors = db.query(HumiditySensor).offset(skip).limit(limit).all()
    return sensors


@app.get("/humiditySensor/{sensor_id}", response_model=HumiditySensorORM)
def read_sensor(sensor_id: int, db: Session = Depends(get_db)):
    sensor = db.query(HumiditySensor).filter(HumiditySensor.id == sensor_id).first()
    if sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")
    return sensor



@app.post("/humidityMeasurements/", response_model=HumidityMeasurementORM)
def create_measurement(measurement: HumidityMeasurementCreateORM, db: Session = Depends(get_db)):
    # Check if sensor exists
    logger.warning(f"Creating measurement {measurement}")
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


@app.get("/humidityMeasurements/sensor/{sensor_id}", response_model=list[HumidityMeasurementORM])
def read_sensor_measurements(sensor_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    measurements = db.query(HumidityMeasurement).filter(
        HumidityMeasurement.sensor_id == sensor_id
    ).offset(skip).limit(limit).all()

    return measurements

@app.get("/humidityOverview", response_model=str)
def read_humidity_overview( db: Session = Depends(get_db)):
    res = ""
    sensors = db.query(HumiditySensor).order_by(HumiditySensor.last_connection).all()
    for sensor in sensors:
        measurements = (db.query(HumidityMeasurement).filter(HumidityMeasurement.sensor_id == sensor.id)
         .order_by(HumidityMeasurement.date).limit(1).all())
        if measurements:
            measurement = measurements[0]
            icon = "🌿"
            if measurement.humidity > sensor.overflow_level:
                icon = "🤿"
            if measurement.humidity < sensor.alert_level:
                icon = "🍂"
            if measurement.humidity < sensor.warning_level:
                icon = "🔥"
            if measurement.humidity < sensor.critical_level:
                icon = "💀"
            res += f"{sensor.name}: {measurement.humidity}% {icon}\n"
    return res


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/humiditySensors/rename", response_model=HumiditySensorORM)
def rename_humidity_sensor(sensor_id: int, new_name: str, db: Session = Depends(get_db)):
    db_sensor = db.query(HumiditySensor).filter(HumiditySensor.id == sensor_id).first()
    if db_sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")

    db.query(HumiditySensor).filter(HumiditySensor.id == sensor_id).update({"name": new_name})
    db.commit()
    return db.query(HumiditySensor).filter(HumiditySensor.id == sensor_id).first()