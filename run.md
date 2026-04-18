python scripts/snap_ads_callback_server.py --port 8787 --path /callback --exchange
ngrok http 8787
python scripts/run_ads_auth.py auth-url

#Re-auth với scope profile:
python scripts/run_ads_auth.py auth-url --scope "snapchat-marketing-api snapchat-profile-api"
python scripts/run_ads_auth.py exchange-code --code "<AUTHORIZATION_CODE>"

#Lấy profile_id:
python scripts/run_ads_profile_lookup.py


#Chạy full chain
SNAP_ADS_PROFILE_ID=<PROFILE_ID>

