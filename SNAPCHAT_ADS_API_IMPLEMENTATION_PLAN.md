# Snapchat Ads API Implementation Plan (Python)

## 1) Muc tieu va pham vi

Muc tieu tai lieu nay la chuyen cac ghi chu nghien cuu Snapchat Marketing API thanh ke hoach trien khai co the code ngay trong repo hien tai.

Pham vi:
- OAuth 2.0 Authorization Code + refresh token management.
- Tao va upload media.
- Tao creative, campaign, ad squad, ad theo dung thu tu phu thuoc.
- Thu thap metric tu Measurement API.
- Toi uu hoa co ban dua tren CPI/CPV/ROI rule-based.

Ngoai pham vi (phase sau):
- Dashboard web hoan chinh.
- ML bidding strategy.
- Multi-tenant phuc tap.

## 2) Nguyen tac ky thuat can khoa chat

- Base URL: `https://adsapi.snapchat.com/v1`
- Tien te: micro-currency (`1 USD = 1_000_000` units)
- Thoi gian: ISO 8601 UTC (`YYYY-MM-DDTHH:MM:SSZ`)
- Video recommendation: `1080x1920`, `MP4/MOV`, uu tien file nho (<32MB neu khong chunk upload)
- Idempotency: cac buoc tao object phai luu mapping local de tranh tao trung khi retry
- Retry strategy: exponential backoff + jitter cho loi `429/5xx`

## 3) Kien truc de xuat trong repo hien tai

Tao namespace rieng de khong anh huong luong automation UI dang co:

```text
modules/
  ads_api/
    __init__.py
    client.py               # HTTP client + auth header + retry
    auth.py                 # oauth exchange/refresh
    endpoints.py            # wrappers theo endpoint
    media.py                # create media + upload file
    builder.py              # orchestration media -> creative -> campaign -> squad -> ad
    measurement.py          # stats pull + normalization
    optimizer.py            # rule engine toi uu budget/status
    schemas.py              # dataclass/pydantic model request/response
    utils.py                # micro_currency/time helper

modules/database/
  models.py                # them bang metadata cho ads api
  db.py                    # CRUD cho token/object mapping/stats/action logs

scripts/
  run_ads_pipeline.py      # chay 1 pipeline tao quang cao
  run_measurement_loop.py  # scheduler polling + optimize
```

## 4) Bien moi truong can them (`.env`)

```env
# Snapchat Ads OAuth
SNAP_ADS_CLIENT_ID=
SNAP_ADS_CLIENT_SECRET=
SNAP_ADS_REDIRECT_URI=
SNAP_ADS_AUTH_BASE=https://accounts.snapchat.com
SNAP_ADS_API_BASE=https://adsapi.snapchat.com/v1

# Runtime context
SNAP_ADS_ORGANIZATION_ID=
SNAP_ADS_AD_ACCOUNT_ID=

# Upload + timeout
SNAP_ADS_TIMEOUT_SECONDS=60
SNAP_ADS_MAX_RETRIES=5
SNAP_ADS_RETRY_BASE_SECONDS=1.5

# Optimization rules
SNAP_TARGET_CPV_MICRO=50000
SNAP_TARGET_CPSWIPE_MICRO=200000
SNAP_MAX_DAILY_SPEND_MICRO=50000000
SNAP_PAUSE_AFTER_CONSECUTIVE_BAD_WINDOWS=3

# Polling
SNAP_STATS_GRANULARITY=DAY
SNAP_STATS_LOOKBACK_DAYS=3
SNAP_MEASUREMENT_POLL_MINUTES=30
```

## 5) Thiet ke DB toi thieu cho luong Ads API

Neu dang dung SQLAlchemy trong `modules/database/models.py`, them cac bang:

1. `snap_oauth_tokens`
- `id`
- `ad_account_id` (unique)
- `access_token` (encrypted at rest)
- `refresh_token` (encrypted at rest)
- `expires_at_utc` (datetime)
- `updated_at_utc`

2. `snap_ads_objects`
- `id`
- `ad_account_id`
- `local_job_id` (nullable)
- `entity_type` (`media|creative|campaign|adsquad|ad`)
- `entity_id` (Snap ID)
- `name`
- `status`
- `payload_json`
- `created_at_utc`

3. `snap_stats_snapshots`
- `id`
- `entity_type`
- `entity_id`
- `granularity` (`TOTAL|DAY|HOUR`)
- `start_time_utc`
- `end_time_utc`
- `impressions`
- `swipes`
- `spend_micro`
- `view_completion`
- `screen_time_millis`
- `raw_json`
- `fetched_at_utc`

4. `snap_optimization_actions`
- `id`
- `entity_type`
- `entity_id`
- `rule_name`
- `decision` (`decrease_budget|pause|no_action`)
- `before_json`
- `after_json`
- `reason`
- `created_at_utc`

## 6) Luong xac thuc (OAuth 2.0)

### 6.1 Authorization URL generation
- Tao URL voi `client_id`, `redirect_uri`, `response_type=code`, `scope`.
- Sinh `state` ngau nhien, luu vao DB/session de verify callback.

### 6.2 Exchange code -> token
- Endpoint token cua Snap (form-encoded).
- Luu `access_token`, `refresh_token`, `expires_in`.
- Quy doi `expires_at_utc = now + expires_in - safety_window(120s)`.

### 6.3 Auto refresh
- Moi request API:
1. Doc token theo `ad_account_id`.
2. Neu `now >= expires_at_utc`, goi refresh.
3. Neu refresh fail (invalid_grant), danh dau token stale va yeu cau authorize lai.

### 6.4 Security checklist
- Khong log token raw.
- Ma hoa token truoc khi ghi DB (it nhat AES/Fernet key tu env).
- Rotate client secret theo policy noi bo.

## 7) Luong upload du lieu (create ad stack)

Trinh tu bat buoc:
1. `POST /adaccounts/{ad_account_id}/media` (create media object)
2. `POST /media/{media_id}/upload` (multipart upload file)
3. `POST /adaccounts/{ad_account_id}/creatives`
4. `POST /adaccounts/{ad_account_id}/campaigns`
5. `POST /campaigns/{campaign_id}/adsquads`
6. `POST /adsquads/{ad_squad_id}/ads`

### 7.1 Orchestration strategy
- Tao class `AdsPipelineBuilder`:
1. Validate input (media path, objective, budget, targeting)
2. Upload media
3. Tao creative
4. Tao campaign
5. Tao ad squad
6. Tao ad
7. Commit mapping object vao DB

### 7.2 Input contract (de code nhanh)
- `media_path`
- `headline`
- `brand_name`
- `attachment_url`
- `campaign_name`, `objective`
- `adsquad_name`, `daily_budget_micro`, `bid_micro`
- `targeting` (geo, age, gender, interests)
- `ad_name`, `status` (ACTIVE/PAUSED)

### 7.3 Validation can co
- File ton tai va dung dinh dang (`.mp4/.mov/.jpg/.png`)
- Video ratio/size hop le (can ffprobe helper)
- Budget, bid > 0 va dang micro-currency
- Time windows (`start_time < end_time`)

## 8) Luong measurement va optimization

### 8.1 Pull stats
- Endpoint: `GET /v1/{entity_type}/{entity_id}/stats`
- Entity theo cap:
1. `ads` de quyet dinh toi uu chi tiet
2. `adsquads` de xu ly budget level
3. `campaigns` de tong hop hieu suat

### 8.2 Metric normalized
- `impressions`
- `swipes`
- `spend_micro`
- `view_completion`
- `screen_time_millis`
- Derived:
  - `cpv_micro = spend_micro / max(view_completion,1)`
  - `cpswipe_micro = spend_micro / max(swipes,1)`
  - `roi = (estimated_value_micro - spend_micro) / max(spend_micro,1)`

### 8.3 Rule engine v1 (deterministic)
- Rule 1: Neu `cpv_micro > SNAP_TARGET_CPV_MICRO` lien tiep `N` windows -> giam budget 10-20%.
- Rule 2: Neu `cpswipe_micro` qua nguong va spend tang -> pause ad squad.
- Rule 3: Neu ad outperform (cpv thap hon target 30% trong 2 windows) -> tang budget nho (5-10%).

### 8.4 Action safety
- Cooldown toi thieu 6-12h giua 2 lan doi budget cho cung 1 ad squad.
- Moi action phai log vao `snap_optimization_actions`.
- Co `dry_run=true` cho giai doan test.

## 9) API client va error handling

### 9.1 HTTP client contract (`client.py`)
- Method: `get/post/put/delete`
- Tu dong attach `Authorization: Bearer <access_token>`
- Timeout per request
- Retry `429,500,502,503,504` (max retries env config)
- Parse error body thanh exception typed:
  - `SnapAuthError`
  - `SnapRateLimitError`
  - `SnapValidationError`
  - `SnapServerError`

### 9.2 Logging/observability
- Structured log JSON:
  - `request_id`
  - `endpoint`
  - `entity_type/entity_id`
  - `duration_ms`
  - `status_code`
  - `error_code`
- Correlation id cho 1 pipeline run.

## 10) Lo trinh trien khai (8 buoc)

1. Scaffold module `modules/ads_api/*` va env keys.
2. Implement OAuth flow (`auth.py`) + luu token DB.
3. Implement base client + retry + typed exceptions.
4. Implement media + creative endpoint wrappers.
5. Implement campaign/adsquad/ad wrappers + orchestration builder.
6. Implement measurement pull + luu snapshot.
7. Implement optimizer rules + dry-run + action logging.
8. Them script CLI de chay end-to-end va scheduler loop.

## 11) Ke hoach test

### 11.1 Unit tests
- `utils`: micro currency convert, ISO parser, safe divide.
- `auth`: token expiry/refresh decision.
- `optimizer`: input metrics -> expected decision.

### 11.2 Integration tests (sandbox/ad account test)
- OAuth authorize + refresh thanh cong.
- Create full stack object (media -> ad) voi test budget nho.
- Pull stats 24h, verify schema parse dung.

### 11.3 Failure tests
- Invalid token -> trigger refresh -> fallback re-auth.
- Rate limit -> retry va eventually fail dung exception.
- Upload file loi format -> validation chot truoc khi goi API.

## 12) Definition of Done (DoD)

- Co the tao 1 ad moi tu media local bang 1 lenh CLI.
- Token duoc auto refresh on-demand, khong can can thiep tay trong runtime binh thuong.
- Measurement job chay dinh ky va luu metric vao DB.
- Optimizer co `dry_run` + `apply` mode, co action logs day du.
- Co tai lieu runbook ngan (`commands + env + known errors`).

## 13) CLI de xuat de van hanh

```bash
# 1) Tao authorization URL
python scripts/run_ads_pipeline.py auth-url

# 2) Exchange code lay token
python scripts/run_ads_pipeline.py exchange-code --code "<AUTH_CODE>"

# 3) Tao full ad stack
python scripts/run_ads_pipeline.py create-ad --config configs/ad_job_001.json

# 4) Chay measurement + optimize loop
python scripts/run_measurement_loop.py --apply=false
python scripts/run_measurement_loop.py --apply=true
```

## 14) RUI RO chinh va cach giam thieu

- API schema thay doi: dong bang request/response schema versioned + contract tests.
- Rate limit manh khi scale: queue theo ad_account, throttle global.
- Mapping object loi do retry: idempotency key + transaction DB.
- Decision toi uu gay sut hieu suat: bat dau `dry_run`, rollout theo whitelist adsquad.

## 15) Backlog phase 2

- Async reporting (`async=true`) + export CSV/XLS cho dataset lon.
- Breakdown analytics (`GEO/DEMO/INTEREST/DEVICE`) + dashboard.
- Rule engine nang cao theo objective tung campaign.
- Alerting qua Slack/Email khi vuot spend threshold.

