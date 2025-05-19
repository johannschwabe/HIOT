# api/monitor.py
import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Optional, List, Tuple

from api.schemas import HumiditySensor, HumidityMeasurement
from api.session import  SessionLocal
from tbd.telegram_notifier import TelegramNotifier, AlertLevel

logger = logging.getLogger("humidity-monitor")


class HumidityMonitor:
    """
    Monitors humidity sensors and measurements, sending alerts when thresholds are exceeded.
    """

    def __init__(
            self,
            check_interval: int = 300,  # 5 minutes
            humidity_threshold_high: float = 70.0,
            humidity_threshold_low: float = 30.0,
            connection_threshold_minutes: int = 70,
            telegram_notifier: Optional[TelegramNotifier] = None
    ):
        """
        Initialize the humidity monitor.

        Args:
            check_interval: How often to check sensors (in seconds)
            humidity_threshold_high: Alert if humidity exceeds this value
            humidity_threshold_low: Alert if humidity drops below this value
            connection_threshold_minutes: Alert if sensor hasn't reported in this many minutes
            telegram_notifier: TelegramNotifier instance for sending alerts
        """
        self.check_interval = check_interval
        self.humidity_threshold_high = humidity_threshold_high
        self.humidity_threshold_low = humidity_threshold_low
        self.connection_threshold_minutes = connection_threshold_minutes

        # Initialize notifier if not provided
        self.notifier = telegram_notifier or TelegramNotifier()

        # Store last alert time for each sensor to prevent alert spam
        self._last_humidity_alert: Dict[int, datetime] = {}
        self._last_connection_alert: Dict[int, datetime] = {}

        # Time between repeated alerts (4 hours)
        self.alert_cooldown = timedelta(hours=4)

        # Task for background monitoring
        self._monitor_task = None

    async def start(self):
        """Start the monitoring process"""
        if self._monitor_task:
            logger.warning("Monitor already running")
            return

        logger.info("Starting humidity monitoring service")
        await self.notifier.send_system_alert_async(
            "Monitoring Started",
            f"Humidity monitor starting with thresholds: {self.humidity_threshold_low}% - {self.humidity_threshold_high}%",
            level=AlertLevel.INFO
        )

        self._monitor_task = asyncio.create_task(self._monitoring_loop())

    async def stop(self):
        """Stop the monitoring process"""
        if not self._monitor_task:
            logger.warning("Monitor not running")
            return

        logger.info("Stopping humidity monitoring service")
        self._monitor_task.cancel()
        try:
            await self._monitor_task
        except asyncio.CancelledError:
            pass
        self._monitor_task = None

    async def _monitoring_loop(self):
        """Main monitoring loop that runs at regular intervals"""
        while True:
            try:
                await self._check_all_sensors()
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                # Send critical alert about monitor failure
                await self.notifier.send_system_alert_async(
                    "Monitor Error",
                    f"Monitoring service encountered an error: {str(e)}",
                    level=AlertLevel.CRITICAL
                )

            # Wait for next check interval
            await asyncio.sleep(self.check_interval)

    async def _check_all_sensors(self):
        """Check all sensors for issues"""
        db = SessionLocal()
        try:
            # Check connection status for all sensors
            await self._check_sensor_connections(db)

            # Check humidity levels for all sensors
            await self._check_humidity_levels(db)
        finally:
            db.close()

    async def _check_sensor_connections(self, db: Session):
        """Check if any sensors haven't reported within threshold time"""
        now = datetime.utcnow()
        threshold_time = now - timedelta(minutes=self.connection_threshold_minutes)

        # Find all sensors with old connections
        stale_sensors = db.query(HumiditySensor).filter(
            HumiditySensor.last_connection < threshold_time
        ).all()

        # Send alerts for stale sensors
        for sensor in stale_sensors:
            # Check if we've already alerted recently
            if (sensor.id in self._last_connection_alert and
                    now - self._last_connection_alert[sensor.id] < self.alert_cooldown):
                continue

            # Format time for human readability
            last_conn = sensor.last_connection.strftime("%Y-%m-%d %H:%M:%S UTC")

            # Send alert
            logger.warning(f"Sensor {sensor.name} (ID: {sensor.id}) hasn't connected since {last_conn}")
            alert_sent = await self.notifier.send_connection_alert_async(
                sensor_name=sensor.name,
                last_connection=last_conn,
                threshold=self.connection_threshold_minutes,
                level=AlertLevel.WARNING
            )

            if alert_sent:
                self._last_connection_alert[sensor.id] = now

    async def _check_humidity_levels(self, db: Session):
        """Check the latest humidity readings for all sensors"""
        # Get the latest reading for each sensor using a subquery
        latest_readings = self._get_latest_measurements(db)

        for sensor_id, sensor_name, humidity, timestamp in latest_readings:
            # Skip if no readings (this is handled by connection check)
            if humidity is None:
                continue

            now = datetime.utcnow()

            # Check if humidity is outside thresholds
            if humidity > self.humidity_threshold_high or humidity < self.humidity_threshold_low:
                # Check if we've already alerted recently
                if (sensor_id in self._last_humidity_alert and
                        now - self._last_humidity_alert[sensor_id] < self.alert_cooldown):
                    continue

                # Determine which threshold was exceeded
                threshold = (self.humidity_threshold_high if humidity > self.humidity_threshold_high
                             else self.humidity_threshold_low)

                # Determine alert level based on how far beyond threshold
                level = AlertLevel.WARNING
                if (humidity > self.humidity_threshold_high * 1.15 or
                        humidity < self.humidity_threshold_low * 0.85):
                    level = AlertLevel.CRITICAL

                # Format time for human readability
                formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")

                # Send alert
                logger.warning(f"Sensor {sensor_name} (ID: {sensor_id}) reported humidity of {humidity}%")
                alert_sent = await self.notifier.send_humidity_alert_async(
                    sensor_name=sensor_name,
                    humidity=humidity,
                    threshold=threshold,
                    timestamp=formatted_time,
                    level=level
                )

                if alert_sent:
                    self._last_humidity_alert[sensor_id] = now

    def _get_latest_measurements(self, db: Session) -> List[Tuple[int, str, float, datetime]]:
        """Get the latest humidity measurement for each sensor"""
        # Subquery to find the latest measurement ID for each sensor
        subq = db.query(
            HumidityMeasurement.sensor_id,
            func.max(HumidityMeasurement.id).label("latest_id")
        ).group_by(HumidityMeasurement.sensor_id).subquery("latest_measurements")

        # Join to get the actual measurement data
        results = db.query(
            HumiditySensor.id,
            HumiditySensor.name,
            HumidityMeasurement.humidity,
            HumidityMeasurement.date
        ).join(
            subq, HumiditySensor.id == subq.c.sensor_id, isouter=True
        ).join(
            HumidityMeasurement,
            (HumidityMeasurement.id == subq.c.latest_id) & (HumidityMeasurement.sensor_id == HumiditySensor.id),
            isouter=True
        ).all()

        return results