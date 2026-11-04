#!/usr/bin/env python3
"""
Test FastAPI app connectivity to Neon PostgreSQL and Redis.
Run this to verify the application can start and connect to services.
"""
import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# DO NOT call load_dotenv() - pydantic-settings handles .env.local loading
# Calling load_dotenv() loads .env with placeholders and pollutes environment


async def test_postgresql():
    """Test PostgreSQL connectivity and basic queries."""
    print("🔌 Testing PostgreSQL connection...")
    try:
        from sqlalchemy import text
        from app.core.database import engine
        
        async with engine.connect() as conn:
            # Test basic connectivity
            result = await conn.execute(text("SELECT 1 as test"))
            assert result.scalar() == 1
            
            # Get version
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"  ✓ Connected: {version[:80]}...")
            
            # Check current database
            result = await conn.execute(text("SELECT current_database(), current_user"))
            db, user = result.fetchone()
            print(f"  ✓ Database: {db}, User: {user}")
            
            # Check tables exist
            result = await conn.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """))
            tables = [row[0] for row in result.fetchall()]
            print(f"  ✓ Tables found ({len(tables)}): {', '.join(tables)}")
            
            # Check specific tables we care about
            expected = {'User', 'Otp', 'alert_rules', 'alerts', 'security_logs'}
            found = set(tables)
            missing = expected - found
            if missing:
                print(f"  ⚠️  Missing expected tables: {missing}")
            else:
                print(f"  ✓ All expected tables present")
            
            return True
        
    except Exception as e:
        print(f"  ❌ PostgreSQL connection failed: {e}")
        return False


async def test_redis():
    """Test Redis connectivity with unique temporary key."""
    print("\n🔌 Testing Redis connection...")
    try:
        import redis.asyncio as redis
        import time
        from app.core.config import get_settings
        
        settings = get_settings()
        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        
        # Test ping
        result = await client.ping()
        assert result is True
        print(f"  ✓ Redis PING successful")
        
        # Test set/get with unique temporary key (10s TTL)
        unique_key = f"fastapi_test_{int(time.time() * 1000)}_{os.getpid()}"
        await client.set(unique_key, "test_value", ex=10)
        value = await client.get(unique_key)
        assert value == "test_value"
        print(f"  ✓ Redis SET/GET successful (key: {unique_key}, TTL: 10s)")
        
        # Verify TTL
        ttl = await client.ttl(unique_key)
        assert 0 < ttl <= 10
        print(f"  ✓ Redis TTL verified: {ttl}s")
        
        # Clean up - delete only our test key
        await client.delete(unique_key)
        await client.aclose()
        return True
        
    except Exception as e:
        print(f"  ❌ Redis connection failed: {e}")
        return False


async def test_fastapi_import():
    """Test that FastAPI app imports without errors."""
    print("\n📦 Testing FastAPI app import...")
    try:
        from app.main import app
        print(f"  ✓ FastAPI app imported successfully")
        print(f"  ✓ Routes registered: {len(app.routes)}")
        return True
    except Exception as e:
        print(f"  ❌ FastAPI import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_model_imports():
    """Test that all models import correctly."""
    print("\n📦 Testing model imports...")
    try:
        from app.models.user import User
        from app.models.alert import AlertRule, Alert, EmailNotification
        from app.models.security_event import SecurityEvent
        from app.models.otp import Otp
        from app.models.base import Base
        
        # Verify table names match expectations
        assert User.__tablename__ == "User"
        assert Otp.__tablename__ == "Otp"
        assert AlertRule.__tablename__ == "alert_rules"
        assert Alert.__tablename__ == "alerts"
        assert EmailNotification.__tablename__ == "email_notifications"
        assert SecurityEvent.__tablename__ == "security_logs"
        
        print(f"  ✓ All models imported, table names verified")
        return True
    except Exception as e:
        print(f"  ❌ Model import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("="*60)
    print("FASTAPI LOCAL CONNECTIVITY TEST")
    print("="*60)
    print("⚠️  NOTE: This test verifies INFRASTRUCTURE connectivity only.")
    print("ℹ️  Auth compatibility is covered by tests/test_auth_compatibility.py (pytest).")
    print("="*60)
    
    results = []
    
    results.append(("PostgreSQL", await test_postgresql()))
    results.append(("Redis", await test_redis()))
    results.append(("FastAPI Import", await test_fastapi_import()))
    results.append(("Model Imports", await test_model_imports()))
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False
    
    print("="*60)
    if all_passed:
        print("🎉 ALL INFRASTRUCTURE CONNECTIVITY TESTS PASSED")
        return 0
    else:
        print("⚠️  SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))