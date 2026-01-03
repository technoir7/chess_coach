import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_backend():
    print("Testing Backend API...")
    
    # 1. Create Game
    print("\n1. Creating Game...")
    resp = requests.post(f"{BASE_URL}/game/new")
    if resp.status_code != 200:
        print(f"FAILED: {resp.text}")
        return
    data = resp.json()
    game_id = data["game_id"]
    print(f"Game Created: {game_id}")
    
    # 2. Resign Game
    print("\n2. Resigning Game...")
    resp = requests.post(f"{BASE_URL}/game/{game_id}/resign")
    if resp.status_code != 200:
        print(f"FAILED: {resp.text}")
    else:
        state = resp.json()
        print(f"Resign Success: Game Over={state['game_over']}, Result={state['result']}")

    # 3. Create NEW Game for Draw
    print("\n3. Creating New Game for Draw...")
    resp = requests.post(f"{BASE_URL}/game/new")
    game_id_2 = resp.json()["game_id"]
    
    # 4. Offer Draw (Should be declined at start)
    print("\n4. Offering Draw...")
    resp = requests.post(f"{BASE_URL}/game/{game_id_2}/draw/offer")
    if resp.status_code != 200:
        print(f"FAILED: {resp.text}")
    else:
        data = resp.json()
        print(f"Draw Offer Result: Accepted={data['accepted']}, Message='{data['message']}'")

if __name__ == "__main__":
    test_backend()
