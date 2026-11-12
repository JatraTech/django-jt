from django.contrib.auth.backends import ModelBackend


class StatusBackend(ModelBackend):
    """
    Custom authentication backend that can be extended to check
    access halt reasons or other custom authentication logic.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        user = super().authenticate(request, username, password, **kwargs)

        # Add custom logic here if needed (e.g., check access_halt_reason)
        # if user and user.access_halt_reason:
        #     return None

        return user
