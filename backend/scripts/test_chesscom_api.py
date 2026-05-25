"""Test Chess.com API directly to understand case sensitivity and error handling."""
import asyncio
import httpx

async def test_chesscom_api():
    """Test various scenarios with Chess.com API."""
    
    test_cases = [
        ("gh_wilder", "lowercase - should work"),
        ("GH_Wilder", "mixed case - testing"),
        ("GH_WILDER", "uppercase - testing"),
        ("nonexistentuser12345xyz", "non-existent user"),
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for username, description in test_cases:
            url = f"https://api.chess.com/pub/player/{username}"
            print(f"\n{'='*60}")
            print(f"Testing: {username} ({description})")
            print(f"URL: {url}")
            
            try:
                # Test WITHOUT User-Agent
                print("\n--- Without User-Agent ---")
                response = await client.get(url)
                print(f"Status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"Success! Username in response: {data.get('username', 'N/A')}")
                    print(f"Player URL: {data.get('url', 'N/A')}")
                else:
                    print(f"Response: {response.text[:200]}")
                    
            except httpx.HTTPStatusError as e:
                print(f"HTTP Error: {e.response.status_code}")
                print(f"Response: {e.response.text[:200]}")
            except Exception as e:
                print(f"Error: {str(e)}")
            
            # Small delay to respect rate limits
            await asyncio.sleep(1)
            
            try:
                # Test WITH proper User-Agent
                print("\n--- With User-Agent ---")
                headers = {
                    "User-Agent": "ChessInsightAI/1.0 (contact: test@example.com)",
                    "Accept": "application/json"
                }
                response = await client.get(url, headers=headers)
                print(f"Status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"Success! Username in response: {data.get('username', 'N/A')}")
                    print(f"Name: {data.get('name', 'N/A')}")
                    print(f"Title: {data.get('title', 'N/A')}")
                    print(f"Status: {data.get('status', 'N/A')}")
                else:
                    print(f"Response: {response.text[:200]}")
                    
            except httpx.HTTPStatusError as e:
                print(f"HTTP Error: {e.response.status_code}")
                print(f"Response: {e.response.text[:200]}")
            except Exception as e:
                print(f"Error: {str(e)}")
            
            # Delay between test cases
            await asyncio.sleep(2)

if __name__ == "__main__":
    print("🧪 Testing Chess.com API Behavior")
    print("Testing case sensitivity and error responses\n")
    asyncio.run(test_chesscom_api())
