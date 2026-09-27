from django.core.cache import cache

cache.set("test_key", "Redis is working", timeout=60)

print(cache.get("test_key"))