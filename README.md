# Setup Instructions

The stack uses github actions, but for local development, follow the below guide.

## CDK Setup 

The AWS Cloud Development Kit (CDK) is used for deploying cloud infrastructure.

1. **Install AWS CDK globally:**
   ```bash
   npm install -g aws-cdk
   ```

2. **Set up AWS credentials** if not already configured (using AWS CLI or environment variables).

3. **Bootstrap your AWS environment** (only required once per AWS account/region):

   This step sets up a special S3 bucket that CDK needs to deploy resources.

   ```bash
   cdk bootstrap
   ```

---

## CDK Deployment Instructions

1. Navigate to the CDK project directory:
   ```bash
   cd cdk
   ```

2. Update the configuration:

   - Open `cdk/config/config.sample.json`.
   - Fill in the required secrets and environment-specific details.
   - Save it as `config.json` in the same directory.

3. Install CDK dependencies inside `cdk/` if not already done:
   ```bash
   npm install
   ```

4. Deploy the CDK stack:

   ```bash
   cdk deploy
   ```

   The deployment will show a list of changes and ask for confirmation — type `y` to proceed.

---

# Notes

- Make sure your AWS CLI is configured properly (`aws configure`).
- CDK apps are region-specific; ensure you're using the correct AWS region.
- If you change config values later, re-run `cdk deploy` to update the deployed resources.

