from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import ASYNCHRONOUS
from app.core.config import settings

class InfluxDBManager:
    def __init__(self):
        self.client = InfluxDBClient(
            url=settings.INFLUXDB_URL,
            token=settings.INFLUXDB_TOKEN,
            org=settings.INFLUXDB_ORG
        )
        self.write_api = self.client.write_api(write_options=ASYNCHRONOUS)
        self.query_api = self.client.query_api()

    def write_point(self, point: Point):
        """Write a single point to InfluxDB"""
        self.write_api.write(bucket=settings.INFLUXDB_BUCKET, record=point)

    def close(self):
        """Close the client connection"""
        self.client.close()

# Singleton instance
influx_manager = InfluxDBManager()
