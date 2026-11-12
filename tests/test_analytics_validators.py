import json

from django_jt.analytics import AnalyticsData, AnalyticsDataItem, DataType


def test_analytics_data_iterates_and_serializes():
    payload = AnalyticsData(
        root=[
            AnalyticsDataItem(
                key="total",
                label="Total",
                value=0.0,
                type=DataType.AMOUNT,
            ),
        ]
    )
    items = list(payload)
    assert len(items) == 1
    assert items[0].key == "total"
    data = json.loads(payload.model_dump_json())
    assert data[0]["type"] == "amount"
