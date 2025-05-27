import datetime
import logging
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.schemas import HumiditySensor, HumidityMeasurement, HumidityMeasurementCreateORM, HumiditySensorORM, \
    HumidityMeasurementORM
from api.session import get_db, Base, engine
from fastapi.responses import Response
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO

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
        measurement: HumidityMeasurement = (db.query(HumidityMeasurement)
                                            .filter(HumidityMeasurement.sensor_id == sensor.id)
                                            .order_by(HumidityMeasurement.date.desc()).first())
        if measurement:
            res += get_alert_text(sensor, measurement)
    return res


@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/humidity/check", response_model=str)
def check_humidity(db: Session = Depends(get_db)):
    """
    Check the latest humidity measurement for all sensors

    Returns:
        Latest measurement for each sensor if critical
    """
    sensors = db.query(HumiditySensor).all()
    if not sensors:
        raise HTTPException(status_code=404, detail="No sensors found")

    res = ""
    for sensor in sensors:
        latest_measurement = db.query(HumidityMeasurement).filter(
            HumidityMeasurement.sensor_id == sensor.id
        ).order_by(HumidityMeasurement.date.desc()).first()

        if latest_measurement and (
                latest_measurement.humidity > sensor.overflow_level or
                latest_measurement.humidity < sensor.alert_level
        ):
            res += get_alert_text(sensor, latest_measurement)

    return res


@app.post("/humiditySensors/rename", response_model=HumiditySensorORM)
def rename_humidity_sensor(sensor_id: int, new_name: str, db: Session = Depends(get_db)):
    db_sensor = db.query(HumiditySensor).filter(HumiditySensor.id == sensor_id).first()
    if db_sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")

    db.query(HumiditySensor).filter(HumiditySensor.id == sensor_id).update({"name": new_name})
    db.commit()
    return db.query(HumiditySensor).filter(HumiditySensor.id == sensor_id).first()


@app.get("/humiditySensors/plot")
def get_all_sensors_humidity_plot_7days(
        width: int = Query(15, ge=10, le=25),
        height: int = Query(8, ge=6, le=15),
        db: Session = Depends(get_db)
):
    """
    Generate a plot showing humidity measurements for ALL sensors in the last 7 days

    Args:
        format: Output format (png, jpg, svg, base64)
        width: Plot width in inches
        height: Plot height in inches

    Returns:
        Plot as image response or base64 string
    """

    # Calculate date range (last 7 days)
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=7)

    # Fetch all sensors
    sensors = db.query(HumiditySensor).all()
    if not sensors:
        raise HTTPException(status_code=404, detail="No sensors found")

    # Create the plot
    plt.figure(figsize=(width, height))

    colors = plt.cm.Set3(range(len(sensors)))  # Generate different colors

    for i, sensor in enumerate(sensors):
        # Fetch measurements for this sensor
        measurements = db.query(HumidityMeasurement).filter(
            HumidityMeasurement.sensor_id == sensor.id,
            HumidityMeasurement.date >= start_date,
            HumidityMeasurement.date <= end_date
        ).order_by(HumidityMeasurement.date).all()

        if measurements:
            timestamps = [m.date for m in measurements]
            humidity_values = [m.humidity for m in measurements]

            plt.plot(timestamps, humidity_values,
                     color=colors[i], linewidth=2,
                     label=f'{sensor.name} (ID: {sensor.id})', alpha=0.8)

    # Formatting
    plt.title('Humidity Measurements - All Sensors (Last 7 Days)', fontsize=16, fontweight='bold')
    plt.xlabel('Time', fontsize=12)
    plt.ylabel('Humidity (%)', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.ylim(0, 100)
    # Format x-axis
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
    plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=12))
    plt.xticks(rotation=45)

    plt.tight_layout()

    # Generate output based on format (same logic as above)
    buffer = BytesIO()


    plt.savefig(buffer, format="png", dpi=150, bbox_inches='tight')
    buffer.seek(0)
    plt.close()

    return Response(content=buffer.getvalue(), media_type="image/png")


def get_alert_text(sensor: HumiditySensor, measurement: HumidityMeasurement):
    icon = "🌿"
    if measurement.humidity > sensor.overflow_level:
        icon = "🤿"
    if measurement.humidity < sensor.alert_level:
        icon = "🍂"
    if measurement.humidity < sensor.warning_level:
        icon = "🔥"
    if measurement.humidity < sensor.critical_level:
        icon = "💀"
    seconds_since_update = (datetime.datetime.utcnow() - sensor.last_connection).total_seconds()
    hours = seconds_since_update // 3600
    alerts = min(hours, 4)
    alert = ""
    logger.warning(f"Hours passed {hours}")
    if alerts > 0:
        alert = " ({alerts * '🤖'})"
    if hours > 4:
        alert = " ☠️"
    return f"{sensor.name}{alert}: {measurement.humidity:.1f}% {icon}\n"