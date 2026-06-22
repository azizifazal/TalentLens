# ==============================================================================
#  TalentLens AI - Windows PowerShell Deployment Script
#  Deploys all 3 CDK stacks, then builds and syncs the frontend to S3.
#
#  Usage (run from project root in PowerShell):
#    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#    .\deploy.ps1
#
#  Optional - set a known production frontend URL before running:
#    $env:FRONTEND_URL = "https://your-cf-domain.cloudfront.net"
#    .\deploy.ps1
#
#  Prerequisites:
#    - AWS CLI v2  (https://aws.amazon.com/cli/)
#    - AWS CDK CLI v2  (npm install -g aws-cdk@2)
#    - Docker Desktop (running)
#    - Node.js 20+  (https://nodejs.org/)
#    - Python 3.12+  (https://python.org/)
#    - Bedrock model access enabled in us-east-1 for:
#        amazon.nova-pro-v1:0
#        amazon.titan-embed-text-v2:0
# ==============================================================================

#Requires -Version 5.1
$ErrorActionPreference = "Stop"

# -- Configuration -------------------------------------------------------------
$AWS_ACCOUNT_ID = "022784798053"
$AWS_REGION     = "us-east-1"
$FRONTEND_URL   = if ($env:FRONTEND_URL) { $env:FRONTEND_URL } else { "http://localhost:5173" }
$TMP            = "C:\Windows\Temp"

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Definition

# -- Colour helpers ------------------------------------------------------------
function Write-Info { param($msg) Write-Host "[INFO]  $msg" -ForegroundColor Cyan   }
function Write-OK   { param($msg) Write-Host "[OK]    $msg" -ForegroundColor Green  }
function Write-Warn { param($msg) Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Write-Err  {
    param($msg)
    Write-Host "[ERROR] $msg" -ForegroundColor Red
    exit 1
}

function Assert-Command {
    param([string]$Name, [string]$InstallHint)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-Err "$Name not found. $InstallHint"
    }
}

function Invoke-Cmd {
    param([string]$Description, [scriptblock]$ScriptBlock)
    Write-Info $Description
    & $ScriptBlock
    if ($LASTEXITCODE -ne 0) {
        Write-Err "$Description failed (exit code $LASTEXITCODE). Check output above."
    }
}

# Helper: write JSON to a temp file and return the file:// URI for AWS CLI
function Write-JsonTemp {
    param([string]$FileName, [string]$JsonContent)
    $path = "$TMP\$FileName"
    [System.IO.File]::WriteAllText($path, $JsonContent, (New-Object System.Text.UTF8Encoding $false))
    return "file://C:/Windows/Temp/$FileName"
}

# ==============================================================================
# 1. Pre-flight checks
# ==============================================================================
Write-Info "Running pre-flight checks..."

Assert-Command "aws"    "Install AWS CLI v2 from https://aws.amazon.com/cli/"
Assert-Command "cdk"    "Run: npm install -g aws-cdk@2"
Assert-Command "docker" "Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
Assert-Command "node"   "Install Node.js 20+ from https://nodejs.org/"
Assert-Command "npm"    "npm should come with Node.js - reinstall Node.js."
Assert-Command "python" "Install Python 3.12+ from https://python.org/ and check 'Add to PATH'."

docker info 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Err "Docker daemon is not running. Start Docker Desktop and retry."
}

$callerIdentity = aws sts get-caller-identity --query Account --output text 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Err "AWS credentials not configured. Run 'aws configure' or set up SSO, then retry."
}
$CALLER_ACCOUNT = $callerIdentity.Trim()

if ($CALLER_ACCOUNT -ne $AWS_ACCOUNT_ID) {
    Write-Warn "Active AWS account ($CALLER_ACCOUNT) differs from target ($AWS_ACCOUNT_ID)."
    Write-Warn "Proceeding with active account: $CALLER_ACCOUNT"
    $AWS_ACCOUNT_ID = $CALLER_ACCOUNT
}

Write-OK "Pre-flight checks passed (account: $AWS_ACCOUNT_ID, region: $AWS_REGION)"

# ==============================================================================
# 2. CDK Bootstrap
# ==============================================================================
$env:CDK_DEFAULT_ACCOUNT = $AWS_ACCOUNT_ID
$env:CDK_DEFAULT_REGION  = $AWS_REGION

$INFRA_DIR = Join-Path $SCRIPT_DIR "infra"
Set-Location $INFRA_DIR

$VENV_DIR = Join-Path $INFRA_DIR ".venv"
if (-not (Test-Path $VENV_DIR)) {
    Write-Info "Creating Python virtual environment for infra..."
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Err "Failed to create Python virtual environment." }
}

$ACTIVATE = Join-Path $VENV_DIR "Scripts\Activate.ps1"
if (-not (Test-Path $ACTIVATE)) { Write-Err "venv activation script not found at: $ACTIVATE" }
. $ACTIVATE

Invoke-Cmd "Installing CDK Python dependencies" {
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet -r requirements.txt
}

Write-Info "Bootstrapping CDK toolkit (idempotent)..."
cdk bootstrap "aws://$AWS_ACCOUNT_ID/$AWS_REGION"
if ($LASTEXITCODE -ne 0) { Write-Err "CDK bootstrap failed." }
Write-OK "CDK bootstrap complete."

# ==============================================================================
# 3. Deploy all CDK stacks
# ==============================================================================
Write-Info "Deploying all CDK stacks (Auth -> Storage -> Compute)..."
Write-Info "Note: First deploy takes 10-20 minutes."

cdk deploy --all `
    --require-approval never `
    -c "allowed_origins=$FRONTEND_URL" `
    -c "environment=poc"

if ($LASTEXITCODE -ne 0) { Write-Err "CDK deploy failed. Check CloudFormation console." }
Write-OK "All CDK stacks deployed."

# ==============================================================================
# 4. Capture stack outputs
# ==============================================================================
Write-Info "Fetching stack outputs..."

$USER_POOL_ID = (aws cloudformation describe-stacks `
    --stack-name TalentLensAuthStack --region $AWS_REGION `
    --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" `
    --output text).Trim()

$USER_POOL_CLIENT_ID = (aws cloudformation describe-stacks `
    --stack-name TalentLensAuthStack --region $AWS_REGION `
    --query "Stacks[0].Outputs[?OutputKey=='UserPoolClientId'].OutputValue" `
    --output text).Trim()

$API_URL = (aws cloudformation describe-stacks `
    --stack-name TalentLensComputeStack --region $AWS_REGION `
    --query "Stacks[0].Outputs[?OutputKey=='ApiFunctionUrl'].OutputValue" `
    --output text).Trim()

if ([string]::IsNullOrWhiteSpace($USER_POOL_ID))        { Write-Err "Missing UserPoolId output." }
if ([string]::IsNullOrWhiteSpace($USER_POOL_CLIENT_ID)) { Write-Err "Missing UserPoolClientId output." }
if ([string]::IsNullOrWhiteSpace($API_URL))             { Write-Err "Missing ApiFunctionUrl output." }

Write-OK "Stack outputs captured:"
Write-Host "  UserPoolId:       $USER_POOL_ID"
Write-Host "  UserPoolClientId: $USER_POOL_CLIENT_ID"
Write-Host "  API URL:          $API_URL"

# ==============================================================================
# 5. Build the frontend
# ==============================================================================
$FRONTEND_DIR = Join-Path $SCRIPT_DIR "frontend"
Set-Location $FRONTEND_DIR

Write-Info "Installing frontend npm dependencies..."
npm install --silent
if ($LASTEXITCODE -ne 0) { Write-Err "npm install failed." }

Write-Info "Writing .env.production..."
$envContent = "VITE_API_BASE_URL=$API_URL`nVITE_COGNITO_USER_POOL_ID=$USER_POOL_ID`nVITE_COGNITO_CLIENT_ID=$USER_POOL_CLIENT_ID`n"
[System.IO.File]::WriteAllText((Join-Path $FRONTEND_DIR ".env.production"), $envContent, [System.Text.Encoding]::UTF8)

Write-Info "Building frontend..."
npm run build
if ($LASTEXITCODE -ne 0) { Write-Err "Frontend build failed." }
Write-OK "Frontend build complete."

# ==============================================================================
# 6. S3 (private) + CloudFront with OAC
# ==============================================================================
$FRONTEND_BUCKET = "talentlens-frontend-$AWS_ACCOUNT_ID"

# 6a. Ensure bucket exists
Write-Info "Ensuring S3 bucket exists: $FRONTEND_BUCKET"
$savedPref = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
aws s3api head-bucket --bucket $FRONTEND_BUCKET 2>&1 | Out-Null
$headExit = $LASTEXITCODE
$ErrorActionPreference = $savedPref

if ($headExit -eq 0) {
    Write-Info "Bucket already exists, skipping creation."
} else {
    $savedPref = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    $br = aws s3api create-bucket --bucket $FRONTEND_BUCKET --region $AWS_REGION 2>&1
    $bExit = $LASTEXITCODE
    $ErrorActionPreference = $savedPref
    if ($bExit -ne 0) { Write-Err "Failed to create bucket: $br" }
    Write-OK "Bucket created."
}

# Block all public access
aws s3api put-public-access-block --bucket $FRONTEND_BUCKET `
    --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
if ($LASTEXITCODE -ne 0) { Write-Err "Failed to block public access on bucket." }

# 6b. Create or reuse CloudFront OAC
Write-Info "Setting up CloudFront Origin Access Control..."
$oacName = "talentlens-oac"

$savedPref = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
$existingOacId = (aws cloudfront list-origin-access-controls `
    --query "OriginAccessControlList.Items[?Name=='$oacName'].Id" `
    --output text 2>&1).Trim()
$ErrorActionPreference = $savedPref

if ([string]::IsNullOrWhiteSpace($existingOacId) -or $existingOacId -eq "None") {
    Write-Info "Creating Origin Access Control..."
    $oacJson = '{"Name":"talentlens-oac","Description":"OAC for TalentLens","SigningProtocol":"sigv4","SigningBehavior":"always","OriginAccessControlOriginType":"s3"}'
    $oacFile = Write-JsonTemp "talentlens-oac.json" $oacJson
    $OAC_ID = (aws cloudfront create-origin-access-control `
        --origin-access-control-config $oacFile `
        --query "OriginAccessControl.Id" --output text).Trim()
    if ($LASTEXITCODE -ne 0) { Write-Err "Failed to create CloudFront OAC." }
    Write-OK "OAC created: $OAC_ID"
} else {
    $OAC_ID = $existingOacId
    Write-Info "Reusing OAC: $OAC_ID"
}

# 6c. Create or reuse CloudFront distribution
Write-Info "Setting up CloudFront distribution..."
$S3_DOMAIN = "$FRONTEND_BUCKET.s3.$AWS_REGION.amazonaws.com"

$savedPref = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
$existingDistJson = aws cloudfront list-distributions `
    --query "DistributionList.Items[?Origins.Items[0].DomainName=='$S3_DOMAIN'].{Id:Id,Domain:DomainName}" `
    --output json 2>&1
$ErrorActionPreference = $savedPref
$existingDists = $existingDistJson | ConvertFrom-Json -ErrorAction SilentlyContinue

if ($existingDists -and $existingDists.Count -gt 0) {
    $CF_DIST_ID     = $existingDists[0].Id
    $CF_DOMAIN_NAME = $existingDists[0].Domain
    Write-Info "Reusing distribution: $CF_DIST_ID"
} else {
    Write-Info "Creating CloudFront distribution (~5 min)..."
    $callerRef = "talentlens-$(Get-Date -Format 'yyyyMMddHHmmss')"
    $distJson = @"
{"CallerReference":"$callerRef","Comment":"TalentLens AI","DefaultRootObject":"index.html","Origins":{"Quantity":1,"Items":[{"Id":"S3Origin","DomainName":"$S3_DOMAIN","S3OriginConfig":{"OriginAccessIdentity":""},"OriginAccessControlId":"$OAC_ID"}]},"DefaultCacheBehavior":{"TargetOriginId":"S3Origin","ViewerProtocolPolicy":"redirect-to-https","CachePolicyId":"658327ea-f89d-4fab-a63d-7e88639e58f6","AllowedMethods":{"Quantity":2,"Items":["GET","HEAD"]},"Compress":true},"CustomErrorResponses":{"Quantity":1,"Items":[{"ErrorCode":403,"ResponseCode":"200","ResponsePagePath":"/index.html","ErrorCachingMinTTL":0}]},"Enabled":true,"HttpVersion":"http2","PriceClass":"PriceClass_100"}
"@
    $distFile = Write-JsonTemp "talentlens-dist.json" $distJson
    $newDistRaw = aws cloudfront create-distribution `
        --distribution-config $distFile `
        --query "Distribution.{Id:Id,Domain:DomainName}" --output json 2>&1
    if ($LASTEXITCODE -ne 0) { Write-Err "Failed to create CloudFront distribution: $newDistRaw" }
    $newDist        = $newDistRaw | ConvertFrom-Json
    $CF_DIST_ID     = $newDist.Id
    $CF_DOMAIN_NAME = $newDist.Domain
    Write-OK "Distribution created: $CF_DIST_ID"
    Write-Warn "CloudFront takes ~5 min to propagate. URL will be active shortly."
}

# 6d. S3 bucket policy for CloudFront OAC
Write-Info "Attaching S3 bucket policy for CloudFront..."
$bktPolicy = @"
{"Version":"2012-10-17","Statement":[{"Sid":"AllowCloudFrontOAC","Effect":"Allow","Principal":{"Service":"cloudfront.amazonaws.com"},"Action":"s3:GetObject","Resource":"arn:aws:s3:::$FRONTEND_BUCKET/*","Condition":{"StringEquals":{"AWS:SourceArn":"arn:aws:cloudfront::$AWS_ACCOUNT_ID:distribution/$CF_DIST_ID"}}}]}
"@
$bktFile = Write-JsonTemp "talentlens-bkt-policy.json" $bktPolicy
aws s3api put-bucket-policy --bucket $FRONTEND_BUCKET --policy $bktFile
if ($LASTEXITCODE -ne 0) { Write-Err "Failed to apply S3 bucket policy." }
Write-OK "Bucket policy applied."

# 6e. Sync frontend to S3
Write-Info "Syncing frontend to S3..."
$DIST_DIR = Join-Path $FRONTEND_DIR "dist"
aws s3 sync $DIST_DIR "s3://$FRONTEND_BUCKET" --delete --region $AWS_REGION
if ($LASTEXITCODE -ne 0) { Write-Err "S3 sync failed." }
Write-OK "Frontend synced to S3."

# 6f. Invalidate CloudFront cache
Write-Info "Invalidating CloudFront cache..."
$savedPref = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
aws cloudfront create-invalidation --distribution-id $CF_DIST_ID --paths "/*" | Out-Null
$ErrorActionPreference = $savedPref
Write-OK "Cache invalidated."

$FRONTEND_WEBSITE_URL = "https://$CF_DOMAIN_NAME"
Write-OK "Frontend live at: $FRONTEND_WEBSITE_URL"

# ==============================================================================
# 7. Update Lambda CORS
# ==============================================================================
if ($FRONTEND_URL -ne $FRONTEND_WEBSITE_URL) {
    Write-Info "Updating Lambda CORS with CloudFront URL..."
    Set-Location $INFRA_DIR
    cdk deploy TalentLensComputeStack `
        --require-approval never `
        -c "allowed_origins=$FRONTEND_WEBSITE_URL" `
        -c "environment=poc"
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "CORS update failed. Re-run: `$env:FRONTEND_URL='$FRONTEND_WEBSITE_URL'; .\deploy.ps1"
    } else {
        Write-OK "Lambda CORS updated to: $FRONTEND_WEBSITE_URL"
    }
}

# ==============================================================================
# 8. Summary
# ==============================================================================
Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "        TalentLens AI - Deployment Complete                     " -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend URL:     " -NoNewline; Write-Host $FRONTEND_WEBSITE_URL  -ForegroundColor Cyan
Write-Host "  API URL:          " -NoNewline; Write-Host $API_URL               -ForegroundColor Cyan
Write-Host "  User Pool ID:     " -NoNewline; Write-Host $USER_POOL_ID          -ForegroundColor Cyan
Write-Host "  User Pool Client: " -NoNewline; Write-Host $USER_POOL_CLIENT_ID   -ForegroundColor Cyan
Write-Host "  CloudFront ID:    " -NoNewline; Write-Host $CF_DIST_ID            -ForegroundColor Cyan
Write-Host "  AWS Account:      " -NoNewline; Write-Host $AWS_ACCOUNT_ID        -ForegroundColor Cyan
Write-Host "  Region:           " -NoNewline; Write-Host $AWS_REGION            -ForegroundColor Cyan
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor Yellow
Write-Host "  1. Open the Frontend URL above (HTTPS)"
Write-Host "  2. Sign up via Cognito"
Write-Host "  3. CloudFront takes ~5 min to fully propagate on first deploy"
Write-Host ""
