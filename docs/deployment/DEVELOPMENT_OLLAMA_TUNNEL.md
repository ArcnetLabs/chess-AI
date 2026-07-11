# Development Ollama Tunnel

Use this setup only to let the deployed ChessRun backend call Ollama running on a developer machine during private testing. It is not the production inference architecture.

## Security Boundary

Do not port-forward `11434` from the router and do not use an unauthenticated quick tunnel. Create a named Cloudflare Tunnel, publish an HTTPS hostname, and protect it with a Cloudflare Access application that has a service-auth policy. The Render backend uses that service token on every Ollama request.

## Cloudflare Setup

1. In Cloudflare Zero Trust, create a named tunnel and add a public hostname such as `ollama-dev.example.com` that routes to `http://localhost:11434`.
2. Create a self-hosted Access application for that hostname with a service-auth policy only.
3. Create a service token and save its client ID and client secret. Cloudflare only displays the secret once.
4. On the Windows machine running Ollama, set `CLOUDFLARE_TUNNEL_TOKEN` and run:

```powershell
.\scripts\start_dev_ollama_tunnel.ps1
```

The script checks that Ollama is available locally before it starts `cloudflared`. Do not commit the tunnel token or Access credentials.

## Render Development Profile

Set these values in Render, not in a committed `.env` file:

```text
LLM_RUNTIME_MODE=development_tunnel
LLM_PRIMARY_PROVIDER=ollama
OLLAMA_BASE_URL=https://ollama-dev.example.com
OLLAMA_MODEL=phi3:mini
OLLAMA_REQUEST_HEADERS_JSON={"CF-Access-Client-Id":"<client-id>","CF-Access-Client-Secret":"<client-secret>"}
```

`development_tunnel` deliberately uses only Ollama. If the laptop or tunnel is unavailable, the API exposes that failure through the existing coach fallback instead of silently using a hosted provider.

## Production Switch

When the GPU-hosted vLLM endpoint is ready, remove the development-only values and set:

```text
LLM_RUNTIME_MODE=production
LLM_PRIMARY_PROVIDER=local
LLM_LOCAL_BASE_URL=https://llm.example.com/v1
LLM_LOCAL_MODEL=<production-8b-model>
LLM_FALLBACK_CHAIN=local,openrouter,openai
OLLAMA_REQUEST_HEADERS_JSON=
```

No API, frontend, prompt, or retrieval code changes are required for this switch.
