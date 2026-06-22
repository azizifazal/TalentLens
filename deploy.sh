#!/usr/bin/env bash
# =============================================================================
#  TalentLens AI — One-shot deployment script
#  Deploys all 3 CDK stacks, then builds and syncs the frontend to S3.
#
#  Usage:
#    chmod +x deploy.sh
#    ./deploy.sh
#
#  Prerequisites:
#    - AWS CLI v2 configured (aws configure or SSO)
#    - Docker running
#    - Node.js 20+ and npm
#    - Python 3.12+
#    - AWS CDK CLI v2  (npm install -g aws-cdk@2)
#    - Bedrock model access enabled for:
#        amazon.nova-pro-v1:0
#        amazon.titan-embed-text-v2:0
# =============================================================================

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
AWS_ACCOUNT_ID="022784798053"
AWS_REGION="us-east-1"
# Update this after you know your frontend URL (CloudFront or S3 website URL).
# Re-run the script with the real URL to update CORS on the Lambda.
FRONTEND_URL="${FRONTEND_URL:-http://localhost:5173}"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ── Resolve script directory (works when called from any cwd) ─────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# =============================================================================
# 1. Pre-flight checks
# =============================================================================
info "Running pre-flight checks..."

command -v aws      >/dev/null 2>&1 || error "AWS CLI not found. Install from https://aws.amazon.com/cli/"
command -v cdk      >/dev/null 2>&1 || error "CDK CLI not found. Run: npm install -g aws-cdk@2"
command -v docker   >/dev/null 2>&1 || error "Docker not found. Install Docker Desktop."
command -v node     >/dev/null 2>&1 || error "Node.js not found. Install Node.js 20+."
command -v npm      >/dev/null 2>&1 || error "npm not found."
command -v python3  >/dev/null 2>&1 || error "Python 3 not found."

docker info >/dev/null 2>&1 || error "Docker daemon is not running. Start Docker Desktop and retry."

CALLER_ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) \
  || error "AWS credentials not configured. Run 'aws configure' or set up SSO."

if [[ "$CALLER_ACCOUNT" != "$AWS_ACCOUNT_ID" ]]; then
  warn "Active AWS account ($CALLER_ACCOUNT) differs from target ($AWS_ACCOUNT_ID)."
  warn "Proceeding with active account: $CALLER_ACCOUNT"
  AWS_ACCOUNT_ID="$CALLER_ACCOUNT"
fi

success "Pre-flight checks passed (account: $AWS_ACCOUNT_ID, region: $AWS_REGION)"

# =============================================================================
# 2. CDK Bootstrap (idempotent — safe to re-run)
# =============================================================================
info "Bootstrapping CDK toolkit (idempotent)..."
export CDK_DEFAULT_ACCOUNT="$AWS_ACCOUNT_ID"
export CDK_DEFAULT_REGION="$AWS_REGION"

cd "$SCRIPT_DIR/infra"

# Set up Python venv for CDK infra
if [[ ! -d ".venv" ]]; then
  info "Creating Python virtual environment for infra..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

cdk bootstrap "aws://${AWS_ACCOUNT_ID}/${AWS_REGION}" \
  || error "CDK bootstrap failed."
success "CDK bootstrap complete."

# =============================================================================
# 3. Deploy all CDK stacks
# =============================================================================
info "Deploying all CDK stacks (Auth → Storage → Compute)..."
info "Note: First deploy takes 10–20 min (Docker builds + OpenSearch provisioning)"

cdk deploy --all \
  --require-approval never \
  -c "allowed_origins=${FRONTEND_URL}" \
  -c "environment=poc" \
  || error "CDK deploy failed. Check the output above for details."

success "All CDK stacks deployed successfully."

# =============================================================================
# 4. Capture stack outputs
# =============================================================================
info "Fetching stack outputs..."

USER_POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name TalentLensAuthStack \
  --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" \
  --output text)

USER_POOL_CLIENT_ID=$(aws cloudformation describe-stacks \
  --stack-name TalentLensAuthStack \
  --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='UserPoolClientId'].OutputValue" \
  --output text)

API_URL=$(aws cloudformation describe-stacks \
  --stack-name TalentLensComputeStack \
  --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiFunctionUrl'].OutputValue" \
  --output text)

[[ -z "$USER_POOL_ID" ]]        && error "Could not read UserPoolId from CloudFormation outputs."
[[ -z "$USER_POOL_CLIENT_ID" ]] && error "Could not read UserPoolClientId from CloudFormation outputs."
[[ -z "$API_URL" ]]             && error "Could not read ApiFunctionUrl from CloudFormation outputs."

success "Stack outputs captured:"
echo "  UserPoolId:       $USER_POOL_ID"
echo "  UserPoolClientId: $USER_POOL_CLIENT_ID"
echo "  API URL:          $API_URL"

# =============================================================================
# 5. Build the frontend
# =============================================================================
info "Installing frontend dependencies..."
cd "$SCRIPT_DIR/frontend"
npm install --silent

info "Writing frontend production environment..."
cat > .env.production <<EOF
VITE_API_BASE_URL=${API_URL}
VITE_COGNITO_USER_POOL_ID=${USER_POOL_ID}
VITE_COGNITO_CLIENT_ID=${USER_POOL_CLIENT_ID}
EOF

info "Building frontend (Vite production build)..."
npm run build || error "Frontend build failed. Check the output above."
success "Frontend build complete (dist/)."

# =============================================================================
# 6. Deploy frontend to S3
# =============================================================================
FRONTEND_BUCKET="talentlens-frontend-${AWS_ACCOUNT_ID}"

info "Creating S3 bucket for frontend (if not exists): $FRONTEND_BUCKET"
aws s3api create-bucket \
  --bucket "$FRONTEND_BUCKET" \
  --region "$AWS_REGION" \
  2>/dev/null || true   # bucket may already exist — ignore error

# Enable static website hosting
aws s3 website "s3://${FRONTEND_BUCKET}" \
  --index-document index.html \
  --error-document index.html   # SPA — route all 404s to index.html

# Make objects publicly readable (S3 static website hosting requires this)
aws s3api put-public-access-block \
  --bucket "$FRONTEND_BUCKET" \
  --public-access-block-configuration \
    "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

aws s3api put-bucket-policy \
  --bucket "$FRONTEND_BUCKET" \
  --policy "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Sid\": \"PublicReadGetObject\",
      \"Effect\": \"Allow\",
      \"Principal\": \"*\",
      \"Action\": \"s3:GetObject\",
      \"Resource\": \"arn:aws:s3:::${FRONTEND_BUCKET}/*\"
    }]
  }"

info "Syncing frontend build to S3..."
aws s3 sync dist/ "s3://${FRONTEND_BUCKET}" \
  --delete \
  --region "$AWS_REGION"

FRONTEND_WEBSITE_URL="http://${FRONTEND_BUCKET}.s3-website-${AWS_REGION}.amazonaws.com"
success "Frontend deployed to S3."

# =============================================================================
# 7. Update Lambda CORS with real frontend URL (if it differs from placeholder)
# =============================================================================
if [[ "$FRONTEND_URL" == "http://localhost:5173" ]]; then
  info "Re-deploying compute stack with real frontend URL..."
  cd "$SCRIPT_DIR/infra"
  cdk deploy TalentLensComputeStack \
    --require-approval never \
    -c "allowed_origins=${FRONTEND_WEBSITE_URL}" \
    -c "environment=poc" \
    || warn "CORS update deploy failed — re-run manually with the correct FRONTEND_URL."
  success "Lambda CORS updated to: $FRONTEND_WEBSITE_URL"
fi

# =============================================================================
# 8. Summary
# =============================================================================
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           TalentLens AI — Deployment Complete            ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${CYAN}Frontend URL:${NC}       $FRONTEND_WEBSITE_URL"
echo -e "  ${CYAN}API URL:${NC}            $API_URL"
echo -e "  ${CYAN}User Pool ID:${NC}       $USER_POOL_ID"
echo -e "  ${CYAN}User Pool Client:${NC}   $USER_POOL_CLIENT_ID"
echo -e "  ${CYAN}AWS Account:${NC}        $AWS_ACCOUNT_ID"
echo -e "  ${CYAN}Region:${NC}             $AWS_REGION"
echo ""
echo -e "  ${YELLOW}Next steps:${NC}"
echo -e "  1. Open the frontend URL above in your browser"
echo -e "  2. Sign up for an account via Cognito"
echo -e "  3. (Optional) Set up CloudFront in front of the S3 bucket for HTTPS"
echo -e "     Then re-run:  FRONTEND_URL=https://your-cf-domain.cloudfront.net ./deploy.sh"
echo ""
