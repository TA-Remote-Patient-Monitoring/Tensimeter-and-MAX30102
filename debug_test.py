"""Quick debug script to test endpoints."""
import httpx
import asyncio
import sys

BASE = "http://127.0.0.1:8000"

async def test():
    async with httpx.AsyncClient(timeout=10) as c:
        # 1. Register
        print("=== 1. Register ===")
        r = await c.post(f"{BASE}/api/auth/register", json={
            "name": "DebugUser",
            "email": f"debug_{id(c)}@test.com",
            "phone": f"08{id(c)}",
            "password": "TestPassword123!"
        })
        print(f"  Status: {r.status_code}")
        print(f"  Body: {r.text}")
        if r.status_code != 200:
            print("  FAILED at register!")
            return
        
        user_id = r.json()["id_user"]
        print(f"  user_id: {user_id}")

        # 2. Login
        print("\n=== 2. Login ===")
        r = await c.post(f"{BASE}/api/auth/login", json={
            "email": f"debug_{id(c)}@test.com",
            "password": "TestPassword123!"
        })
        print(f"  Status: {r.status_code}")
        print(f"  Body: {r.text}")
        if r.status_code != 200:
            print("  FAILED at login!")
            return
        
        token = r.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Create Profile
        print("\n=== 3. Create Profile ===")
        r = await c.post(f"{BASE}/api/profiles", data={
            "id_user": str(user_id),
            "name": "Test Profile",
            "age": "30",
            "gender": "Male",
            "tb": "170.0",
            "bb": "70.0",
        }, headers=headers)
        print(f"  Status: {r.status_code}")
        print(f"  Body: {r.text}")
        if r.status_code != 200:
            print("  FAILED at create profile!")
            return
        
        profile_id = r.json()["id"]

        # 4. Save Measurement
        print("\n=== 4. Save Measurement ===")
        r = await c.post(f"{BASE}/api/measurements", json={
            "id_user": user_id,
            "id_profile": profile_id,
            "sys": 120, "dia": 80, "bpm": 72,
            "ihb": 0, "mov": 0,
            "datetime": "2025-01-01T00:00:00"
        }, headers={"Content-Type": "application/json", **headers})
        print(f"  Status: {r.status_code}")
        print(f"  Body: {r.text}")
        if r.status_code != 200:
            print("  FAILED at save measurement!")
            return

        # 5. Get Profiles
        print("\n=== 5. Get Profiles ===")
        r = await c.get(f"{BASE}/api/profiles/{user_id}", headers=headers)
        print(f"  Status: {r.status_code}")
        print(f"  Body: {r.text[:200]}")

        # 6. Get Latest Measurement
        print("\n=== 6. Get Latest Measurement ===")
        r = await c.get(f"{BASE}/api/measurements/{profile_id}/latest", headers=headers)
        print(f"  Status: {r.status_code}")
        print(f"  Body: {r.text[:200]}")

        print("\n=== ALL TESTS PASSED ===")

asyncio.run(test())
