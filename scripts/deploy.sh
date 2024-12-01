#!/bin/bash

PROJECT_ID="spotcanvas-prod"
REGION="europe-west1"
SHARD_COUNT=10
VERSION=$(date +%Y%m%d-%H%M%S)

# Exit on any error
set -e

# Ensure Cloud Build is set up correctly
chmod +x scripts/setup-cloud-build.sh
./scripts/setup-cloud-build.sh

echo "Deploying using Cloud Build..."

# Generate cloudbuild.yaml dynamically
cat > cloudbuild.yaml.tmp << EOF
steps:
  # Build the container image
  - name: "gcr.io/cloud-builders/docker"
    args: 
      - "build"
      - "-t"
      - "\${_REGION}-docker.pkg.dev/\${PROJECT_ID}/spot-server/spot-server:\${_VERSION}"
      - "."

  # Push the container image to Artifact Registry
  - name: "gcr.io/cloud-builders/docker"
    args: 
      - "push"
      - "\${_REGION}-docker.pkg.dev/\${PROJECT_ID}/spot-server/spot-server:\${_VERSION}"

EOF

# Add deploy steps for each shard
for i in $(seq 0 $((SHARD_COUNT-1))); do
  cat >> cloudbuild.yaml.tmp << EOF
  # Deploy shard $i
  - name: "gcr.io/cloud-builders/gcloud"
    id: deploy-shard-$i
    args:
      - "run"
      - "deploy"
      - "spot-server-shard-$i"
      - "--image"
      - "\${_REGION}-docker.pkg.dev/\${PROJECT_ID}/spot-server/spot-server:\${_VERSION}"
      - "--region"
      - "\${_REGION}"
      - "--platform"
      - "managed"
      - "--allow-unauthenticated"
      - "--set-env-vars"
      - "PROJECT_ID=\${PROJECT_ID},ENVIRONMENT=production,SHARD_COUNT=$SHARD_COUNT,SHARD_INDEX=$i"
      - "--memory"
      - "512Mi"
      - "--min-instances"
      - "1"
      - "--max-instances"
      - "10"
      - "--timeout"
      - "300s"
      - "--port"
      - "8080"
      - "--cpu"
      - "1"
      - "--use-http2"
      - "--cpu-boost"

EOF
done

# Add the rest of the config
cat >> cloudbuild.yaml.tmp << EOF
substitutions:
  _REGION: $REGION

images:
  - "\${_REGION}-docker.pkg.dev/\${PROJECT_ID}/spot-server/spot-server:\${_VERSION}"

timeout: 1800s
EOF

# Use the generated config
mv cloudbuild.yaml.tmp cloudbuild.yaml

# Submit the build
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_REGION="$REGION",_VERSION="$VERSION" \
  .

# Wait for all services to be healthy
for i in $(seq 0 $((SHARD_COUNT-1))); do
  echo "Waiting for shard $i to be healthy..."
  gcloud run services describe spot-server-shard-$i \
    --region=$REGION \
    --project=$PROJECT_ID \
    --format='get(status.conditions[0].status)' \
    || true
done

echo "Deployment complete!" 