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