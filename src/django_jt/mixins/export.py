import io

from django.db.models import QuerySet
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import decorators


def _require_export_deps():
    try:
        import polars as pl  # noqa: F401
        from styleframe import StyleFrame  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "ExportMixin requires django-jt[analytics] (polars and styleframe)."
        ) from exc


class ExportMixin:
    def __init__(self, url_path="export", queryset=None) -> None:
        self.url_path = url_path
        self.custom_queryset = queryset

    def get_export_file_name(self):
        now = timezone.now()
        try:
            filename = f"""{self.__class__.__name__.replace("ViewSet", "")}"""
        except Exception:
            filename = "file"
        return f"""{filename} {now.strftime("%m-%d-%Y")}"""

    @decorators.action(detail=False, methods=["get"], url_path="export/xlsx")
    def export_xlsx(
        self,
        request,
        queryset: QuerySet | None = None,
        columns: list | None = None,
        rename_columns: dict | None = None,
        ordered_column=None,
        exclude_columns=None,
        change_types=None,
        format_types=None,
        *args,
        **kwargs,
    ):
        _require_export_deps()
        import polars as pl
        from styleframe import StyleFrame

        queryset = queryset if queryset else self.filter_queryset(self.get_queryset())
        data = list(queryset.values(*(columns or [])))
        rename_columns = rename_columns or {}
        ordered_column = ordered_column or []
        exclude_columns = exclude_columns or []
        change_types = change_types or {}
        format_types = format_types or []

        if not data:
            return HttpResponse("No data to export", status=204)
        df = pl.DataFrame(data)

        if ordered_column:
            cols = [c for c in ordered_column if c in df.columns] + [
                c for c in df.columns if c not in ordered_column
            ]
            df = df.select(cols)

        for col, dtype in change_types.items():
            if col in df.columns:
                try:
                    df = df.with_columns(df[col].cast(dtype).alias(col))
                except Exception:
                    pass

        if format_types:
            for f in format_types:
                if callable(f):
                    for col in df.columns:
                        df = df.with_columns(
                            df[col].map_elements(lambda v, f=f, col=col: f(col, v)).alias(
                                col
                            )
                        )

        df = df.rename(rename_columns)
        df = df.drop([c for c in exclude_columns if c in df.columns])

        for col, dtype in zip(df.columns, df.dtypes, strict=True):
            if dtype == pl.Datetime or dtype == pl.Date:
                df = df.with_columns(
                    df[col].dt.strftime("%Y-%m-%dT%H:%M:%S").alias(col)
                )

        bytes_io = io.BytesIO()
        sf = StyleFrame(df.to_dicts())

        with StyleFrame.ExcelWriter(bytes_io) as writer:
            sf.to_excel(writer, best_fit=list(df.columns))
        filename = f"{self.get_export_file_name()}.xlsx"
        http_response = HttpResponse(
            bytes_io.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        http_response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return http_response
