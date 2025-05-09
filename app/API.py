import datetime

from fastapi import Depends, HTTPException, FastAPI
from sqlalchemy.orm import Session

from app.monitor_integration import humidity_monitor, app
from app.schemas import Measurement, MeasurementCreate, Sensor, SensorCreate, HumiditySensor, HumidityMeasurement
from app.session import get_db


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


@app.get("/monitor/status")
def get_monitor_status():
    """Get the current monitoring status and thresholds"""
    if not humidity_monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    return {
        "status": "running" if humidity_monitor._monitor_task else "stopped",
        "thresholds": {
            "humidity_high": humidity_monitor.humidity_threshold_high,
            "humidity_low": humidity_monitor.humidity_threshold_low,
            "connection_minutes": humidity_monitor.connection_threshold_minutes
        },
        "check_interval_seconds": humidity_monitor.check_interval
    }


@app.post("/monitor/check-now")
async def trigger_immediate_check():
    """Trigger an immediate check of all sensors"""
    if not humidity_monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    try:
        await humidity_monitor._check_all_sensors()
        return {"status": "check completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Check failed: {str(e)}")
@app.get("/health")
def health_check():
    return {"status": "healthy"}
