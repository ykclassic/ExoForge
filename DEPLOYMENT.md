# EXOFORGE Deployment & Operations Guide

## 1. Prerequisites
- **GitHub**: Repository hosting the EXOFORGE codebase.
- **Supabase**: Active PostgreSQL 14+ database instance.
- **Render**: Account for containerized worker deployment.
- **Gate.io**: API keys with Spot Trading permissions (IP binding recommended).
- **Discord**: Webhook URL generated from your server channel.

## 2. Supabase Configuration
1. Navigate to your Supabase project dashboard.
2. Go to **Project Settings > Database** and copy the **Connection string (URI)**.
3. Replace `[YOUR-PASSWORD]` with your actual database password. Ensure the port is `6543` to utilize the Supabase IPv4 connection pooler.
4. *Initial Setup*: Run the bot locally once to trigger `Base.metadata.create_all` which generates the schema tables (`signals`, `trades`, `orders`).

## 3. Render Deployment Steps
1. Connect your GitHub repository to Render.
2. Go to **Blueprints > New Blueprint Instance** and select your repository.
3. Render will automatically detect the `render.yaml` file and provision the `exoforge-trading-bot` worker service.
4. Go to the newly created service > **Environment**.
5. Input the exact values for the following sensitive variables:
   - `GATEIO_API_KEY`
   - `GATEIO_API_SECRET`
   - `SUPABASE_DB_URL` (Use the transaction pooler URI)
   - `DISCORD_WEBHOOK_URL`

## 4. Continuous Integration
To enable automatic deployments:
1. In Render, go to your service > **Settings** and copy the **Deploy Hook** URL.
2. In GitHub, go to your repository **Settings > Secrets and variables > Actions**.
3. Create a new repository secret named `RENDER_DEPLOY_HOOK_URL` and paste the URL.
4. The GitHub Action in `.github/workflows/deploy.yml` will now automatically trigger Render to pull and deploy the latest Docker image on every push to `main`.

## 5. Production Operations Checklist
- [ ] Database backups configured in Supabase.
- [ ] Gate.io API Keys restricted to Spot Trading only (No withdrawals).
- [ ] Discord Webhook tested successfully.
- [ ] Render logging dashboard accessible for real-time `trading.log` outputs.
