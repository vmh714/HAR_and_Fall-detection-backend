import requests
import json
import uuid
import sys

BASE_URL = "http://localhost:8001/api/v1"

def test_devices():
    print("--- Testing Devices API ---")
    
    # 1. GET /devices/
    print("\n[1] GET /devices/")
    try:
        response = requests.get(f"{BASE_URL}/devices/")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            devices = response.json()
            print(f"Count: {len(devices)}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")

    # 2. POST /devices/
    device_id = f"test_dev_{uuid.uuid4().hex[:6]}"
    print(f"\n[2] POST /devices/ (ID: {device_id})")
    payload = {
        "device_id": device_id,
        "firmware_version": "1.0.0-test",
        "is_active": True
    }
    try:
        response = requests.post(f"{BASE_URL}/devices/", json=payload)
        print(f"Status: {response.status_code}")
        if response.status_code in [200, 201]:
            print("Success!")
            device_data = response.json()
        else:
            print(f"Error 500 Detected!" if response.status_code == 500 else f"Error: {response.status_code}")
            print(f"Response: {response.text}")
            return # Stop if create fails
    except Exception as e:
        print(f"Exception: {e}")
        return

    # 3. PUT /devices/{id}
    print(f"\n[3] PUT /devices/{device_id}")
    update_payload = {
        "firmware_version": "1.1.0-test",
        "is_active": False
    }
    try:
        response = requests.put(f"{BASE_URL}/devices/{device_id}", json=update_payload)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("Update Success!")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")

    # 4. Fetch a wearer for assign test
    print("\n[4] Fetching a wearer for assign test...")
    try:
        wearer_resp = requests.get(f"{BASE_URL}/wearers/")
        if wearer_resp.status_code == 200 and len(wearer_resp.json()) > 0:
            wearer_id = wearer_resp.json()[0]['id']
            print(f"Found wearer: {wearer_id}")
            
            # POST /devices/{id}/assign
            print(f"\n[5] POST /devices/{device_id}/assign")
            assign_payload = {"wearer_id": wearer_id}
            response = requests.post(f"{BASE_URL}/devices/{device_id}/assign", json=assign_payload)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print("Assign Success!")
                
                # POST /devices/{id}/unassign
                print(f"\n[6] POST /devices/{device_id}/unassign")
                response = requests.post(f"{BASE_URL}/devices/{device_id}/unassign")
                print(f"Status: {response.status_code}")
                if response.status_code == 200:
                    print("Unassign Success!")
            else:
                print(f"Assign Error: {response.text}")
        else:
            print("No wearers found, skipping assign/unassign tests.")
    except Exception as e:
        print(f"Exception during wearer fetch/assign: {e}")

    # 5. DELETE /devices/{id}
    print(f"\n[7] DELETE /devices/{device_id}")
    try:
        response = requests.delete(f"{BASE_URL}/devices/{device_id}")
        print(f"Status: {response.status_code}")
        if response.status_code == 204:
            print("Delete Success!")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_devices()
