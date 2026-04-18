import os
import sys
import json
import requests
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from modules.ads_api import SnapAdsOAuthManager

def main():
    ad_account_id = os.getenv("SNAP_ADS_AD_ACCOUNT_ID", "").strip()
    if not ad_account_id:
        print("[ERROR] Thieu SNAP_ADS_AD_ACCOUNT_ID trong file .env")
        return 1

    api_base = os.getenv("SNAP_ADS_API_BASE", "https://adsapi.snapchat.com/v1").rstrip("/")
    auth = SnapAdsOAuthManager()
    
    try:
        access_token = auth.get_valid_access_token(auto_refresh=True)
    except Exception as e:
        print(f"[ERROR] OAuth error: {e}")
        return 1

    url = f"{api_base}/adaccounts/{ad_account_id}/media"
    print(f"[INFO] Dang lay danh sach Media tu Ad Account: {ad_account_id}...")

    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30
    )

    if response.status_code != 200:
        print(f"[ERROR] Khong the lay danh sach. Status: {response.status_code}")
        print(response.text)
        return 1

    data = response.json()
    media_list = data.get("media", [])

    if not media_list:
        print("[INFO] Chua co video nao duoc tai len tai khoan nay.")
        return 0

    print("\n" + "="*80)
    print(f"{'TEN VIDEO':<40} | {'MEDIA ID':<40} | {'TRANG THAI'}")
    print("-"*80)
    
    for item in media_list:
        m = item.get("media", {})
        name = m.get("name", "N/A")[:38]
        mid = m.get("id", "N/A")
        status = m.get("media_status", "N/A")
        print(f"{name:<40} | {mid:<40} | {status}")
    
    print("="*80)
    return 0

if __name__ == "__main__":
    sys.exit(main())
