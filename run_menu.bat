@echo off
setlocal enabledelayedexpansion
title SNAPCHAT AUTO UPLOADER - MENU

:menu
cls
echo ======================================================
echo           SNAPCHAT AUTO UPLOADER DASHBOARD
echo ======================================================
echo  0. [HUONG DAN] Xem huong dan su dung
echo  1. [KHOI TAO] Xac thuc OAuth (Lay Access Token)
echo  2. [TRA CUU] Tim Public Profile ID
echo  3. [TAI LEN] Video vao Media Library
echo  4. [QUANG CAO] Chay chien dich (Campaign/Ad)
echo  5. [STORY] Dang Public Story (Noi dung Profile)
echo  6. [SPOTLIGHT] Tu dong dang Spotlight (TRINH DUYET)
echo  7. [AUTO-PILOT] Robot tu dong theo doi thu muc va dang bai
echo  8. [THOAT] Thoat chuong trinh
echo ======================================================
set /p opt="Chon chuc nang (0-8): "

if "%opt%"=="0" goto opt0
if "%opt%"=="1" goto opt1
if "%opt%"=="2" goto opt2
if "%opt%"=="3" goto opt3
if "%opt%"=="4" goto opt4
if "%opt%"=="5" goto opt5
if "%opt%"=="6" goto opt6
if "%opt%"=="7" goto opt7
if "%opt%"=="8" goto opt8

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
echo  [HUONG DAN] TAI VIDEO LEN THU VIEN
echo ======================================================
echo  - Muc dich: Day file video tu may tinh len Snapchat.
echo  - Ket qua: Ban se nhan duoc mot 'Media ID'.
echo    Hay copy Media ID nay de dung cho Buoc 4 hoac 5.
echo ======================================================
set /p vfile="Nhap duong dan video (mac dinh: uploads/video/snap_1.mp4): "
if "!vfile!"=="" set vfile=uploads/video/snap_1.mp4
echo [INFO] Dang tai len file: !vfile!
python scripts/run_ads_media_upload.py --file !vfile! --poll
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
python scripts/spotlight_watcher.py
pause
goto menu

:opt8
echo [INFO] Tam biet!
exit
