from mozilla_django_oidc.auth import OIDCAuthenticationBackend

__all__ = ["OIDCBackend"]


class OIDCBackend(OIDCAuthenticationBackend):
    """Match users on ``auth901_sub``, then email; persist Auth901 claims."""

    def filter_users_by_claims(self, claims):
        sub = claims.get("sub")
        if sub and hasattr(self.UserModel, "auth901_sub"):
            users = self.UserModel.objects.filter(auth901_sub=sub)
            if users.exists():
                return users
        email = claims.get("email")
        if email:
            return self.UserModel.objects.filter(email__iexact=email)
        return self.UserModel.objects.none()

    def create_user(self, claims):
        user = super().create_user(claims)
        return self.update_user(user, claims)

    def update_user(self, user, claims):
        if hasattr(user, "auth901_sub") and claims.get("sub"):
            user.auth901_sub = claims["sub"]
        if claims.get("email"):
            user.email = claims["email"]
        if claims.get("given_name"):
            user.first_name = claims["given_name"]
        if claims.get("family_name"):
            user.last_name = claims["family_name"]
        username = claims.get("preferred_username")
        if username:
            user.username = username[:150]
        user.save()
        return user
