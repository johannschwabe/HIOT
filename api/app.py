import os
import datetime
import logging
from io import BytesIO
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from database import init_database, get_db
from models import HumiditySensor, HumidityMeasurement
from schemas import HumiditySensorORM, HumidityMeasurementCreateORM, HumidityMeasurementORM
from ENV import DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
logger = logging.getLogger("humidity-api")

app = FastAPI(title="IoT Humidity Sensor API", root_path="/hiot")


# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database connection and tables on startup"""
    db_url = os.getenv("DATABASE_URL",
                       f"postgresql://{DB_USER}:{DB_PASSWORD}@"
                       f"{DB_HOST}:{DB_PORT}/{DB_NAME}"
                       )
    init_database(db_url)
    logger.info("Application startup complete")


# Utility functions
def get_alert_text(sensor: HumiditySensor, measurement: HumidityMeasurement) -> str:
    """Generate alert text with appropriate emoji based on humidity level"""
    # Determine humidity status emoji
    if measurement.humidity > sensor.overflow_level:
        icon = "🤿"
    elif measurement.humidity < sensor.critical_level:
        icon = "💀"
    elif measurement.humidity < sensor.warning_level:
        icon = "🔥"
    elif measurement.humidity < sensor.alert_level:
        icon = "🍂"
    else:
        icon = "🌿"

    # Calculate time since last update
    seconds_since_update = (datetime.datetime.utcnow() - sensor.last_connection).total_seconds()
    hours = int(seconds_since_update // 3600)

    # Generate connection status alert
    if hours > 4:
        alert = " ☠️"
    elif hours > 0:
        alerts = min(hours, 4)
        alert = f" ({'🤖' * alerts})"
    else:
        alert = ""

    return f"{sensor.name}{alert}: {measurement.humidity:.1f}% {icon}\n"


# API Endpoints
@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/humiditySensors/", response_model=list[HumiditySensorORM])
def read_sensors(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get list of all humidity sensors"""
    sensors = db.query(HumiditySensor).offset(skip).limit(limit).all()
    return sensors


@app.get("/humiditySensor/{sensor_id}", response_model=HumiditySensorORM)
def read_sensor(sensor_id: int, db: Session = Depends(get_db)):
    """Get specific sensor by ID"""
    sensor = db.query(HumiditySensor).filter(HumiditySensor.id == sensor_id).first()
    if sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")
    return sensor


@app.post("/humiditySensors/rename", response_model=HumiditySensorORM)
def rename_humidity_sensor(sensor_id: int, new_name: str, db: Session = Depends(get_db)):
    """Rename a humidity sensor"""
    sensor = db.query(HumiditySensor).filter(HumiditySensor.id == sensor_id).first()
    if sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")

    sensor.name = new_name
    db.commit()
    db.refresh(sensor)
    return sensor


@app.post("/humidityMeasurements/", response_model=HumidityMeasurementORM)
def create_measurement(measurement: HumidityMeasurementCreateORM, db: Session = Depends(get_db)):
    """Create a new humidity measurement"""
    logger.warning(f"Creating measurement {measurement}")

    # Get or create sensor
    sensor = db.query(HumiditySensor).filter(HumiditySensor.id == measurement.sensor_id).first()
    if sensor is None:
        sensor = HumiditySensor(id=measurement.sensor_id, name="Unknown")
        db.add(sensor)
        db.commit()
        db.refresh(sensor)

    # Update sensor's last connection time
    sensor.last_connection = datetime.datetime.utcnow()

    # Create measurement
    db_measurement = HumidityMeasurement(
        sensor_id=measurement.sensor_id,
        raw_value=measurement.raw_value,
        humidity=measurement.humidity,
        battery_voltage=measurement.battery_voltage
    )

    db.add(db_measurement)
    db.commit()
    db.refresh(db_measurement)

    return db_measurement


@app.get("/humidityMeasurements/sensor/{sensor_id}", response_model=list[HumidityMeasurementORM])
def read_sensor_measurements(sensor_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get measurements for a specific sensor"""
    measurements = db.query(HumidityMeasurement).filter(
        HumidityMeasurement.sensor_id == sensor_id
    ).offset(skip).limit(limit).all()
    return measurements


@app.get("/humidityOverview", response_model=str)
def read_humidity_overview(db: Session = Depends(get_db)):
    """Get overview of all sensors with their latest measurements"""
    result = ""
    sensors = db.query(HumiditySensor).order_by(HumiditySensor.last_connection).all()

    for sensor in sensors:
        measurement = db.query(HumidityMeasurement).filter(
            HumidityMeasurement.sensor_id == sensor.id
        ).order_by(HumidityMeasurement.date.desc()).first()

        if measurement:
            result += get_alert_text(sensor, measurement)

    return result


@app.get("/humidity/check", response_model=str)
def check_humidity(db: Session = Depends(get_db)):
    """Check for critical humidity levels across all sensors"""
    sensors = db.query(HumiditySensor).all()
    if not sensors:
        raise HTTPException(status_code=404, detail="No sensors found")

    result = ""
    for sensor in sensors:
        latest = db.query(HumidityMeasurement).filter(
            HumidityMeasurement.sensor_id == sensor.id
        ).order_by(HumidityMeasurement.date.desc()).first()

        if latest and (latest.humidity > sensor.overflow_level or latest.humidity < sensor.alert_level):
            result += get_alert_text(sensor, latest)

    return result


@app.get("/humiditySensors/plot")
def get_all_sensors_humidity_plot_7days(
        width: int = Query(15, ge=10, le=25),
        height: int = Query(8, ge=6, le=15),
        db: Session = Depends(get_db)
):
    """Generate humidity plot for all sensors over the last 7 days"""
    # Calculate date range
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=7)

    # Fetch all sensors
    sensors = db.query(HumiditySensor).all()
    if not sensors:
        raise HTTPException(status_code=404, detail="No sensors found")

    # Create plot
    plt.figure(figsize=(width, height))
    colors = plt.cm.Set3(range(len(sensors)))

    for i, sensor in enumerate(sensors):
        measurements = db.query(HumidityMeasurement).filter(
            HumidityMeasurement.sensor_id == sensor.id,
            HumidityMeasurement.date >= start_date,
            HumidityMeasurement.date <= end_date
        ).order_by(HumidityMeasurement.date).all()

        if measurements:
            timestamps = [m.date for m in measurements]
            humidity_values = [m.humidity for m in measurements]

            plt.plot(
                timestamps, humidity_values,
                color=colors[i], linewidth=2,
                label=f'{sensor.name} (ID: {sensor.id})', alpha=0.8
            )

    # Format plot
    plt.title('Humidity Measurements - All Sensors (Last 7 Days)', fontsize=16, fontweight='bold')
    plt.xlabel('Time', fontsize=12)
    plt.ylabel('Humidity (%)', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')

    # Format x-axis
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
    plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=12))
    plt.xticks(rotation=45)

    plt.tight_layout()

    # Generate image
    buffer = BytesIO()
    plt.savefig(buffer, format="png", dpi=150, bbox_inches='tight')
    buffer.seek(0)
    plt.close()

    return Response(content=buffer.getvalue(), media_type="image/png")


# main.py
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)