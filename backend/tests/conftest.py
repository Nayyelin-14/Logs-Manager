@pytest.fixture()
def client():
    """Test client with the test-only flagged route registered."""
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api.routes.health import require_feature

    # Create a test-only app that includes the health router plus a
    # test-only flagged route. This route is NOT registered in the
    # production app, so it only exists during tests.
    test_app = FastAPI()
    test_app.include_router(app.router)

    @test_app.get("/features/test-flagged")
    async def test_flagged_route(_=Depends(require_feature("test_flag"))):
        """Test-only route behind FEATURE_TEST_FLAG_ENABLED."""
        return {"status": "ok", "feature": "test_flag"}

    with TestClient(test_app) as test_client:
        yield test_client