from app.api.analysis import router

print(f"Total routes: {len(router.routes)}")
for route in router.routes:
    print(f"{route.path} {route.methods}")
