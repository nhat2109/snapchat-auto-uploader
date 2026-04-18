@echo off
setlocal enabledelayedexpansion
title SNAPCHAT AUTO UPLOADER - MENU

:menu
cls
echo ======================================================
echo           SNAPCHAT AUTO UPLOADER DASHBOARD
echo ======================================================
echo  1. [KHOI TAO] Xac thuc OAuth (Lay Access Token)
echo  2. [TRA CUU] Tim Public Profile ID
echo  3. [TAI LEN] Video vao Media Library
echo  4. [QUANG CAO] Chay chien dich (Campaign/Ad)
echo  5. [STORY] Dang Public Story (Noi dung Profile)
echo  6. [SPOTLIGHT] Tu dong dang Spotlight (TRINH DUYET)
echo  7. [THOAT] Thoat chuong trinh
echo ======================================================
set /p opt="Chon chuc nang (1-7): "

if "%opt%"=="1" (
    echo [INFO] Dang chay xac thuc...
    python scripts/run_ads_auth.py
    pause
    goto menu
)

if "%opt%"=="2" (
    echo [INFO] Dang tra cuu Profile...
    python scripts/run_ads_profile_lookup.py
    pause
    goto menu
)

if "%opt%"=="3" (
    set /p vfile="Nhap duong dan video (mac dinh: uploads/video/snap_1.mp4): "
    if "!vfile!"=="" set vfile=uploads/video/snap_1.mp4
    echo [INFO] Dang tai len file: !vfile!
    python scripts/run_ads_media_upload.py --file !vfile! --poll
    pause
    goto menu
)

if "%opt%"=="4" (
    set /p mid="Nhap Media ID: "
    if "!mid!"=="" (
        echo [ERROR] Ban phai nhap Media ID!
        pause
        goto menu
    )
    echo [INFO] Dang khoi tao chien dich cho Media !mid!...
    python scripts/run_ads_launch.py --media-id !mid!
    pause
    goto menu
)

if "%opt%"=="5" (
    set /p smid="Nhap Media ID Video cho Story: "
    if "!smid!"=="" (
        echo [ERROR] Ban phai nhap Media ID!
        pause
        goto menu
    )
    echo [INFO] Dang dang Public Story cho Media !smid!...
    python scripts/run_ads_story_post.py --media-id !smid!
    pause
    goto menu
)

if "%opt%"=="6" (
    echo [INFO] Dang chuan bi khoi chay Trinh duyet...
    echo [IMPORTANT] Vui long dam bao da xac nhan cai dat Playwright.
    python scripts/run_spotlight_web_upload.py
    pause
    goto menu
)

if "%opt%"=="7" (
    echo [INFO] Tam biet!
    exit
)

echo [WARNING] Lua chon khong hop le!
pause
goto menu
