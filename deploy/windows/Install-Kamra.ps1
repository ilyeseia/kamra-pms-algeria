<#
.SYNOPSIS
    Installs the ZIRI PMS Algeria distribution on Windows 10 via WSL2 + Docker Desktop.

.DESCRIPTION
    Read this before running it.

    Frappe does not run on Windows. There is no Windows build, and the project's
    own installer (deploy/install.sh) is a bash script that calls systemctl and
    apt-get. So this script does not install ZIRI PMS "on Windows" in any real
    sense: it verifies that Windows can host Linux containers, then drives the
    Linux installer inside WSL2 where Docker Desktop actually runs the stack.

    That distinction matters commercially. For a hotel that depends on this to
    take bookings, a Linux VPS is the more robust home and the Windows machine
    is simply a browser pointed at it. Use this script for a demo on a laptop,
    a pilot, or a single-site install the operator accepts responsibility for.
    See docs/algeria/INSTALLATION.md for the comparison.

    WHAT IT DOES NOT DO WITH PASSWORDS
    It never asks for, stores, or passes the admin password. It exports
    SITE_NAME and ADMIN_EMAIL only; install.sh's prompt() skips variables that
    are already set, so the Linux installer prompts for the password by itself
    and reads it straight from the console. The password therefore never enters
    a PowerShell variable, the environment block, a log, or your shell history.

.PARAMETER Mode
    Trial       Demo profile. Site kamra.localhost, sample hotel data seeded,
                demo mode on. Everything is disposable.
    Production  Live profile. No sample data, no demo accounts, demo mode off.

.PARAMETER SiteName
    Frappe site name. Must contain a dot - install.sh rejects anything that does
    not look like a domain. Trial defaults to kamra.localhost, which is also
    what lets the demo reset job recognise the site as a playground
    (reset_demo.py accepts any .localhost suffix).

.PARAMETER Preflight
    Run every environment check and change nothing. Run this first, always.

.EXAMPLE
    .\Install-Kamra.ps1 -Preflight

.EXAMPLE
    .\Install-Kamra.ps1 -Mode Trial

.EXAMPLE
    .\Install-Kamra.ps1 -Mode Production -SiteName pms.hotelalger.dz -AdminEmail gm@hotelalger.dz

.NOTES
    ZIRI PMS Algeria Distribution 1.0.0, on Kamra core 2.6.5.
    Targets Windows PowerShell 5.1, which is what Windows 10 ships - so no
    ternary, null-coalescing, or && / || operators appear in this file.
#>

[CmdletBinding()]
param(
    [ValidateSet('Trial', 'Production')]
    [string] $Mode,

    [string] $SiteName,

    [string] $AdminEmail,

    [ValidateRange(1, 65535)]
    [int] $HttpPort = 8080,

    [string] $RepoUrl = 'https://github.com/ilyeseia/kamra-pms-algeria',

    [string] $Branch = 'feature/algeria-hospitality-platform',

    [string] $WslDistro = '',

    [switch] $Preflight
)

$ErrorActionPreference = 'Stop'

# ── Minimums ────────────────────────────────────────────────────────────────
# From deploy/README.md: 2 vCPU / 4 GB / 40 GB is the floor for the stack
# itself. On Windows, Docker Desktop and the WSL2 VM need memory on top of
# whatever Windows is already using, which is why the RAM advice here is
# higher than the Linux figure.
$MinWindowsBuild = 19041   # Windows 10 2004; WSL2 needs this or later
$HardMinRamGb    = 4       # below this the image build will not finish
$MinRamGb        = 8
$RecommendedRamGb = 16
$MinFreeDiskGb   = 40

$script:Failures = New-Object System.Collections.ArrayList
$script:Warnings = New-Object System.Collections.ArrayList

function Write-Head($text) {
    Write-Host ''
    Write-Host "== $text" -ForegroundColor Cyan
}

function Write-Ok($text) {
    Write-Host "  [ OK ] $text" -ForegroundColor Green
}

function Write-Bad($text, $fix) {
    Write-Host "  [FAIL] $text" -ForegroundColor Red
    if ($fix) { Write-Host "         fix: $fix" -ForegroundColor Yellow }
    [void] $script:Failures.Add($text)
}

function Write-Meh($text) {
    Write-Host "  [WARN] $text" -ForegroundColor Yellow
    [void] $script:Warnings.Add($text)
}

function Write-Info($text) {
    Write-Host "         $text" -ForegroundColor DarkGray
}

# ── Preflight ───────────────────────────────────────────────────────────────

function Test-Windows {
    Write-Head 'Windows'

    if (-not [Environment]::Is64BitOperatingSystem) {
        Write-Bad '32-bit Windows' 'WSL2 requires 64-bit Windows. This machine cannot host the stack.'
        return
    }
    Write-Ok '64-bit Windows'

    $os = Get-CimInstance Win32_OperatingSystem
    $build = [int] ($os.BuildNumber)
    if ($build -lt $MinWindowsBuild) {
        Write-Bad "Windows build $build is older than $MinWindowsBuild" `
                  'Install Windows 10 version 2004 or later (Settings > Update).'
    }
    else {
        Write-Ok "$($os.Caption) build $build"
    }

    # Hardware virtualisation. Reported, never blocking: once Hyper-V claims
    # the CPU it hides the feature from Win32_Processor, so this property reads
    # $false on machines that are demonstrably running WSL2 right now. Treating
    # it as fatal would turn a working install into a BIOS wild goose chase.
    # The check that actually proves virtualisation works is "can we run a
    # command inside a WSL2 distro", which Test-Wsl does below.
    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    if ($cpu.VirtualizationFirmwareEnabled -eq $false) {
        Write-Meh 'Win32_Processor reports virtualisation disabled in firmware'
        Write-Info 'Often a false negative: Hyper-V hides the flag once it owns the CPU.'
        Write-Info 'If the WSL2 checks below pass, virtualisation is working - ignore this.'
        Write-Info 'If they fail, enable Intel VT-x / AMD-V in BIOS or UEFI setup.'
    }
    else {
        Write-Ok 'Hardware virtualisation available'
    }

    $cores = $cpu.NumberOfLogicalProcessors
    if ($cores -lt 2) {
        Write-Bad "$cores logical processor" 'The stack needs at least 2.'
    }
    else {
        Write-Ok "$cores logical processors"
    }
}

function Test-Resources {
    Write-Head 'Resources'

    $os = Get-CimInstance Win32_OperatingSystem
    $ramGb = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
    if ($ramGb -lt $HardMinRamGb) {
        Write-Bad "$ramGb GB RAM" `
                  "Below $HardMinRamGb GB the image build will not finish. This machine cannot host the stack."
    }
    elseif ($ramGb -lt $MinRamGb) {
        # Not fatal: install.sh adds a swap file under 8 GB precisely so the
        # build survives. Slow and worth saying out loud, but not a blocker -
        # and "7.9 GB" is what an 8 GB machine reports once firmware reserves
        # its share, which is no reason to refuse to install.
        Write-Meh "$ramGb GB RAM - under the $MinRamGb GB target, expect a slow build and swapping"
        Write-Info 'install.sh adds a swap file below 8 GB so the build is not OOM-killed.'
        Write-Info "For a production hotel, $RecommendedRamGb GB or a Linux VPS is the right answer."
    }
    elseif ($ramGb -lt $RecommendedRamGb) {
        Write-Meh "$ramGb GB RAM - workable, but the image build will be slow and may swap"
        Write-Info "The Linux installer adds a swap file below 8 GB so the build does not get OOM-killed."
    }
    else {
        Write-Ok "$ramGb GB RAM"
    }

    $sysDrive = $env:SystemDrive
    $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$sysDrive'"
    $freeGb = [math]::Round($disk.FreeSpace / 1GB, 1)
    if ($freeGb -lt $MinFreeDiskGb) {
        Write-Bad "$freeGb GB free on $sysDrive" `
                  "Need at least $MinFreeDiskGb GB. The image is built locally, not pulled, so the build cache is large."
    }
    else {
        Write-Ok "$freeGb GB free on $sysDrive"
    }
}

function Get-WslDistro {
    # `wsl -l -q` emits UTF-16LE; PowerShell 5.1 reads it as mojibake unless
    # the console output encoding is switched first. Restore it afterwards so
    # the rest of the session is unaffected.
    $prev = [Console]::OutputEncoding
    try {
        [Console]::OutputEncoding = [System.Text.Encoding]::Unicode
        $raw = & wsl.exe -l -q 2>$null
    }
    finally {
        [Console]::OutputEncoding = $prev
    }
    if (-not $raw) { return @() }
    $out = New-Object System.Collections.ArrayList
    foreach ($line in $raw) {
        $name = ($line -replace "`0", '').Trim()
        if ($name) { [void] $out.Add($name) }
    }
    return $out
}

function Test-Wsl {
    Write-Head 'WSL2'

    $wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
    if (-not $wsl) {
        Write-Bad 'wsl.exe not found' 'Run in an elevated prompt: wsl --install   then reboot.'
        return
    }
    Write-Ok 'wsl.exe present'

    $distros = Get-WslDistro
    if ($distros.Count -eq 0) {
        Write-Bad 'No WSL distribution installed' `
                  'Run: wsl --install -d Ubuntu   then set a UNIX username and password when it first starts.'
        return
    }
    Write-Ok "distributions: $($distros -join ', ')"

    if (-not $script:Distro) {
        if ($WslDistro) {
            $script:Distro = $WslDistro
        }
        else {
            $preferred = $distros | Where-Object { $_ -like 'Ubuntu*' } | Select-Object -First 1
            if ($preferred) { $script:Distro = $preferred } else { $script:Distro = $distros[0] }
        }
    }

    if ($distros -notcontains $script:Distro) {
        Write-Bad "distribution '$($script:Distro)' is not installed" `
                  "Pick one of: $($distros -join ', ')"
        return
    }
    Write-Ok "using distribution: $($script:Distro)"

    # Version 2 specifically. A distro still on WSL1 cannot run Docker.
    $verbose = & wsl.exe -l -v 2>$null | Out-String
    $clean = $verbose -replace "`0", ''
    $match = [regex]::Match($clean, "(?m)^\s*\*?\s*$([regex]::Escape($script:Distro))\s+\S+\s+(\d)")
    if ($match.Success) {
        if ($match.Groups[1].Value -ne '2') {
            Write-Bad "$($script:Distro) is running on WSL1" `
                      "Run: wsl --set-version $($script:Distro) 2"
        }
        else {
            Write-Ok "$($script:Distro) is on WSL2"
        }
    }
    else {
        Write-Meh "could not read the WSL version for $($script:Distro) - continuing, but confirm with: wsl -l -v"
    }

    $uname = & wsl.exe -d $script:Distro -- uname -s 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Bad "cannot execute inside $($script:Distro)" 'Start it once interactively: wsl -d <distro>'
    }
    else {
        Write-Ok "shell reachable ($($uname))"
    }
}

function Test-Docker {
    Write-Head 'Docker'

    if (-not $script:Distro) {
        Write-Bad 'skipped - no usable WSL distribution' 'Fix the WSL failures above first.'
        return
    }

    # Docker must be reachable from INSIDE the distro, not just on Windows.
    # This is the check that matters: if it fails, install.sh sees no docker on
    # PATH and tries to apt-get install docker.io inside WSL, which is the
    # wrong daemon and a confusing mess to unpick afterwards.
    & wsl.exe -d $script:Distro -- bash -lc 'command -v docker' > $null 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Bad "docker CLI not on PATH inside $($script:Distro)" `
                  "Docker Desktop > Settings > Resources > WSL integration > enable '$($script:Distro)', then Apply & restart."
        return
    }
    Write-Ok 'docker CLI present inside WSL'

    $ver = & wsl.exe -d $script:Distro -- bash -lc 'docker version --format "{{.Server.Version}}" 2>/dev/null' 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $ver) {
        # "No daemon" and "daemon running but not shared with this distro" are
        # different problems with different fixes, and saying the wrong one
        # sends someone restarting Docker Desktop over and over. Ask the
        # Windows side: if IT can see a server, the daemon is fine and only
        # the WSL integration is missing.
        $winVer = & docker.exe version --format "{{.Server.Version}}" 2>$null
        if ($LASTEXITCODE -eq 0 -and $winVer) {
            Write-Bad "Docker Desktop is running ($($winVer.Trim())) but is not shared with $($script:Distro)" `
                      "Docker Desktop > Settings > Resources > WSL integration > turn on '$($script:Distro)' > Apply & restart."
            Write-Info 'The daemon is healthy - only this distro cannot reach it.'
            Write-Info "Confirm after: wsl -d $($script:Distro) -- docker version"
        }
        else {
            Write-Bad 'docker daemon not responding' 'Start Docker Desktop and wait for it to report Running.'
        }
        return
    }
    Write-Ok "docker daemon $($ver.Trim())"

    & wsl.exe -d $script:Distro -- bash -lc 'docker compose version' > $null 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Bad 'docker compose v2 unavailable' 'Update Docker Desktop; the installer uses `docker compose`, not docker-compose.'
    }
    else {
        Write-Ok 'docker compose v2 present'
    }
}

function Test-Port {
    Write-Head "Port $HttpPort"
    $inUse = Get-NetTCPConnection -LocalPort $HttpPort -State Listen -ErrorAction SilentlyContinue
    if ($inUse) {
        $owner = ''
        try {
            $p = Get-Process -Id $inUse[0].OwningProcess -ErrorAction SilentlyContinue
            if ($p) { $owner = " (held by $($p.ProcessName), PID $($p.Id))" }
        } catch { }
        Write-Meh "port $HttpPort is already listening$owner"
        Write-Info "Pass -HttpPort with a free port, or stop that service before installing."
    }
    else {
        Write-Ok "port $HttpPort is free"
    }
}

function Test-Repo {
    Write-Head 'Algeria distribution source'
    Write-Ok "repository: $RepoUrl"
    Write-Ok "branch:     $Branch"
    Write-Info 'install.sh defaults to upstream Kamra on `main`. These override it;'
    Write-Info 'without the override the client gets upstream with no Algeria work.'

    # A private repo cannot be cloned from inside the build container, which
    # has no credentials. Catch it here rather than 30 minutes into a build.
    if (-not $script:Distro) { return }
    $probe = "git ls-remote --heads '$RepoUrl' '$Branch' 2>/dev/null | head -1"
    $head = & wsl.exe -d $script:Distro -- bash -lc $probe 2>$null
    if (-not $head) {
        Write-Bad "branch '$Branch' is not publicly readable at $RepoUrl" `
                  'Make the repository public, or the image build will fail: the Containerfile clones this URL from inside the container with no credentials.'
    }
    else {
        Write-Ok "branch reachable anonymously ($(($head -split '\s+')[0].Substring(0,7)))"
    }
}

# ── Install ─────────────────────────────────────────────────────────────────

function Invoke-Install {
    $script:ProfileName = $Mode

    if (-not $SiteName) {
        if ($Mode -eq 'Trial') {
            $SiteName = 'kamra.localhost'
        }
        else {
            # Prompt rather than throw: this is reached from a Start menu
            # shortcut, where an exception is just a red wall of text.
            Write-Host ''
            $SiteName = Read-Host '  Site domain (e.g. pms.yourhotel.dz)'
            if (-not $SiteName) { throw 'A site domain is required for Production.' }
        }
    }
    if ($SiteName -notmatch '\.') {
        throw "SiteName '$SiteName' has no dot. install.sh rejects anything that does not look like a domain."
    }
    if (-not $AdminEmail) {
        if ($Mode -eq 'Trial') {
            $AdminEmail = 'admin@kamra.localhost'
        }
        else {
            $AdminEmail = Read-Host '  Admin email'
            if (-not $AdminEmail) { throw 'An admin email is required for Production.' }
        }
    }
    if ($AdminEmail -notmatch '@') { throw "AdminEmail '$AdminEmail' is not an email address." }

    Write-Head "Installing - $Mode profile"
    Write-Host "  site        $SiteName"
    Write-Host "  admin       $AdminEmail"
    Write-Host "  port        $HttpPort"
    Write-Host "  source      $RepoUrl @ $Branch"
    Write-Host "  distro      $($script:Distro)"
    Write-Host ''

    if ($Mode -eq 'Production') {
        Write-Host '  PRODUCTION PROFILE' -ForegroundColor Yellow
        Write-Host '  No sample data is seeded and no demo accounts are created.' -ForegroundColor Yellow
        Write-Host '  Never run kamra/scripts/seed_users.py on this site: it creates six' -ForegroundColor Yellow
        Write-Host '  accounts whose passwords are published in the repository and compiled' -ForegroundColor Yellow
        Write-Host '  into the shipped JavaScript bundle.' -ForegroundColor Yellow
        Write-Host ''
    }

    Write-Host '  The Linux installer will now ask for the admin password itself.' -ForegroundColor Cyan
    Write-Host '  It is read straight from this console. This script never sees it.' -ForegroundColor Cyan
    Write-Host '  Minimum 10 characters; there is no default.' -ForegroundColor Cyan
    Write-Host ''
    Write-Host '  First install builds the image locally and takes 20-45 minutes.' -ForegroundColor DarkGray
    Write-Host ''

    $installer = '/tmp/kamra-install.sh'
    $rawBase = ($RepoUrl -replace '^https://github\.com/', 'https://raw.githubusercontent.com/')
    $rawUrl = "$rawBase/$Branch/deploy/install.sh"

    # Fetch, then run. Deliberately two steps, not `curl | bash`: the script is
    # written to disk first so an operator can read what they are about to run
    # as root, and so a truncated download fails before execution.
    $fetch = "set -e; curl -fsSL '$rawUrl' -o '$installer'; test -s '$installer'; echo fetched"
    $got = & wsl.exe -d $script:Distro -u root -- bash -lc $fetch
    if ($LASTEXITCODE -ne 0) {
        throw "Could not download the installer from $rawUrl"
    }
    Write-Ok "installer downloaded to $installer inside $($script:Distro)"
    Write-Info "Review it if you like:  wsl -d $($script:Distro) -- less $installer"
    Write-Host ''

    # SITE_NAME and ADMIN_EMAIL are exported so install.sh's prompt() skips
    # them. ADMIN_PASSWORD is deliberately NOT exported, which is exactly why
    # install.sh prompts for it and this script stays ignorant of it.
    $env_ = @(
        "export KAMRA_GIT_URL='$RepoUrl'",
        "export KAMRA_BRANCH='$Branch'",
        "export SITE_NAME='$SiteName'",
        "export ADMIN_EMAIL='$AdminEmail'",
        "export HTTP_PUBLISH_PORT='$HttpPort'"
    ) -join '; '

    & wsl.exe -d $script:Distro -u root -- bash -lc "$env_; bash '$installer' install"
    if ($LASTEXITCODE -ne 0) {
        throw "install.sh exited with code $LASTEXITCODE. See deploy/TROUBLESHOOTING.md."
    }

    if ($Mode -eq 'Trial') { Invoke-TrialSeed }

    Show-Result
}

function Invoke-TrialSeed {
    Write-Head 'Seeding the demo hotel'
    Write-Info 'Trial profile only. This also sets kamra_demo_mode, which is what'
    Write-Info 'lets the demo reset job recognise a .localhost site as a playground.'

    $cmd = "cd /opt/kamra/frappe_docker && docker compose --env-file /opt/kamra/kamra.env " +
           "-f compose.yaml -f overrides/compose.mariadb.yaml exec -T backend " +
           "bench --site '$SiteName' execute kamra.scripts.seed_demo.execute"
    & wsl.exe -d $script:Distro -u root -- bash -lc $cmd
    if ($LASTEXITCODE -ne 0) {
        Write-Meh 'demo seeding failed - the install itself is fine, the site is just empty'
        Write-Info 'Retry manually, or create a property at /kamra/setup by hand.'
    }
    else {
        Write-Ok 'demo hotel seeded'
    }
}

function Show-Result {
    Write-Head 'Done'
    Write-Host "  Open        http://localhost:$HttpPort/kamra" -ForegroundColor Green
    Write-Host "  User        Administrator  ($AdminEmail)"
    Write-Host "  Password    the one you just typed - there is no default"
    Write-Host ''
    Write-Host "  Stack dir   /opt/kamra  (inside WSL: wsl -d $($script:Distro))"
    Write-Host "  Secrets     /opt/kamra/kamra.env   mode 600, holds the DB password"
    Write-Host "  Update      sudo /opt/kamra/install.sh update"
    Write-Host ''

    if ($Mode -eq 'Production') {
        Write-Host '  Before handover, work through docs/algeria/INSTALLATION.md:' -ForegroundColor Yellow
        Write-Host '    - put TLS in front of it; do not serve a hotel over plain HTTP'
        Write-Host '    - set up and TEST a restore (docs/algeria/BACKUP.md)'
        Write-Host '    - have the accountant confirm the TVA treatment (docs/algeria/TAXES.md)'
        Write-Host '    - confirm no demo accounts exist on the site'
        Write-Host ''
    }

    Write-Host '  Verify the Algeria pack is actually live:' -ForegroundColor Cyan
    Write-Host '    open /kamra/setup and confirm Algeria appears in the country list,'
    Write-Host '    then that the currency shows DZD and the tax label reads TVA.'
    Write-Host ''
    Write-Host '  NOT YET PROVEN on any database - read this before going live:' -ForegroundColor Yellow
    Write-Host '    Migrations v36 and v37 have never run against a real database'
    Write-Host '    before this install. If it completed, they just ran for the'
    Write-Host '    first time. Check the site loads and a reservation saves.'
    Write-Host ''
}

# ── Main ────────────────────────────────────────────────────────────────────

Write-Host ''
Write-Host 'ZIRI PMS - Algeria Distribution 1.0.0' -ForegroundColor White
Write-Host 'on Kamra core 2.6.5 - AGPL-3.0 - see docs/algeria/LICENSING.md' -ForegroundColor DarkGray

$script:Distro = ''

Test-Windows
Test-Resources
Test-Wsl
Test-Docker
Test-Port
Test-Repo

Write-Head 'Preflight summary'
if ($script:Failures.Count -gt 0) {
    Write-Host "  $($script:Failures.Count) blocking problem(s):" -ForegroundColor Red
    foreach ($f in $script:Failures) { Write-Host "    - $f" -ForegroundColor Red }
    Write-Host ''
    Write-Host '  Nothing was changed. Fix the above and run again.' -ForegroundColor Yellow
    exit 1
}
if ($script:Warnings.Count -gt 0) {
    Write-Host "  $($script:Warnings.Count) warning(s) - not blocking:" -ForegroundColor Yellow
    foreach ($w in $script:Warnings) { Write-Host "    - $w" -ForegroundColor Yellow }
}
Write-Host '  Environment can host the stack.' -ForegroundColor Green

if ($Preflight) {
    Write-Host ''
    Write-Host '  -Preflight was set: stopping here without changing anything.' -ForegroundColor Cyan
    Write-Host '  When ready:  .\Install-Kamra.ps1 -Mode Trial' -ForegroundColor Cyan
    Write-Host ''
    exit 0
}

if (-not $Mode) {
    Write-Host ''
    Write-Host '  No -Mode given, so nothing was installed.' -ForegroundColor Cyan
    Write-Host '    .\Install-Kamra.ps1 -Mode Trial'
    Write-Host '    .\Install-Kamra.ps1 -Mode Production -SiteName pms.hotel.dz -AdminEmail gm@hotel.dz'
    Write-Host ''
    exit 0
}

Invoke-Install
