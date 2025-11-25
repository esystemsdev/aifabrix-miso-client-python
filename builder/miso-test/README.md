# Miso Test Builder

Build, run, and deploy Miso Test using `@aifabrix/builder`.

---

## Quick Start

### 1. Install

```bash
npm install -g @aifabrix/builder
```

### 2. First Time Setup

```bash
# Check your environment
aifabrix doctor

# Login to controller
aifabrix login --method device --environment dev --controller http://localhost:3100

# Register your application (gets you credentials automatically)
aifabrix app register miso-test --environment miso
```

### 3. Build & Run Locally

```bash
# Build the Docker image
aifabrix build miso-test

# Generate environment variables
aifabrix resolve miso-test

# Run locally
aifabrix run miso-test
```

**Access your app:** <http://localhost:8083>

**View logs:**

```bash
docker logs aifabrix-miso-test -f
```

**Stop:**

```bash
aifabrix down miso-test
# aifabrix down miso-test --volumes   # also remove data volume
```

### 4. Deploy to Azure

```bash
# Build with version tag
aifabrix build miso-test --tag v1.0.0

# Push to registry
aifabrix push miso-test --registry myacr.azurecr.io --tag "v1.0.0,latest"

# Deploy to miso-controller
aifabrix deploy miso-test --controller https://controller.aifabrix.ai --environment dev
```

---

## Using miso-client

> [miso-client](https://github.com/esystemsdev/aifabrix-miso-client)

After registering your app, you automatically get credentials in your secret file. Use miso-client for login, RBAC, audit logs, etc.

**Rotate credentials if needed:**

```bash
aifabrix app rotate-secret miso-test --environment dev
```

---

## Reference

### Common Commands

```bash
# Development
aifabrix build miso-test                        # Build app
aifabrix run miso-test                          # Run locally
aifabrix down miso-test [--volumes]             # Stop app (optionally remove volume)
aifabrix dockerfile miso-test --force           # Generate Dockerfile
aifabrix resolve miso-test                      # Generate .env file

# Deployment
aifabrix json miso-test                         # Preview deployment JSON
aifabrix genkey miso-test                       # Generate deployment key
aifabrix push miso-test --registry myacr.azurecr.io # Push to ACR
aifabrix deploy miso-test --controller <url>    # Deploy to Azure

# Management
aifabrix app register miso-test --environment dev
aifabrix app list --environment dev
aifabrix app rotate-secret miso-test --environment dev

# Utilities
aifabrix doctor                                   # Check environment
aifabrix login --method device --environment dev  # Login
aifabrix --help                                   # Get help
```

### Build Options

```bash
aifabrix build miso-test --tag v1.0.0           # Custom tag
aifabrix build miso-test --force-template       # Force template regeneration
aifabrix build miso-test --language typescript  # Override language detection
```

### Run Options

```bash
aifabrix run miso-test --port 8083          # Custom port
aifabrix run miso-test --debug                  # Debug output
```

### Push Options

```bash
aifabrix push miso-test --registry myacr.azurecr.io --tag v1.0.0
aifabrix push miso-test --registry myacr.azurecr.io --tag "v1.0.0,latest,stable"
```

### Deploy Options

```bash
aifabrix deploy miso-test --controller <url> --environment dev
aifabrix deploy miso-test --controller <url> --environment dev --no-poll
```

### Login Methods

```bash
# Device code flow
aifabrix login --method device --environment dev

# Credentials (reads from secrets.local.yaml)
aifabrix login --method credentials --app miso-test --environment dev

# Explicit credentials
aifabrix login --method credentials --app miso-test --client-id $CLIENT_ID --client-secret $CLIENT_SECRET --environment dev
```

### Configuration

Set overrides in `~/.aifabrix/config.yaml`:

```yaml
aifabrix-home: "/custom/path"
aifabrix-secrets: "/path/to/secrets.yaml"
```

---

## Troubleshooting

- **"Docker not running"** → Start Docker Desktop
- **"Not logged in"** → Run `aifabrix login` first
- **"Port already in use"** → Use `--port` flag or change `build.localPort` in `variables.yaml` (default: 8083)
- **"Authentication failed"** → Run `aifabrix login` again
- **"Build fails"** → Check Docker is running and `aifabrix-secrets` in `config.yaml` is configured correctly
- **"Can't connect"** → Verify infrastructure is running

**Regenerate files:**

```bash
aifabrix resolve miso-test --force
aifabrix json miso-test
aifabrix genkey miso-test
```

---

## Prerequisites

- `@aifabrix/builder` installed globally
- Docker Desktop running
- Azure CLI installed (for push command)
- Authenticated with controller (for deploy command)
- Authentication/RBAC configured

---

**Application**: miso-test | **Port**: 8083 | **Registry**: myacr.azurecr.io | **Image**: aifabrix/miso-test:latest
