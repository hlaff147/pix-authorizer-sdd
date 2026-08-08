#!/bin/bash
set -eo pipefail

echo "Initializing DynamoDB tables in LocalStack..."

awslocal dynamodb create-table \
    --table-name pix_transactions_store \
    --attribute-definitions \
        AttributeName=PK,AttributeType=S \
        AttributeName=SK,AttributeType=S \
    --key-schema \
        AttributeName=PK,KeyType=HASH \
        AttributeName=SK,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1

echo "DynamoDB table pix_transactions_store created successfully!"
