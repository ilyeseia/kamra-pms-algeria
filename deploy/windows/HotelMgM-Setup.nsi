; Hotel MgM - Windows setup
;
; Builds setup.exe with NSIS:
;     "C:\Program Files (x86)\NSIS\makensis.exe" HotelMgM-Setup.nsi
;
; WHAT THIS INSTALLER HONESTLY IS
; Frappe does not run on Windows. This package therefore does NOT install the
; PMS itself onto Windows - nothing could. It installs the installer: the
; preflight checker, the guided install launcher, and the documentation in
; three languages. The PMS itself is built and run by Docker Desktop inside
; WSL2, which the launcher drives.
;
; The installer says so on its own welcome page rather than letting an
; operator discover it after double-clicking. An installer that misrepresents
; what it does is how a hotel ends up with a half-installed system.

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"

;--------------------------------
; Product

!define PRODUCT      "Hotel MgM"
!define VERSION      "1.0.0"
!define CORE         "Kamra core 2.6.5"
!define PUBLISHER    "Hotel MgM"
!define REGKEY       "Software\Microsoft\Windows\CurrentVersion\Uninstall\HotelMgM"

Name                 "${PRODUCT} ${VERSION}"
OutFile              "HotelMgM-Setup-${VERSION}.exe"
InstallDir           "$PROGRAMFILES64\${PRODUCT}"
InstallDirRegKey     HKLM "Software\HotelMgM" "InstallDir"
RequestExecutionLevel admin
Unicode              true
SetCompressor /SOLID lzma

VIProductVersion     "1.0.0.0"
VIAddVersionKey      "ProductName"     "${PRODUCT}"
VIAddVersionKey      "ProductVersion"  "${VERSION}"
VIAddVersionKey      "FileVersion"     "1.0.0.0"
VIAddVersionKey      "CompanyName"     "${PUBLISHER}"
VIAddVersionKey      "FileDescription" "${PRODUCT} installer and documentation"
VIAddVersionKey      "LegalCopyright"  "AGPL-3.0. Built on Kamra PMS (HeyKoala and contributors)."

;--------------------------------
; Pages

!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "${PRODUCT} ${VERSION}"
!define MUI_WELCOMEPAGE_TEXT  "This package installs the ${PRODUCT} installer and its documentation.$\r$\n$\r$\nRead this before continuing:$\r$\n$\r$\nThe hotel system itself runs in Docker containers under WSL2 - it is not a Windows program, and no Windows program could run it. What gets installed here is the tool that checks this PC, then builds and starts the system inside WSL2, plus the installation and user guides in Arabic, French and English.$\r$\n$\r$\nYou will need: Windows 10 build 19041 or later, WSL2, Docker Desktop with WSL integration enabled, 8 GB RAM and 40 GB free disk. The first install takes 20-45 minutes because the system is built on this machine rather than downloaded.$\r$\n$\r$\nFor a hotel taking live bookings, a Linux server is the more reliable home and this PC would simply be a browser. The guides explain both.$\r$\n$\r$\nLicence: AGPL-3.0. Built on Kamra PMS by HeyKoala and contributors."
!insertmacro MUI_PAGE_WELCOME

!insertmacro MUI_PAGE_LICENSE "..\..\license.txt"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

!define MUI_FINISHPAGE_TITLE "${PRODUCT} is ready to install the system"
!define MUI_FINISHPAGE_TEXT  "Nothing is running yet. The next step is to check this PC.$\r$\n$\r$\nOpen the Start menu, find ${PRODUCT}, and run '1 - Check this PC'. It changes nothing and tells you exactly what is missing, if anything.$\r$\n$\r$\nThen run '2 - Install trial' for a demo with sample data, or '3 - Install production' for a live hotel.$\r$\n$\r$\nRead the guide for your language first - it is in the Start menu under Guides."
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Check this PC now (changes nothing)"
!define MUI_FINISHPAGE_RUN_FUNCTION RunPreflight
!define MUI_FINISHPAGE_SHOWREADME "$INSTDIR\guides\INSTALL-en.md"
!define MUI_FINISHPAGE_SHOWREADME_TEXT "Open the English installation guide"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "French"
!insertmacro MUI_LANGUAGE "Arabic"

;--------------------------------

Function RunPreflight
  Exec '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -NoExit -File "$INSTDIR\Install-Kamra.ps1" -Preflight'
FunctionEnd

Function .onInit
  ; WSL2 requires 64-bit Windows; there is no point installing on 32-bit.
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "${PRODUCT} needs 64-bit Windows. WSL2, which runs the system, is not available on 32-bit Windows."
    Abort
  ${EndIf}

  ; Windows 10 2004 / build 19041 is the floor for WSL2. Warn rather than
  ; block: the operator may be installing the documentation on one machine and
  ; running the system on another.
  ClearErrors
  ReadRegStr $0 HKLM "SOFTWARE\Microsoft\Windows NT\CurrentVersion" "CurrentBuildNumber"
  ${If} ${Errors}
    ; unreadable - say nothing rather than guess
  ${ElseIf} $0 < 19041
    MessageBox MB_ICONEXCLAMATION|MB_OKCANCEL "This is Windows build $0. WSL2 needs build 19041 (version 2004) or later, so the system will not run on this PC until Windows is updated.$\r$\n$\r$\nYou can still install the documentation and the installer. Continue?" IDOK +2
    Abort
  ${EndIf}
FunctionEnd

;--------------------------------
; Install

Section "Installer and documentation" SecMain
  SectionIn RO
  SetOutPath "$INSTDIR"

  File "Install-Kamra.ps1"
  File "README.md"
  File "..\..\license.txt"

  SetOutPath "$INSTDIR\guides"
  File "..\..\docs\algeria\guides\INSTALL-en.md"
  File "..\..\docs\algeria\guides\INSTALL-fr.md"
  File "..\..\docs\algeria\guides\INSTALL-ar.md"
  File "..\..\docs\algeria\guides\USER-en.md"
  File "..\..\docs\algeria\guides\USER-fr.md"
  File "..\..\docs\algeria\guides\USER-ar.md"

  ; The vendor-facing runbooks. Shipped because the person installing this is
  ; often the person who has to restore a backup at 2am.
  SetOutPath "$INSTDIR\reference"
  File "..\..\docs\algeria\INSTALLATION.md"
  File "..\..\docs\algeria\BACKUP.md"
  File "..\..\docs\algeria\LICENSING.md"
  File "..\..\docs\algeria\TAXES.md"
  File "..\..\docs\algeria\VERSIONING.md"
  File "..\..\docs\algeria\IMPLEMENTATION_STATUS.md"

  SetOutPath "$INSTDIR"
  WriteRegStr HKLM "Software\HotelMgM" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "Software\HotelMgM" "Version"    "${VERSION}"
  WriteRegStr HKLM "Software\HotelMgM" "Core"       "${CORE}"

  WriteRegStr   HKLM "${REGKEY}" "DisplayName"     "${PRODUCT} ${VERSION}"
  WriteRegStr   HKLM "${REGKEY}" "DisplayVersion"  "${VERSION}"
  WriteRegStr   HKLM "${REGKEY}" "Publisher"       "${PUBLISHER}"
  WriteRegStr   HKLM "${REGKEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr   HKLM "${REGKEY}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegDWORD HKLM "${REGKEY}" "NoModify" 1
  WriteRegDWORD HKLM "${REGKEY}" "NoRepair" 1

  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Start menu shortcuts" SecShortcuts
  CreateDirectory "$SMPROGRAMS\${PRODUCT}"

  ; Numbered, because the order matters and an operator should not have to
  ; guess it. Preflight first - it is the only one that changes nothing.
  CreateShortcut "$SMPROGRAMS\${PRODUCT}\1 - Check this PC.lnk" \
    "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" \
    '-NoProfile -ExecutionPolicy Bypass -NoExit -File "$INSTDIR\Install-Kamra.ps1" -Preflight'

  CreateShortcut "$SMPROGRAMS\${PRODUCT}\2 - Install trial.lnk" \
    "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" \
    '-NoProfile -ExecutionPolicy Bypass -NoExit -File "$INSTDIR\Install-Kamra.ps1" -Mode Trial'

  ; Production asks for the site domain and the admin email itself, so this
  ; shortcut is the same shape as the others - and needs no escaped quotes
  ; inside an NSIS string, which NSIS does not support anyway.
  CreateShortcut "$SMPROGRAMS\${PRODUCT}\3 - Install production.lnk" \
    "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" \
    '-NoProfile -ExecutionPolicy Bypass -NoExit -File "$INSTDIR\Install-Kamra.ps1" -Mode Production'

  CreateDirectory "$SMPROGRAMS\${PRODUCT}\Guides"
  CreateShortcut "$SMPROGRAMS\${PRODUCT}\Guides\Installation (English).lnk" "$INSTDIR\guides\INSTALL-en.md"
  CreateShortcut "$SMPROGRAMS\${PRODUCT}\Guides\Installation (Francais).lnk" "$INSTDIR\guides\INSTALL-fr.md"
  CreateShortcut "$SMPROGRAMS\${PRODUCT}\Guides\Installation (Arabic).lnk" "$INSTDIR\guides\INSTALL-ar.md"
  CreateShortcut "$SMPROGRAMS\${PRODUCT}\Guides\User guide (English).lnk" "$INSTDIR\guides\USER-en.md"
  CreateShortcut "$SMPROGRAMS\${PRODUCT}\Guides\User guide (Francais).lnk" "$INSTDIR\guides\USER-fr.md"
  CreateShortcut "$SMPROGRAMS\${PRODUCT}\Guides\User guide (Arabic).lnk" "$INSTDIR\guides\USER-ar.md"

  CreateShortcut "$SMPROGRAMS\${PRODUCT}\Open ${PRODUCT} (after install).lnk" \
    "http://localhost:8080/kamra"

  CreateShortcut "$SMPROGRAMS\${PRODUCT}\Uninstall.lnk" "$INSTDIR\uninstall.exe"
SectionEnd

LangString DESC_SecMain      ${LANG_ENGLISH} "The installer, the launcher and the guides. Required."
LangString DESC_SecShortcuts ${LANG_ENGLISH} "Start menu entries for the preflight check, the two install modes and the guides."

LangString DESC_SecMain      ${LANG_FRENCH}  "L'installateur, le lanceur et les guides. Obligatoire."
LangString DESC_SecShortcuts ${LANG_FRENCH}  "Raccourcis du menu Demarrer : verification du PC, les deux modes d'installation et les guides."

LangString DESC_SecMain      ${LANG_ARABIC}  "المُثبّت والمُشغّل والأدلّة. إلزامي."
LangString DESC_SecShortcuts ${LANG_ARABIC}  "اختصارات قائمة البدء: فحص الجهاز، ووضعا التركيب، والأدلّة."

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecMain}      $(DESC_SecMain)
  !insertmacro MUI_DESCRIPTION_TEXT ${SecShortcuts} $(DESC_SecShortcuts)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

;--------------------------------
; Uninstall

Section "Uninstall"
  ; This removes the launcher and the documentation. It deliberately does NOT
  ; touch the system inside WSL2 - /opt/kamra, the Docker volumes and the
  ; database all survive. Deleting a hotel's reservations because somebody
  ; uninstalled a shortcut package would be indefensible, so removing the
  ; actual data is a separate, deliberate act documented in
  ; docs/algeria/INSTALLATION.md.
  MessageBox MB_ICONINFORMATION|MB_OK "This removes the ${PRODUCT} installer and guides from Windows.$\r$\n$\r$\nThe hotel system inside WSL2 is NOT removed: its database, files and Docker volumes are left untouched. Removing those is a separate step, described in the installation guide under 'Uninstall'."

  Delete "$INSTDIR\Install-Kamra.ps1"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\license.txt"
  Delete "$INSTDIR\uninstall.exe"
  RMDir /r "$INSTDIR\guides"
  RMDir /r "$INSTDIR\reference"
  RMDir "$INSTDIR"

  RMDir /r "$SMPROGRAMS\${PRODUCT}"

  DeleteRegKey HKLM "${REGKEY}"
  DeleteRegKey HKLM "Software\HotelMgM"
SectionEnd
