"""Test the fixed Chess.com API client with real API calls."""
import asyncio
from app.services.chesscom_api import chesscom_api, ChessComAPIError


async def test_real_api():
    """Test with real Chess.com API."""
    
    test_cases = [
        ("GH_Wilder", "Mixed case - should work now"),
        ("gh_wilder", "Lowercase - should work"),
        ("hikaru", "Famous player"),
        ("nonexistentuser99999xyz", "Non-existent - should fail gracefully"),
    ]
    
    for username, description in test_cases:
        print(f"\n{'='*60}")
        print(f"Testing: {username} ({description})")
        
        try:
            profile = await chesscom_api.get_player_profile(username)
            print(f"✅ SUCCESS!")
            print(f"   Username: {profile.get('username')}")
            print(f"   Name: {profile.get('name', 'N/A')}")
            print(f"   Status: {profile.get('status', 'N/A')}")
            print(f"   URL: {profile.get('url', 'N/A')}")
            
        except ChessComAPIError as e:
            print(f"❌ ERROR: {str(e)}")
        
        # Small delay to respect rate limits
        await asyncio.sleep(2)

if __name__ == "__main__":
    print("🧪 Testing Fixed Chess.com API Client")
    print("Testing case sensitivity handling with redirects\n")
    asyncio.run(test_real_api())
