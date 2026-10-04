#!/usr/bin/env bash
# Deployment steps used by .github/workflows/deploy.yml and teardown.yml. Each subcommand is
# idempotent and reads its inputs from the environment:
#   DEPLOY_TOOL   terraform | bicep
#   TARGET_ENV    dev | prod
#   LOCATION      Azure region (default eastus2)
#   ALERT_EMAIL   drift alert receiver (repository variable MODELRISK_ALERT_EMAIL)
#   ARM_* / AZURE_*  set by azure/login (OIDC) and the workflow env
#
#   deploy.sh provision   create/update the evidence plane, write rg/storage to $GITHUB_OUTPUT
#   deploy.sh smoke       check policy assignments, the workbook and blob versioning exist
#   deploy.sh publish     run the gate and upload its report and the audit log (Entra auth)
#   deploy.sh destroy     tear the environment down (teardown workflow only)
set -euo pipefail

TOOL="${DEPLOY_TOOL:-terraform}"
ENV_NAME="${TARGET_ENV:?TARGET_ENV is required}"
LOCATION="${LOCATION:-eastus2}"
STACK="infra/terraform"
OUT="${GITHUB_OUTPUT:-/dev/stdout}"
EMAIL_ARGS=()

log() { echo "::group::$*"; }
end() { echo "::endgroup::"; }

tf_init() {
  : "${TFSTATE_RESOURCE_GROUP:?set repo/environment variable TFSTATE_RESOURCE_GROUP}"
  : "${TFSTATE_STORAGE_ACCOUNT:?set repo/environment variable TFSTATE_STORAGE_ACCOUNT}"
  terraform -chdir="$STACK" init -input=false \
    -backend-config="envs/${ENV_NAME}.backend.hcl" \
    -backend-config="resource_group_name=${TFSTATE_RESOURCE_GROUP}" \
    -backend-config="storage_account_name=${TFSTATE_STORAGE_ACCOUNT}" \
    -backend-config="container_name=${TFSTATE_CONTAINER:-tfstate}"
}

provision() {
  if [[ "$TOOL" == "terraform" ]]; then
    log "terraform apply ($ENV_NAME)"
    tf_init
    [[ -n "${ALERT_EMAIL:-}" ]] && EMAIL_ARGS=(-var "alert_email=${ALERT_EMAIL}")
    terraform -chdir="$STACK" apply -auto-approve -input=false \
      -var-file="envs/${ENV_NAME}.tfvars" -var "location=${LOCATION}" "${EMAIL_ARGS[@]}"
    rg=$(terraform -chdir="$STACK" output -raw AZURE_RESOURCE_GROUP)
    st=$(terraform -chdir="$STACK" output -raw EVIDENCE_STORAGE_ACCOUNT)
    end
  else
    log "bicep: az deployment sub create ($ENV_NAME)"
    effect=Audit; alert=false
    [[ "$ENV_NAME" == "prod" ]] && { effect=Deny; alert=true; }
    [[ -n "${ALERT_EMAIL:-}" ]] && EMAIL_ARGS=(alertEmail="${ALERT_EMAIL}")
    outputs=$(az deployment sub create --name "modelrisk-${ENV_NAME}-${GITHUB_RUN_ID:-local}" \
      --location "$LOCATION" --template-file infra/bicep/main.bicep \
      --parameters environment="$ENV_NAME" location="$LOCATION" policyEffect="$effect" deployDriftAlert="$alert" "${EMAIL_ARGS[@]}" \
      --query properties.outputs -o json)
    rg=$(jq -r .AZURE_RESOURCE_GROUP.value <<<"$outputs")
    st=$(jq -r .EVIDENCE_STORAGE_ACCOUNT.value <<<"$outputs")
    end
  fi
  { echo "resource_group=$rg"; echo "storage_account=$st"; } >>"$OUT"
}

smoke() {
  : "${RESOURCE_GROUP:?}" "${STORAGE_ACCOUNT:?}"
  n=$(az policy assignment list -g "$RESOURCE_GROUP" --query "length([?starts_with(name, 'modelrisk-')])" -o tsv)
  [[ "$n" -ge 3 ]] || { echo "::error::expected 3 modelrisk policy assignments, found $n"; exit 1; }
  w=$(az resource list -g "$RESOURCE_GROUP" --resource-type Microsoft.Insights/workbooks --query "length(@)" -o tsv)
  [[ "$w" -ge 1 ]] || { echo "::error::model-risk workbook missing"; exit 1; }
  v=$(az storage account blob-service-properties show --account-name "$STORAGE_ACCOUNT" -g "$RESOURCE_GROUP" --query isVersioningEnabled -o tsv)
  [[ "$v" == "true" ]] || { echo "::error::evidence registry versioning is off"; exit 1; }
  echo "smoke checks passed: $n policy assignments, workbook, versioned evidence registry"
}

publish() {
  : "${STORAGE_ACCOUNT:?}"
  mkdir -p evidence
  modelrisk gate --json > evidence/gate-report.json
  az storage blob upload --auth-mode login --account-name "$STORAGE_ACCOUNT" -c evidence \
    -f evidence/gate-report.json -n "gate/${GITHUB_SHA:-local}.json" --overwrite
  az storage blob upload --auth-mode login --account-name "$STORAGE_ACCOUNT" -c audit \
    -f registry/audit-log.jsonl -n "audit-log/${GITHUB_SHA:-local}.jsonl" --overwrite
  echo "published gate report and audit log for ${GITHUB_SHA:-local}"
}

destroy() {
  if [[ "$TOOL" == "terraform" ]]; then
    tf_init
    terraform -chdir="$STACK" destroy -auto-approve -input=false \
      -var-file="envs/${ENV_NAME}.tfvars" -var "location=${LOCATION}"
  else
    case "$LOCATION" in eastus2) short=eus2 ;; westus2) short=wus2 ;; westeurope) short=weu ;; *) exit 1 ;; esac
    az group delete --name "rg-modelrisk-${ENV_NAME}-${short}-001" --yes
    for p in require-model-card-tags allowed-risk-tier deny-public-ai-endpoints; do
      az policy definition delete --name "modelrisk-${p}" || true
    done
  fi
}

"$@"
