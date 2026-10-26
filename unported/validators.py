from pydantic import BaseModel, RootModel

from app.constants import DataType


class AnalyticsDataItem(BaseModel):
    key: str
    label: str
    value: float
    type: DataType


class AnalyticsData(RootModel):
    root: list[AnalyticsDataItem]

    def __iter__(self):
        return iter(self.root)
