; QUANT PRO - NSIS installer script
; Usage: makensis /DAPP_DIR="..." quantpro.nsi

!define APP_NAME "QUANT PRO"
!define APP_VERSION "2.7.0"
!define APP_PUBLISHER "QUANT PRO"
!define APP_EXE "QUANT PRO.exe"
!define APP_INSTALL_DIR "$LOCALAPPDATA\Programs\QUANT PRO"

!ifndef APP_DIR
  !define APP_DIR "C:\Users\86157\quantpro-releases\win-unpacked"
!endif

RequestExecutionLevel user
Unicode true
SetCompressor /SOLID lzma

Name "${APP_NAME}"
Caption "${APP_NAME} ${APP_VERSION}"
OutFile "C:\Users\86157\quantpro-releases\QUANT_PRO_Setup_${APP_VERSION}.exe"
InstallDir "${APP_INSTALL_DIR}"
; NOTE: do NOT use InstallDirRegKey - it would read stale registry path and install to wrong dir

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "Main Program" SecMain
  SectionIn RO
  SetOutPath "$INSTDIR"
  File /r "${APP_DIR}\*.*"
  WriteRegStr HKCU "Software\${APP_NAME}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayIcon" "$INSTDIR\${APP_EXE}"
  CreateShortCut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\Uninstall ${APP_NAME}.lnk" "$INSTDIR\Uninstall.exe"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
  ExecWait 'taskkill /F /IM "QUANT PRO.exe" /T'
  ExecWait 'taskkill /F /IM "QUANT_PRO_backend.exe" /T'
  RMDir /r "$INSTDIR"
  Delete "$DESKTOP\${APP_NAME}.lnk"
  RMDir /r "$SMPROGRAMS\${APP_NAME}"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
  DeleteRegKey HKCU "Software\${APP_NAME}"
  SetAutoClose true
SectionEnd
