# terraform

Terraform stack.

| File | What it does |
|---|---|
| `versions.tf` | Versions |
| `providers.tf` | azurerm provider |
| `backend.tf` | Partial azurerm backend (Entra auth) |
| `variables.tf` | Inputs |
| `locals.tf` | Policy and workbook files, names |
| `main.tf` | Resources |
| `outputs.tf` | Outputs for the deploy script |
| `.tflint.hcl` | tflint configuration |
| `envs/` | Per-environment settings |
| `tests/` | Offline plan tests |
