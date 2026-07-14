import uuid

from auth.models import User
from auth.schemas import RegisterRequest
from auth.service import AuthService
from services.subscription import SubscriptionService, UsageService


def _create_user() -> User:
    email = f"subscription-{uuid.uuid4().hex[:8]}@example.com"
    service = AuthService()
    service.register(RegisterRequest(name="Subscription User", email=email, password="secret123"))
    return service.session.query(User).filter(User.email == email).first()


def test_free_plan_enforces_upload_quota() -> None:
    user = _create_user()
    usage_service = UsageService()

    result = usage_service.enforce_upload_quota(user.id, size_bytes=11 * 1024 * 1024, pages=1)

    assert result["success"] is False
    assert result["errorCode"] == "PLAN_LIMIT_REACHED"
    assert result["recommendedPlan"] == "PRO"


def test_plan_change_updates_subscription_and_user_fields() -> None:
    user = _create_user()
    subscription_service = SubscriptionService()

    changed = subscription_service.change_plan(user.id, "PRO")

    assert changed["planCode"] == "PRO"
    assert changed["currentPlan"] == "PRO"

    refreshed_user = subscription_service.session.query(User).get(user.id)
    assert refreshed_user.current_plan == "PRO"
    assert refreshed_user.subscription_status == "active"
