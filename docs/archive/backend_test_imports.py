"""Quick script to verify all critical packages are installed."""

print("🔍 Testing package imports...\n")

packages = [
    ("fastapi", "FastAPI"),
    ("supabase", "Supabase"),
    ("pytest", "Pytest"),
    ("chess", "python-chess"),
    ("httpx", "HTTPX"),
    ("pydantic", "Pydantic"),
    ("sqlalchemy", "SQLAlchemy"),
    ("redis", "Redis"),
]

failed = []
success = []

for module, name in packages:
    try:
        __import__(module)
        print(f"✅ {name}")
        success.append(name)
    except ImportError as e:
        print(f"❌ {name}: {e}")
        failed.append(name)

print(f"\n📊 Results: {len(success)}/{len(packages)} packages available")

if failed:
    print(f"\n⚠️ Missing packages: {', '.join(failed)}")
    print("Run: pip install -r requirements.txt")
else:
    print("\n🎉 All critical packages installed successfully!")
