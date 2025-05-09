import datetime

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
