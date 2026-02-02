# pgAdmin Helm Chart

This Helm chart deploys pgAdmin 4, a web-based PostgreSQL administration tool, pre-configured to connect to the pgvector database.

## Features

- **Auto-configured Database Connection**: Automatically connects to the pgvector PostgreSQL database
- **Persistent Storage**: Uses a PVC to store pgAdmin settings and preferences
- **Secure Access**: HTTPS route with automatic TLS termination
- **Browser-Based**: No local installation required - access via web browser

## Architecture

The chart includes:
- **Deployment**: pgAdmin 4 container
- **Service**: ClusterIP service for internal access
- **Route**: OpenShift Route for external browser access with HTTPS
- **PVC**: Persistent storage for pgAdmin data (1Gi default)
- **ConfigMap**: Pre-configured server connection to pgvector database
- **Secret**: pgAdmin login credentials and PostgreSQL connection info

## Installation

pgAdmin is automatically installed as part of the main quickstart installation.

See the readme file in the root helm directory.

The installation will output the pgAdmin URL at the end.

## Accessing pgAdmin

After installation completes, you'll see output like:

```
pgAdmin URL: https://pgadmin-myns.apps.cluster.example.com
Login with email: admin@example.com
```

1. Open the URL in your browser
2. Login with the email and password you provided in the make command
3. You'll see "PGVector Database" in the server list
4. Click on it and enter the PostgreSQL password when prompted
5. Browse your database!

## Pre-configured Connection

The pgAdmin deployment includes a pre-configured server connection:

- **Server Name**: PGVector Database
- **Host**: pgvector-0.pgvector-postgres-service.<namespace>.svc.cluster.local
- **Port**: 5432
- **Username**: From postgres.userId parameter
- **Database**: postgres (maintenance database)

When you click on the server for the first time, pgAdmin will prompt you for the password. Use the `postgres.password` you set during installation.

## Configuration

### Values

| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| `pgadmin.email` | pgAdmin login email | Yes | - |
| `pgadmin.password` | pgAdmin login password | Yes | - |
| `postgres.host` | PostgreSQL hostname | Yes | pgvector-0.pgvector-postgres-service |
| `postgres.port` | PostgreSQL port | Yes | 5432 |
| `postgres.user` | PostgreSQL username | Yes | - |
| `postgres.password` | PostgreSQL password | Yes | - |
| `postgres.database` | PostgreSQL database name | Yes | - |
| `storage.size` | PVC storage size | No | 1Gi |

## Uninstallation

pgAdmin is automatically uninstalled as part of the quickstart uninstallation:

```bash
make uninstall NAMESPACE=myns
```

Or uninstall only pgAdmin:

```bash
make pgadmin-uninstall NAMESPACE=myns
```

This will remove the deployment, service, route, and PVC.

## Troubleshooting

**pgAdmin pod not starting:**
```bash
oc logs -l app.kubernetes.io/name=pgadmin -n <namespace>
oc describe pod -l app.kubernetes.io/name=pgadmin -n <namespace>
```

**Can't connect to database:**
- Verify the pgvector database is running: `oc get pods -n <namespace>`
- Check that you're using the correct PostgreSQL password
- Ensure you're in the same namespace as the database

**Route not accessible:**
```bash
oc get route pgadmin -n <namespace>
```

## Security Notes

PGAdmin is a powerful tool and usually does not need to be made accessible on a kubernetes environment.
This deployment is intended for **demo and development purposes** to help users browse the backend database objects to evaluate
how the data governance copilot is making decisions. For production use, consider:

- Using stronger passwords
- Adding network policies to restrict access
- Implementing additional authentication (LDAP, OAuth, etc.)
- Regular backups of the pgAdmin PVC
- Enabling audit logging
- Restricting database user permissions

## Files

- `templates/deployment.yaml` - pgAdmin deployment with persistent storage
- `templates/service.yaml` - ClusterIP service
- `templates/route.yaml` - HTTPS route with automatic TLS
- `templates/pvc.yaml` - Persistent volume claim for pgAdmin data
- `templates/configmap.yaml` - Pre-configured server connection
- `templates/secret.yaml` - Login credentials and database connection info
