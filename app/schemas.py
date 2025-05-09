import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()

from pydantic import BaseModel


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
