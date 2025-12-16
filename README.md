# Arcade MCP Deployer

Bulk deploy Arcade MCPs for all available toolkits.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your values
```

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `ARCADE_API_KEY` | Yes | Arcade project API key |
| `ARCADE_ORG_ID` | Yes | Organization ID |
| `ARCADE_PROJECT_ID` | Yes | Project ID |
| `GATEWAY_SLUG_PREFIX` | No | URL prefix (e.g., "toqan" → "toqan-github") |

Note: A fixed 10-second delay between API calls is enforced to prevent rate limiting.

## Usage

```bash
# Preview (no changes)
python deploy.py --dry-run

# Deploy all MCPs
python deploy.py
```

## Output

Creates `deployed_mcps.csv`:

```csv
mcp,description,url,num_tools
Github,Tools for GitHub,https://api.arcade.dev/mcp/toqan-github,44
```
