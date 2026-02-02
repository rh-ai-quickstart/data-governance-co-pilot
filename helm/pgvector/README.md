# PGVector Helm Chart with Data Loader

This Helm chart deploys PostgreSQL with the pgvector extension and automatically loads sample e-commerce data.

**Important:** This deployment of the PostgreSQL database is not intended for production use. Data backups and fault tolerance are
not provisioned. For production, consider running a robust fault-tolerant solution provided by Enterprise Database (EDB) on OpenShift.

## Architecture

The chart includes:
- **StatefulSet**: PostgreSQL 15 with pgvector extension
- **Headless Service**: For stable pod DNS names
- **Data Loader Job**: Kubernetes Job that loads CSV data after PostgreSQL starts
- **Init Scripts**: ConfigMap that enables the pgvector extension on startup

## Data Loading Approach

Due to ConfigMap size limits (3MB max), we use a **custom container image** approach with OpenShift BuildConfig:

1. CSV files (~45MB) are uploaded to OpenShift using a **Binary Build**
2. The image is built **inside OpenShift** (no external registry or local podman required)
3. An OpenShift Job uses this image to load data into PostgreSQL

### Building the Data Loader Image

The Makefile automatically builds the image inside OpenShift during installation.

See the readme file in the root helm directory.

```bash
make build-data-loader-image NAMESPACE=<your-namespace>
```

This will:
1. Create an ImageStream `pgvector-data-loader`
2. Create/update a BuildConfig with Dockerfile instructions
3. Upload the entire `pgvector/` directory (including CSV files) to OpenShift
4. Build the image inside OpenShift's internal registry
5. Image is available at `image-registry.openshift-image-registry.svc:5000/<namespace>/pgvector-data-loader:latest`

**Note:** The build uploads ~45MB of CSV data, so it may take 1-2 minutes depending on your network speed.

### What Gets Loaded

The data loader creates:

**Tables:**
- `dim_customer` - Customer master data (99K rows)
- `fact_orders` - Order transactions (99K rows)
- `fact_order_payments` - Payment records (103K rows)

**Views:**
- `v_rpt_customer_ltv_certified` - [CERTIFIED] Customer lifetime value metrics
- `v_cust_ltv_agg_DEPRECATED` - [DEPRECATED] Old LTV calculation
- `sales_rpt_v2` - Orders before 2018
- `customer_master_DEPRECATED` - Deprecated customer table (50% sample)

## Installation

See the main Makefile in `helm/` directory:

## Monitoring Data Load

Check the data loader job status:

```bash
# Watch job progress
oc logs -f job/pgvector-data-loader -n <namespace>

# Check job status
oc get job pgvector-data-loader -n <namespace>

# If job fails, get detailed logs
oc describe job pgvector-data-loader -n <namespace>
```

## OpenShift Compatibility

The data loader image is built to run in OpenShift's restricted security context:
- Runs as non-root user (UID 1001)
- Uses Red Hat UBI9 Python base image
- Installs packages with `pip install --user`
- Proper file permissions for group 0

## Files

- `Dockerfile.data-loader` - Container image definition
- `scripts/load_data.py` - Python script that loads data
- `templates/data-loader-job.yaml` - Kubernetes Job manifest
- `templates/statefulset.yaml` - PostgreSQL StatefulSet
- `templates/configmap.yaml` - Init script for pgvector extension
- `templates/service.yaml` - Headless service
- `templates/secrets.yaml` - Database credentials

## Troubleshooting

**Job fails with "ImagePullBackOff":**
- Ensure you ran `make build-data-loader-image` before `make install`
- Check that the namespace matches

**Job fails with connection errors:**
- The job waits up to 60 seconds for PostgreSQL
- Check PostgreSQL pod logs: `oc logs pgvector-0 -n <namespace>`

**Data doesn't load:**
- Check job logs: `oc logs job/pgvector-data-loader -n <namespace>`
- Verify CSV files exist in `../../notebooks/dataset/`
