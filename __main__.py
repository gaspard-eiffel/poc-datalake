"""Entra-only Azure Blob storage (ADLS Gen2) inside rg-eiffel-int-datalake."""
import uuid

import pulumi
import pulumi_azure_native as azure_native
import pulumi_azuread as azuread

RESOURCE_GROUP_NAME = "rg-eiffel-int-datalake"
ACCESS_GROUP_NAME = "sec-users-azure-sub-eiffel-int-web-apps"
CONTAINER_NAME = "default"

# Built-in role "Storage Blob Data Contributor" (read, write, delete blobs)
BLOB_DATA_CONTRIBUTOR_ROLE_ID = "ba92f5b4-2d11-453d-a403-e96b0029c9fe"

client = azure_native.authorization.get_client_config()
group = azuread.get_group(display_name=ACCESS_GROUP_NAME, security_enabled=True)

resource_group = azure_native.resources.ResourceGroup(
    "rg-datalake",
    resource_group_name=RESOURCE_GROUP_NAME,
)

storage_account = azure_native.storage.StorageAccount(
    "stdatalake",  # Pulumi appends a random suffix: account names are globally unique
    resource_group_name=resource_group.name,
    kind=azure_native.storage.Kind.STORAGE_V2,
    sku=azure_native.storage.SkuArgs(name=azure_native.storage.SkuName.STANDARD_LRS),
    access_tier=azure_native.storage.AccessTier.HOT,
    is_hns_enabled=True,  # hierarchical namespace = data lake (ADLS Gen2)
    minimum_tls_version=azure_native.storage.MinimumTlsVersion.TLS1_2,
    enable_https_traffic_only=True,
    allow_blob_public_access=False,  # no anonymous access
    allow_shared_key_access=False,  # no account keys, Entra ID only
    default_to_o_auth_authentication=True,
    public_network_access=azure_native.storage.PublicNetworkAccess.ENABLED,
)

container = azure_native.storage.BlobContainer(
    "container-default",
    container_name=CONTAINER_NAME,
    account_name=storage_account.name,
    resource_group_name=resource_group.name,
    public_access=azure_native.storage.PublicAccess.NONE,
)

# Only the Entra group gets data access. Role assignment names must be GUIDs.
group_role_assignment = azure_native.authorization.RoleAssignment(
    "group-blob-data-contributor",
    role_assignment_name=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{RESOURCE_GROUP_NAME}/{ACCESS_GROUP_NAME}")),
    scope=storage_account.id,
    principal_id=group.object_id,
    principal_type=azure_native.authorization.PrincipalType.GROUP,
    role_definition_id=pulumi.Output.concat(
        "/subscriptions/", client.subscription_id,
        "/providers/Microsoft.Authorization/roleDefinitions/", BLOB_DATA_CONTRIBUTOR_ROLE_ID,
    ),
)

pulumi.export("resource_group", resource_group.name)
pulumi.export("storage_account", storage_account.name)
pulumi.export("blob_endpoint", storage_account.primary_endpoints.blob)
pulumi.export("dfs_endpoint", storage_account.primary_endpoints.dfs)
pulumi.export("container", container.name)
