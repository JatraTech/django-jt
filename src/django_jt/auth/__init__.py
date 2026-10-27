__all__ = ["Auth901UserMixin"]


def __getattr__(name):
    if name == "Auth901UserMixin":
        from django_jt.auth.models import Auth901UserMixin

        return Auth901UserMixin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
