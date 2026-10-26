__all__ = ["AbstractExtraUser"]


def __getattr__(name):
    if name == "AbstractExtraUser":
        from django_jt.auth.models import AbstractExtraUser

        return AbstractExtraUser
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
