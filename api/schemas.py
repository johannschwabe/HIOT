import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from pydantic import BaseModel

from api.session import Base


class HumiditySensorORM(BaseModel):
    id: int
    name: str
    last_connection: datetime.datetime
    alert_level: int
    warning_level: int
    critical_level: int
    overflow_level: int

    class Config:
        orm_mode = True


class HumidityMeasurementORM(BaseModel):
    id: int
    sensor_id: int
    date: datetime.datetime
    raw_value: float
    humidity: float

    class Config:
        orm_mode = True


class HumidityMeasurementCreateORM(BaseModel):
    sensor_id: int
    raw_value: float
    humidity: float
    battery_voltage: float = 0.0

    class Config:
        orm_mode = True

class HumiditySensor(Base):
    __tablename__ = "humidity_sensors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    last_connection = Column(DateTime, default=datetime.datetime.utcnow)
    overflow_level = Column(Integer, default=60)
    alert_level = Column(Integer, default=30)
    warning_level = Column(Integer, default=20)
    critical_level = Column(Integer, default=10)


class HumidityMeasurement(Base):
    __tablename__ = "humidity_measurements"

    id = Column(Integer, primary_key=True, index=True)
    sensor_id = Column(Integer, ForeignKey("humidity_sensors.id"))
    raw_value = Column(Float, nullable=False)
    humidity = Column(Float, nullable=False)
    date = Column(DateTime, default=datetime.datetime.utcnow)
    battery_voltage = Column(Float, nullable=False, default=0.0)


