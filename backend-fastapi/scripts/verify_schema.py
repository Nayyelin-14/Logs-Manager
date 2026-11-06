#!/usr/bin/env python3
"""
Read-only schema verification script.
Connects to PostgreSQL and compares SQLAlchemy models with actual database schema.
Does NOT modify the database - only inspects and reports.
"""
import asyncio
import os
import sys
from typing import Dict, Set, List, Tuple
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.base import Base
from app.models.user import User
from app.models.alert import AlertRule, Alert, EmailNotification
from app.models.events import Event
from app.models.otp import Otp
from app.core.db_engine import create_engine


def _build_engine(database_url: str):
    """Build engine with proper SSL configuration (matching app/core/db_engine.py)."""
    return create_engine(database_url)


async def get_db_schema(engine) -> Dict:
    """Extract actual database schema using SQLAlchemy inspector."""
    async with engine.connect() as conn:
        # Run inspection in sync context
        def run_inspection(sync_conn):
            inspector = inspect(sync_conn)
            schema = {}
            
            for table_name in inspector.get_table_names():
                cols = {}
                for col in inspector.get_columns(table_name):
                    cols[col['name']] = {
                        'type': str(col['type']),
                        'nullable': col['nullable'],
                        'default': col['default'],
                        'autoincrement': col.get('autoincrement', False),
                    }
                
                indexes = {}
                for idx in inspector.get_indexes(table_name):
                    indexes[idx['name']] = {
                        'columns': idx['column_names'],
                        'unique': idx['unique'],
                    }
                
                fks = {}
                for fk in inspector.get_foreign_keys(table_name):
                    fks[fk['name']] = {
                        'constrained_columns': fk['constrained_columns'],
                        'referred_table': fk['referred_table'],
                        'referred_columns': fk['referred_columns'],
                    }
                
                pk = inspector.get_pk_constraint(table_name)
                
                schema[table_name] = {
                    'columns': cols,
                    'indexes': indexes,
                    'foreign_keys': fks,
                    'primary_key': pk,
                }
            return schema
        
        return await conn.run_sync(run_inspection)


def get_model_schema() -> Dict:
    """Extract expected schema from SQLAlchemy models."""
    schema = {}
    for table_name, table in Base.metadata.tables.items():
        cols = {}
        for col in table.columns:
            cols[col.name] = {
                'type': str(col.type),
                'nullable': col.nullable,
                'default': str(col.default) if col.default is not None else None,
                'autoincrement': col.autoincrement,
            }
        
        indexes = {}
        for idx in table.indexes:
            indexes[idx.name] = {
                'columns': [c.name for c in idx.columns],
                'unique': idx.unique,
            }
        
        fks = {}
        for fk in table.foreign_keys:
            fks[fk.name] = {
                'constrained_columns': [fk.parent.name],
                'referred_table': fk.column.table.name,
                'referred_columns': [fk.column.name],
            }
        
        pk_cols = [c.name for c in table.primary_key.columns]
        
        schema[table_name] = {
            'columns': cols,
            'indexes': indexes,
            'foreign_keys': fks,
            'primary_key': {'constrained_columns': pk_cols},
        }
    return schema


def compare_schemas(db_schema: Dict, model_schema: Dict) -> Tuple[List[str], List[str], List[str]]:
    """Compare database schema with model schema. Returns (missing_tables, extra_tables, differences)."""
    db_tables = set(db_schema.keys())
    model_tables = set(model_schema.keys())
    
    missing = sorted(model_tables - db_tables)  # Tables in model but not in DB
    extra = sorted(db_tables - model_tables)    # Tables in DB but not in model
    
    differences = []
    common_tables = db_tables & model_tables
    
    for table in sorted(common_tables):
        db_cols = set(db_schema[table]['columns'].keys())
        model_cols = set(model_schema[table]['columns'].keys())
        
        if db_cols != model_cols:
            missing_cols = model_cols - db_cols
            extra_cols = db_cols - model_cols
            if missing_cols:
                differences.append(f"{table}: MISSING columns in DB: {sorted(missing_cols)}")
            if extra_cols:
                differences.append(f"{table}: EXTRA columns in DB: {sorted(extra_cols)}")
        
        # Compare primary keys
        db_pk = set(db_schema[table]['primary_key'].get('constrained_columns', []))
        model_pk = set(model_schema[table]['primary_key'].get('constrained_columns', []))
        if db_pk != model_pk:
            differences.append(f"{table}: PK mismatch - DB: {db_pk}, Model: {model_pk}")
        
        # Compare indexes (by column sets)
        db_index_cols = {frozenset(idx['columns']) for idx in db_schema[table]['indexes'].values()}
        model_index_cols = {frozenset(idx['columns']) for idx in model_schema[table]['indexes'].values()}
        if db_index_cols != model_index_cols:
            missing_idx = model_index_cols - db_index_cols
            extra_idx = db_index_cols - model_index_cols
            if missing_idx:
                differences.append(f"{table}: MISSING indexes: {[list(c) for c in missing_idx]}")
            if extra_idx:
                differences.append(f"{table}: EXTRA indexes: {[list(c) for c in extra_idx]}")
    
    return missing, extra, differences


async def main():
    # Load environment using Settings (reads .env.local)
    # DO NOT call load_dotenv() - it loads .env with placeholders
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.core.config import get_settings
    
    settings = get_settings()
    database_url = settings.DATABASE_URL
    if not database_url:
        print("ERROR: DATABASE_URL not set in environment")
        sys.exit(1)
    
    # Don't print full URL (may contain credentials)
    parsed = urllib.parse.urlparse(database_url)
    print(f"Connecting to: {parsed.hostname}:{parsed.port}/{parsed.path.lstrip('/')}")
    
    # Create engine with proper SSL config (matching app/core/database.py)
    engine = _build_engine(database_url)
    
    try:
        # Test connection
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✓ Connected to PostgreSQL: {version[:80]}...")
        
        # Get actual DB schema
        print("\n📊 Inspecting database schema...")
        db_schema = await get_db_schema(engine)
        print(f"Found {len(db_schema)} tables in database")
        
        # Get model schema
        model_schema = get_model_schema()
        print(f"Model defines {len(model_schema)} tables")
        
        # Compare
        print("\n🔍 Comparing schemas...")
        missing, extra, differences = compare_schemas(db_schema, model_schema)
        
        # Report
        print("\n" + "="*60)
        print("SCHEMA COMPARISON REPORT")
        print("="*60)
        
        if missing:
            print(f"\n❌ MISSING TABLES ({len(missing)}):")
            for t in missing:
                print(f"  - {t}")
        else:
            print("\n✅ All model tables exist in database")
        
        if extra:
            print(f"\n⚠️  EXTRA TABLES IN DB ({len(extra)}):")
            for t in extra:
                print(f"  - {t}")
        
        if differences:
            print(f"\n🔄 SCHEMA DIFFERENCES ({len(differences)}):")
            for d in differences:
                print(f"  - {d}")
        else:
            print("\n✅ No column/index/PK differences found")
        
        print("\n" + "="*60)
        
        # Summary
        total_issues = len(missing) + len(extra) + len(differences)
        if total_issues == 0:
            print("🎉 SCHEMA MATCHES PERFECTLY")
            return 0
        else:
            print(f"⚠️  TOTAL ISSUES: {total_issues}")
            return 1
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))