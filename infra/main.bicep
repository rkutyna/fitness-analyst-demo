// Fitness Analyst demo on Azure Container Apps (consumption plan, scale to zero).
// Scope: resource group. No secrets and no registry credentials: the image comes
// from a public GHCR package and the app needs no environment variables.

targetScope = 'resourceGroup'

@description('Azure region for every resource.')
param location string = resourceGroup().location

@description('Base name; the container app, environment and workspace are derived from it.')
@minLength(2)
@maxLength(24)
param appName string = 'faa-demo'

@description('Full image reference, ideally pinned by digest: ghcr.io/<owner>/<name>@sha256:<digest>.')
param image string

@description('Minimum replicas. 0 lets the app scale to zero when idle.')
@minValue(0)
@maxValue(10)
param minReplicas int = 0

@description('Maximum replicas.')
@minValue(1)
@maxValue(10)
param maxReplicas int = 2

@description('Concurrent HTTP requests per replica that trigger scaling out.')
@minValue(1)
param httpConcurrency int = 30

@description('Contact for budget alerts. Empty means no budget resource is created.')
param budgetContactEmail string = ''

@description('Monthly budget amount, in the billing currency of the subscription.')
@minValue(1)
param budgetAmount int = 5

@description('First day of the month the budget starts on (yyyy-MM-01). Pin it after the first deploy: it must not move on later deploys.')
param budgetStartDate string = utcNow('yyyy-MM-01')

@description('Custom domain, for example faa-demo.example.com. Empty means none. Set it on EVERY deploy once added, or a redeploy removes it.')
param customDomain string = ''

@description('Name of the managed certificate that already exists in the environment for customDomain (created by az containerapp hostname bind). Empty binds the hostname without a certificate.')
param managedCertificateName string = ''

var environmentName = '${appName}-env'
var workspaceName = '${appName}-logs'
var hasCustomDomain = !empty(customDomain)
var hasCertificate = hasCustomDomain && !empty(managedCertificateName)

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: workspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: workspace.properties.customerId
        sharedKey: workspace.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  properties: {
    managedEnvironmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8080
        transport: 'auto'
        allowInsecure: false
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
        customDomains: hasCustomDomain ? [
          {
            name: customDomain
            bindingType: hasCertificate ? 'SniEnabled' : 'Disabled'
            certificateId: hasCertificate ? resourceId('Microsoft.App/managedEnvironments/managedCertificates', environmentName, managedCertificateName) : null
          }
        ] : null
      }
    }
    template: {
      containers: [
        {
          name: 'app'
          image: image
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          probes: [
            {
              // Restarts the container if the process stops answering.
              type: 'Liveness'
              httpGet: {
                path: '/healthz'
                port: 8080
              }
              initialDelaySeconds: 5
              periodSeconds: 30
              timeoutSeconds: 3
              failureThreshold: 3
            }
            {
              // /readyz answers 503 until the bundle has loaded, 200 after.
              type: 'Readiness'
              httpGet: {
                path: '/readyz'
                port: 8080
              }
              initialDelaySeconds: 2
              periodSeconds: 10
              timeoutSeconds: 3
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-concurrency'
            http: {
              metadata: {
                concurrentRequests: string(httpConcurrency)
              }
            }
          }
        ]
      }
    }
  }
}

// A monthly budget on the resource group. It alerts; it does not stop spending.
resource budget 'Microsoft.Consumption/budgets@2023-11-01' = if (!empty(budgetContactEmail)) {
  name: '${appName}-monthly'
  properties: {
    category: 'Cost'
    amount: budgetAmount
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: budgetStartDate
    }
    notifications: {
      actual80: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 80
        thresholdType: 'Actual'
        contactEmails: [
          budgetContactEmail
        ]
      }
      forecast100: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 100
        thresholdType: 'Forecasted'
        contactEmails: [
          budgetContactEmail
        ]
      }
    }
  }
}

output fqdn string = app.properties.configuration.ingress.fqdn
output customDomainVerificationId string = environment.properties.customDomainConfiguration.customDomainVerificationId
output environmentName string = environment.name
