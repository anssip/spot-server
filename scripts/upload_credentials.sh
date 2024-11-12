#! /bin/bash

export PROJECT_ID="spotcanvas-prod"

# Activate virtual environment
source venv/bin/activate

python3 scripts/upload_credentials.py --project-id $PROJECT_ID