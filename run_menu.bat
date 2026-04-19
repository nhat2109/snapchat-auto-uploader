@echo off
chcp 65001 >nul
title SNAPCHAT AUTO-UPLOADER DASHBOARD
setlocal enabledelayedexpansion
title SNAPCHAT AUTO UPLOADER - MENU

:menu
cls
echo ======================================================
echo           SNAPCHAT AUTO-UPLOADER DASHBOARD
echo ======================================================
echo.
echo  [1] HE THONG ^& THIET LAP (SYSTEM ^& SETUP)
echo   1. Xac thuc OAuth (Access Token)
echo   2. Tra cuu Public Profile ID
echo  11. Xem danh sach Media ID da tai len
echo.
echo  [2] CO MAY VIRAL (CONTENT MACHINE - AI)
echo   9. ^> VIRAL MACHINE (San, Tai, Edit AI) ^<  [HOT]
echo.
echo  [3] DANG BAI ^& VAN HANH (PUBLISHING ^& OPS)
echo   3. Tai Video vao Media Library (Ads)
echo   5. Dang Public Story (Profile)
echo   6. Dang Spotlight (Trinh duyet - UI)
echo   7. ROBOT AUTO-PILOT (Cua so ngam)
echo.
echo  [4] QUANG CAO (PAID ADS)
echo   4. Chay chien dich Quang cao (Campaign)
echo.
echo  [5] KHAC (OTHERS)
echo   0. Huong dan su dung chi tiet
echo  10. Thoat chuong trinh
echo.
echo ======================================================
set /p choice="Chon chuc nang (1-11): "

if "%choice%"=="0" goto opt0
if "%choice%"=="1" goto opt1
if "%choice%"=="2" goto opt2
if "%choice%"=="3" goto opt3
if "%choice%"=="4" goto opt4
if "%choice%"=="5" goto opt5
if "%choice%"=="6" goto opt6
if "%choice%"=="7" goto opt7
if "%choice%"=="9" goto VIRAL
if "%choice%"=="11" goto opt11
if "%choice%"=="10" goto opt8

echo [WARNING] Lua chon khong hop le!
pause
goto menu

:opt0
cls
echo ======================================================
echo             HUONG DAN SU DUNG CHI TIET
echo ======================================================
echo  1. BUOC KHOI DAU: 
echo     - Chay so 1 de lay Token.
echo     - Chay so 2 de lay Profile ID (Luu vao .env).
echo(
echo  2. DANG QUANG CAO (ADS):
echo     - Chay so 3 de upload video -> Lay Media ID.
echo     - Chay so 4 -> Dan Media ID vao de tao Campaign.
echo(
echo  3. DANG STORY / SPOTLIGHT:
echo     - Dung so 5 de dang Story vao Creative Library.
echo     - Dung so 6 de mo trinh duyet dang Spotlight (Manual).
echo(
echo  4. CHE DO ROBOT AUTO-PILOT (SO 7):
echo     - Buoc 1: Chay so 6 de dang nhap 1 lan tren trinh duyet.
echo     - Buoc 2: Chon so 7 de Robot bat dau canh gac folder.
echo     - Buoc 3: Copy video .mp4 vao 'uploads/video/'.
echo     - Meo: Tao file .txt trung ten video de co Caption rieng.
echo(
echo  Luu y: Video dang xong se tu chuyen vao folder 'completed'.
echo ======================================================
pause
goto menu

:opt1
cls
echo ======================================================
echo  [HUONG DAN] XAC THUC OAUTH
echo ======================================================
echo  - Muc dich: Lay quyen truy cap tu Snapchat.
echo  - Cach lam: Mot trinh duyet se mo ra, ban dang nhap 
echo    va bam 'Allow'. Token se tu dong luu lai.
echo ======================================================
pause
echo [INFO] Dang chay xac thuc...
python scripts/run_ads_auth.py
pause
goto menu

:opt2
cls
echo ======================================================
echo  [HUONG DAN] TRA CUU PROFILE ID
echo ======================================================
echo  - Muc dich: Tim ma ID cua Public Profile cua ban.
echo  - Luu y: Ma nay can thiet de dang Story va Ads.
echo    ID se duoc hien ra man hinh, hay copy vao .env.
echo ======================================================
pause
echo [INFO] Dang tra cuu Profile...
python scripts/run_ads_profile_lookup.py
pause
goto menu

:opt3
cls
echo ======================================================
echo  [THU VIEN VIDEO] CHON VIDEO DE TAI LEN
echo ======================================================
echo  Robot dang quet thu muc: uploads\video va uploads\processed...
echo.

set count=0
:: Quet thu muc processed truoc (vi day la nhung video chuan nhat)
for %%f in (uploads\processed\*.mp4 uploads\processed\*.mov) do (
    set /a count+=1
    set "file_!count!=%%f"
    echo  [!count!] [SAN SANG] %%~nxf
)

:: Quet thu muc video goc
for %%f in (uploads\video\*.mp4 uploads\video\*.mov) do (
    set /a count+=1
    set "file_!count!=%%f"
    echo  [!count!] [GOC] %%~nxf
)

if %count%==0 (
    echo [INFO] Khong tim thay video nao trong thu muc uploads\video.
)

echo  [0] Nhap duong dan thu cong (hoac Keo tha file khac)
echo ======================================================
set /p gchoice="Chon so thu tu video: "

if "%gchoice%"=="0" (
    set /p vfile="Keo tha file .mp4 vao day: "
) else (
    if defined file_%gchoice% (
        set vfile=!file_%gchoice%!
    ) else (
        echo [WARNING] Lua chon khong hop le!
        pause
        goto opt3
    )
)

:: Go bo dau nhay neu co
if defined vfile set vfile=%vfile:"=%
if defined vfile set vfile=%vfile:'=%

echo [INFO] Dang kiem tra file: "%vfile%"
if not exist "%vfile%" (
    echo [ERROR] Khong tim thay file!
    pause
    goto menu
)

python scripts/run_ads_media_upload.py --file "%vfile%" --poll --cleanup
pause
goto menu

:opt11
cls
echo ======================================================
echo  [TRA CUU] DANH SACH MEDIA ID DA TAI LEN
echo ======================================================
python scripts/run_ads_media_lookup.py
pause
goto menu

:opt4
cls
echo ======================================================
echo  [HUONG DAN] CHAY CHIEN DICH QUANG CAO (ADS)
echo ======================================================
echo  - Muc dich: Tu dong tao Campaign, Ad Squad va Ad.
echo  - Luu y: Yeu cau phai co Media ID tu Buoc 3.
echo    Noi dung se duoc duyet de chay quang cao tra phi.
echo ======================================================
set /p mid="Nhap Media ID: "
if "%mid%"=="" (
    echo [ERROR] Ban phai nhap Media ID!
    pause
    goto menu
)
echo [INFO] Dang khoi tao chien dich cho Media %mid%...
python scripts/run_ads_launch.py --media-id %mid%
pause
goto menu

:opt5
cls
echo ======================================================
echo  [HUONG DAN] DANG PUBLIC STORY (CREATIVE LIBRARY)
echo ======================================================
echo  - Muc dich: Tao noi dung Story lien ket voi Profile.
echo  - Luu y: Noi dung se hien trong Creative Library.
echo    Ban co the dung Ads Manager de "Post" len Profile.
echo ======================================================
set /p smid="Nhap Media ID Video cho Story: "
if "%smid%"=="" (
    echo [ERROR] Ban phai nhap Media ID!
    pause
    goto menu
)
echo [INFO] Dang dang Public Story cho Media %smid%...
python scripts/run_ads_story_post.py --media-id %smid%
pause
goto menu

:opt6
cls
echo ======================================================
echo  [HUONG DAN] TU DONG DANG SPOTLIGHT (WEB)
echo ======================================================
echo  - Muc dich: Thue 'Robot' mo web va dang bai ho ban.
echo  - Yeu cau: Ban phai dang nhap 1 lan khi trinh duyet mo.
echo    Script se tu dong quet folder va dang tat ca video.
echo ======================================================
pause
echo [INFO] Dang chuan bi khoi chay Trinh duyet...
python scripts/run_spotlight_web_upload.py
pause
goto menu

:opt7
cls
echo ======================================================
echo  [HUONG DAN] ROBOT AUTO-PILOT (SIEU TU DONG)
echo ======================================================
echo  - Muc dich: Robot tu dong 'canh gac' folder video.
echo  - Cach dung: Cu copy video vao 'uploads/video',
echo    Robot se tu dong dang am tham duoi nen (Headless).
echo  - Yeu cau: Phai da chay Buoc 6 it nhat 1 lan.
echo ======================================================
pause
echo [INFO] Dang kich hoat Robot Auto-Pilot...
python scripts/spotlight_watcher.py --cleanup
pause
goto menu

:VIRAL
cls
echo ======================================================
echo           VIRAL MACHINE - AUTONOMOUS PIPELINE
echo ======================================================
echo Chuc nang nay se:
echo 1. Tu dong san video trending tu YouTube/TikTok
echo 2. Tu dong tai ve va xu ly AI (Chong duplicate)
echo 3. Luu vao thu muc uploads/processed/ de dang Story/Spotlight
echo.
echo Nhan phim bat ky de KICH HOAT Robot...
pause > nul
python scripts/run_viral_collect.py
echo.
echo Quy trinh hoan tat. Video moi da San sang!
pause
goto menu

:opt8
echo [INFO] Tam biet!
exit
