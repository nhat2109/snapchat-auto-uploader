import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from modules.ads_api.launcher import SnapAdsLauncher

def main():
    load_dotenv(PROJECT_ROOT / ".env")
    
    parser = argparse.ArgumentParser(description="Post a video as a Public Story (Creative) to Snapchat Profile.")
    parser.add_argument("--media-id", required=True, help="Media ID from Media Library")
    parser.add_argument("--name", help="Creative name")
    parser.add_argument("--headline", default="Check out our Story!", help="Headline")
    parser.add_argument("--brand-name", help="Brand name")
    args = parser.parse_args()

    # Load IDs from .env
    ad_account_id = os.getenv("SNAP_ADS_AD_ACCOUNT_ID")
    profile_id = os.getenv("SNAP_ADS_PROFILE_ID")
    
    if not all([ad_account_id, profile_id]):
        print("[ERROR] SNAP_ADS_AD_ACCOUNT_ID and SNAP_ADS_PROFILE_ID must be set in .env")
        return 1

    # Load session
    session_path = PROJECT_ROOT / os.getenv("SNAP_ADS_SESSION_PATH", "sessions/snap_ads_oauth.json")
    if not session_path.exists():
        print(f"[ERROR] Session file not found at {session_path}. Run Auth first.")
        return 1
        
    with open(session_path, "r") as f:
        session_data = json.load(f)
    
    token = session_data.get("access_token")
    if not token:
        print("[ERROR] No access token found in session.")
        return 1

    launcher = SnapAdsLauncher(token)
    
    print(f"Step 1/1: Creating Public Story creative...")
    name = args.name or f"Public Story {datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    try:
        # Creating a Creative linked to Public Profile.
        # This will appear in the Creative Library for the profile.
        creative_id = launcher.create_creative(
            ad_account_id=ad_account_id,
            media_id=args.media_id,
            name=name,
            headline=args.headline,
            call_to_action=None, 
            landing_url=None,
            brand_name=args.brand_name,
            profile_id=profile_id,
            status="ACTIVE"
        )
        
        print("\n[SUCCESS] Public Story Creative created successfully!")
        print(f"Creative ID: {creative_id}")
        print("-" * 50)
        print("LƯU Ý:")
        print("1. Nội dung này đã được đẩy lên thư viện Creative và liên kết với Profile.")
        print("2. Video sẽ xuất hiện trong mục 'Public Stories' của Profile bạn.")
        print("3. Bạn có thể kiểm tra trực tiếp trên app Snapchat hoặc Ads Manager.")
        print("-" * 50)
        
    except Exception as e:
        print(f"\n[FAILED] Failed to create Story: {e}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
