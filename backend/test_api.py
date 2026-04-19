import requests
import sys

BASE_URL = "http://localhost:8000/api"

def test_endpoints():
    print("Testing NexusNet CRM API...")
    
    try:
        # Test Customers
        res = requests.get(f"{BASE_URL}/customers")
        assert res.status_code == 200, "Failed /customers"
        cust_data = res.json()
        assert "items" in cust_data
        
        if len(cust_data["items"]) == 0:
            print("No customers found, skipping rest.")
            return
            
        cust_id = cust_data["items"][0]["id"]
        
        # Test Customer Detail
        res = requests.get(f"{BASE_URL}/customers/{cust_id}")
        assert res.status_code == 200, f"Failed /customers/{cust_id}"
        
        # Test Tickets
        res = requests.get(f"{BASE_URL}/tickets")
        assert res.status_code == 200, "Failed /tickets"
        
        # Test Devices
        res = requests.get(f"{BASE_URL}/devices")
        assert res.status_code == 200, "Failed /devices"
        
        # Test Metrics
        res = requests.get(f"{BASE_URL}/metrics/{cust_id}")
        assert res.status_code == 200, f"Failed /metrics/{cust_id}"
        
        # Test Health
        res = requests.get(f"{BASE_URL}/health/{cust_id}")
        assert res.status_code == 200, f"Failed /health/{cust_id}"
        
        # Test Churn
        res = requests.get(f"{BASE_URL}/churn")
        assert res.status_code == 200, "Failed /churn"
        
        print("All API endpoints responded with 200 OK!")
        
    except requests.exceptions.ConnectionError:
        print("Could not connect to API. Is the server running?")
        sys.exit(1)
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_endpoints()
