import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model()


@pytest.mark.django_db
def test_create_user_without_auth901_sub():
    user = User.objects.create_user(
        username="ada",
        email="ada@example.com",
        password="secret",
    )
    assert user.auth901_sub is None
    assert user.get_full_name() == ""


@pytest.mark.django_db
def test_auth901_sub_is_unique():
    User.objects.create_user(username="one", email="one@example.com", password="secret", auth901_sub="sub-1")
    with pytest.raises(IntegrityError):
        User.objects.create_user(username="two", email="two@example.com", password="secret", auth901_sub="sub-1")
