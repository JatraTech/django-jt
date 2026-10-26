from django.contrib.auth import get_user_model
from rest_framework import serializers, status
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django_jt.auth.oidc import invite_user


class InviteMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    given_name = serializers.CharField(max_length=150)
    family_name = serializers.CharField(max_length=150)


class InviteMemberView(APIView):
    """Invite a person into Auth901 and store their subject on the local user."""

    authentication_classes = [BasicAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = InviteMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        given_name = serializer.validated_data["given_name"]
        family_name = serializer.validated_data["family_name"]
        sub = invite_user(email, given_name, family_name)
        user = _local_user(email, given_name, family_name, sub)
        return Response({"id": sub, "email": user.email}, status=status.HTTP_201_CREATED)


def _local_user(email: str, given_name: str, family_name: str, sub: str):
    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        local = email.split("@", 1)[0][:150] or "user"
        username = local
        if User.objects.filter(username=username).exists():
            username = email[:150]
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=given_name,
            last_name=family_name,
        )
    if hasattr(user, "auth901_sub"):
        user.auth901_sub = sub
        user.save(update_fields=["auth901_sub"])
    return user
