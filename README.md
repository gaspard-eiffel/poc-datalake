# poc-datalake

Pulumi (Python) project that provisions an Entra-only Azure Blob storage account (ADLS Gen2) for the Eiffel datalake POC.

## What it creates

All resources live in the resource group `rg-eiffel-int-datalake`:

| Resource | Details |
|---|---|
| Resource group | `rg-eiffel-int-datalake` |
| Storage account | StorageV2, Standard LRS, Hot tier, hierarchical namespace enabled, TLS 1.2 minimum, name `stdatalake<random>` |
| Blob container | `default`, private |
| Role assignment | `Storage Blob Data Contributor` on the storage account for the Entra group `sec-users-azure-sub-eiffel-int-web-apps` |

Access model:
* Shared key (account keys and account SAS) is disabled, so only Entra ID tokens work.
* Anonymous access is disabled.
* Only members of the group get data access. Being Owner or Contributor on the subscription is not enough to read blobs, because those roles only cover the management plane.

## Run it from a Windows laptop

Prerequisites (PowerShell, no admin rights needed, everything installs under your user profile):

```powershell
# 1. uv (manages Python and the local .venv, installs to %USERPROFILE%\.local\bin)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Pulumi CLI (official script, installs to %USERPROFILE%\.pulumi\bin and updates your user PATH)
powershell -ExecutionPolicy ByPass -c "iex ((New-Object System.Net.WebClient).DownloadString('https://get.pulumi.com/install.ps1'))"
```

The Azure CLI is also needed. If you do not have it, install the per-user MSI or the portable ZIP from https://learn.microsoft.com/cli/azure/install-azure-cli-windows. Do not install it with `uv tool`, its `az` shim does not work.

Open a new terminal afterwards so the PATH is refreshed. If the Pulumi script is blocked, download the zip from https://www.pulumi.com/docs/install/versions/, extract it anywhere, and add the folder containing `pulumi.exe` to your user PATH (Settings, System, About, Advanced system settings, Environment Variables, user `Path`). If a tool is already installed by your IT team, skip it.

The Pulumi `uv` toolchain (see [Pulumi.yaml](Pulumi.yaml)) creates `.venv` and installs the dependencies from [pyproject.toml](pyproject.toml) on first run, downloading a suitable Python if none is present. No system Python is required.

Your account needs:
* `Contributor` plus `User Access Administrator` (or `Owner`) on the target subscription, since the stack creates a role assignment.
* Permission to read groups in Entra ID (default for members of the tenant).

Deploy:

```powershell
cd C:\Users\GaspardFerey\git\poc-datalake

az login
az account show -o table

# State backend: local file for a POC (or use `pulumi login` for Pulumi Cloud)
pulumi login --local
$env:PULUMI_CONFIG_PASSPHRASE = "<choose a passphrase>"

pulumi stack init dev
pulumi config set azure-native:location westeurope   # optional, westeurope is the default

pulumi preview    # review the plan
pulumi up         # deploy
```

Pulumi creates `.venv` and installs the dependencies on first run. The stack uses your `az login` session, so no secrets are stored.

Tear down with `pulumi destroy`.

## Access the blobs in the `default` container

You must be a member of `sec-users-azure-sub-eiffel-int-web-apps`. Role assignments can take up to about 10 minutes to propagate, and you may need to sign out and in again to refresh group membership in your token.

Get the account name with `pulumi stack output storage_account`.

**Azure Portal**
1. Open the storage account, then Data storage, Containers, `default`.
2. "Authentication method" should show "Microsoft Entra user account". Shared key access is disabled, so the access key option does not work.

**Azure Storage Explorer (desktop, recommended for browsing)**
1. Install it: `winget install Microsoft.Azure.StorageExplorer`.
2. Sign in with your Eiffel account, then expand your subscription, Storage Accounts, the account, Blob Containers, `default`.

**Azure CLI**

```powershell
az login
$acct = pulumi stack output storage_account
az storage blob list --account-name $acct --container-name default --auth-mode login -o table
az storage blob upload --account-name $acct --container-name default --name hello.txt --file .\hello.txt --auth-mode login
az storage blob download --account-name $acct --container-name default --name hello.txt --file .\out.txt --auth-mode login
```

**AzCopy**

```powershell
azcopy login
azcopy copy ".\data\*" "https://<account>.blob.core.windows.net/default/" --recursive
```

**Python (azure-storage-blob)**

```python
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

svc = BlobServiceClient("https://<account>.blob.core.windows.net", credential=DefaultAzureCredential())
for blob in svc.get_container_client("default").list_blobs():
    print(blob.name)
```

## Expected cost

Prices are indicative pay-as-you-go list prices for West Europe, Standard LRS, Hot tier, with hierarchical namespace. Check the [Azure pricing calculator](https://azure.microsoft.com/pricing/calculator/) for current figures.

| Item | Unit price (approx.) | Example: 100 GB, light usage |
|---|---|---|
| Resource group, role assignment, container, Entra auth | Free | 0 |
| Data stored (Hot, LRS, ADLS Gen2) | about 0.019 to 0.021 USD per GB per month | about 2 USD |
| Write operations | about 0.065 USD per 10,000 | well under 1 USD |
| Read operations | about 0.005 USD per 10,000 | well under 1 USD |
| Egress to the internet | first 100 GB per month free, then about 0.087 USD per GB | 0 |
| Ingress, access from within the same region | Free | 0 |

Rough monthly totals:
* Empty or a few GB: under 0.50 USD per month.
* 100 GB with light usage: about 2 to 4 USD per month.
* 1 TB with light usage: about 20 to 25 USD per month.

Notes:
* There is no fixed monthly fee, you pay only for what is stored and used.
* Cost levers: use the Cool tier for rarely read data (cheaper storage, costlier reads), or add lifecycle rules.
* Hierarchical namespace makes some operations pricier than flat blob storage, and Standard LRS keeps three copies in a single datacenter. Switch to ZRS or GRS if resilience matters more than cost (roughly 1.25x to 2x storage price).
