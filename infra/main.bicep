targetScope = 'resourceGroup'

@minLength(1)
@description('Nombre del entorno azd (prefijo de recursos).')
param environmentName string

@description('Región de los recursos.')
param location string = resourceGroup().location

@description('Intentar desplegar MAI-DS-R1 (competencia). Si la cuota/modelo no está disponible, dejar en false.')
param deployMaiDsR1 bool = false

@description('Capacidad (TPM miles) para gpt-4o.')
param capGpt4o int = 20

@description('Capacidad para MAI-Thinking-1.')
param capMai int = 20

@description('Capacidad para text-embedding-3-large.')
param capEmbeddings int = 50

var token = uniqueString(subscription().id, resourceGroup().id, environmentName)
var prefix = 'amvpqr'
var tags = { 'azd-env-name': environmentName, proyecto: 'AMV-PQR' }

// ---------------- Observabilidad ----------------
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${prefix}-logs-${token}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appi 'Microsoft.Insights/components@2020-02-02' = {
  name: '${prefix}-appi-${token}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
  }
}

// ---------------- Identidad gestionada (usada por el Container App) ----------------
resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-id-${token}'
  location: location
  tags: tags
}

// ---------------- Azure AI Services (Foundry) ----------------
resource ai 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: '${prefix}-ai-${token}'
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: '${prefix}-ai-${token}'
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource depEmbeddings 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: ai
  name: 'text-embedding-3-large'
  sku: { name: 'Standard', capacity: capEmbeddings }
  properties: {
    model: { format: 'OpenAI', name: 'text-embedding-3-large', version: '1' }
  }
}

resource depGpt4o 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: ai
  name: 'gpt-4o'
  sku: { name: 'Standard', capacity: capGpt4o }
  properties: {
    model: { format: 'OpenAI', name: 'gpt-4o', version: '2024-11-20' }
  }
  dependsOn: [ depEmbeddings ]
}

resource depMai 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: ai
  name: 'mai-thinking-1'
  sku: { name: 'GlobalStandard', capacity: capMai }
  properties: {
    model: { format: 'Microsoft', name: 'MAI-Thinking-1', version: '2026-06-01' }
  }
  dependsOn: [ depGpt4o ]
}

resource depMaiDsR1 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (deployMaiDsR1) {
  parent: ai
  name: 'mai-ds-r1'
  sku: { name: 'GlobalStandard', capacity: 10 }
  properties: {
    model: { format: 'Microsoft', name: 'MAI-DS-R1', version: '1' }
  }
  dependsOn: [ depMai ]
}

// ---------------- Azure AI Search ----------------
resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: '${prefix}-srch-${token}'
  location: location
  tags: tags
  sku: { name: 'basic' }
  properties: {
    authOptions: null
    disableLocalAuth: true
    hostingMode: 'default'
    partitionCount: 1
    replicaCount: 1
    semanticSearch: 'free'
  }
}

// ---------------- Storage (Tables + Blob) ----------------
resource stg 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: toLower('${prefix}st${token}')
  location: location
  tags: tags
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
  }
}

resource blob 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: stg
  name: 'default'
}

resource adjuntos 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blob
  name: 'adjuntos'
}

// ---------------- Service Bus (ingesta) ----------------
resource sb 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: '${prefix}-sb-${token}'
  location: location
  tags: tags
  sku: { name: 'Standard', tier: 'Standard' }
  properties: { disableLocalAuth: true }
}

resource sbQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: sb
  name: 'pqr-ingesta'
  properties: { maxDeliveryCount: 10 }
}

// ---------------- Roles (built-in) ----------------
var roleOpenAiUser = 'a97b65f3-24c7-4388-baec-2e87135dc908' // Cognitive Services OpenAI User
var roleSearchIndexContrib = '8ebe5a00-799e-43f5-93ac-243d3dce84a7' // Search Index Data Contributor
var roleSearchServiceContrib = '7ca78c08-252a-4471-8644-bb5ff32d4ba0' // Search Service Contributor
var roleTableContrib = '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3' // Storage Table Data Contributor
var roleBlobContrib = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'  // Storage Blob Data Contributor
var roleSbReceiver = '4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0'   // Service Bus Data Receiver
var roleSbSender = '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39'     // Service Bus Data Sender

resource raOpenAi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(ai.id, uami.id, roleOpenAiUser)
  scope: ai
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleOpenAiUser)
  }
}

resource raSearchIndex 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, uami.id, roleSearchIndexContrib)
  scope: search
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleSearchIndexContrib)
  }
}

resource raSearchService 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, uami.id, roleSearchServiceContrib)
  scope: search
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleSearchServiceContrib)
  }
}

resource raTable 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(stg.id, uami.id, roleTableContrib)
  scope: stg
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleTableContrib)
  }
}

resource raBlob 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(stg.id, uami.id, roleBlobContrib)
  scope: stg
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleBlobContrib)
  }
}

resource raSbRecv 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(sb.id, uami.id, roleSbReceiver)
  scope: sb
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleSbReceiver)
  }
}

resource raSbSend 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(sb.id, uami.id, roleSbSender)
  scope: sb
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleSbSender)
  }
}

// ---------------- Container Apps ----------------
resource acaEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${prefix}-cae-${token}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

resource acaApi 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${prefix}-api-${token}'
  location: location
  tags: union(tags, { 'azd-service-name': 'api' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${uami.id}': {} }
  }
  properties: {
    managedEnvironmentId: acaEnv.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        corsPolicy: { allowedOrigins: [ '*' ], allowedMethods: [ '*' ], allowedHeaders: [ '*' ] }
      }
    }
    template: {
      containers: [
        {
          name: 'api'
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'AI_SERVICES_ENDPOINT', value: 'https://${ai.name}.openai.azure.com' }
            { name: 'AI_INFERENCE_ENDPOINT', value: 'https://${ai.name}.services.ai.azure.com/models' }
            { name: 'DEPLOY_CLASSIFY', value: 'gpt-4o' }
            { name: 'DEPLOY_COMPETENCE', value: deployMaiDsR1 ? 'mai-ds-r1' : 'mai-thinking-1' }
            { name: 'DEPLOY_DRAFT', value: 'mai-thinking-1' }
            { name: 'DEPLOY_EMBEDDINGS', value: 'text-embedding-3-large' }
            { name: 'SEARCH_ENDPOINT', value: 'https://${search.name}.search.windows.net' }
            { name: 'SEARCH_INDEX', value: 'reglas-idx' }
            { name: 'STORAGE_ACCOUNT', value: stg.name }
            { name: 'AZURE_CLIENT_ID', value: uami.properties.clientId }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appi.properties.ConnectionString }
            { name: 'CONFIANZA_MIN', value: '70' }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
  dependsOn: [ depMai, raOpenAi, raTable, raBlob, raSearchIndex ]
}

// ---------------- Static Web App (frontend) ----------------
resource swa 'Microsoft.Web/staticSites@2023-12-01' = {
  name: '${prefix}-web-${token}'
  location: location
  tags: union(tags, { 'azd-service-name': 'web' })
  sku: { name: 'Free', tier: 'Free' }
  properties: {
    stagingEnvironmentPolicy: 'Enabled'
    allowConfigFileUpdates: true
  }
}

output AZURE_LOCATION string = location
output AI_SERVICES_ENDPOINT string = 'https://${ai.name}.openai.azure.com'
output AI_INFERENCE_ENDPOINT string = 'https://${ai.name}.services.ai.azure.com/models'
output SEARCH_ENDPOINT string = 'https://${search.name}.search.windows.net'
output STORAGE_ACCOUNT string = stg.name
output SERVICEBUS_NAMESPACE string = sb.name
output API_URI string = 'https://${acaApi.properties.configuration.ingress.fqdn}'
output WEB_URI string = 'https://${swa.properties.defaultHostname}'
output AZURE_MANAGED_IDENTITY_CLIENT_ID string = uami.properties.clientId
