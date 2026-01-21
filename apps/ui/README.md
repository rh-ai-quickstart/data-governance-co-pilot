# Data Governance Copilot UI

Svelte-based chat interface for the Data Governance Copilot.

## Features

- **Modern chat interface** with message history
- **Real-time responses** from Nemotron LLM via copilot backend
- **Tool execution visibility** - shows which database analysis tools were used
- **Session management** - save and restore conversation history
- **Responsive design** - works on desktop and mobile

## Prerequisites

- Node.js 18+ and npm/pnpm
- **copilot-backend** service running (either locally or in OpenShift)

## Local Development

### 1. Install dependencies

```bash
npm install
# or
pnpm install
```

### 2. Configure backend URL

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and set the backend URL:

```bash
# For local development (backend running on port 8080)
VITE_COPILOT_BACKEND_URL=http://localhost:8080

# For OpenShift deployment (use the route URL)
# VITE_COPILOT_BACKEND_URL=https://copilot-backend-your-namespace.apps.example.com
```

### 3. Start development server

```bash
npm run dev
# or
pnpm dev
```

The UI will be available at http://localhost:5173

### 4. Connect to backend

If running the backend locally via port-forward:

```bash
# In a separate terminal
oc port-forward service/copilot-backend 8080:8080 -n your-namespace
```

Then the UI will connect to `http://localhost:8080/query`

## Building for Production

```bash
npm run build
# or
pnpm build
```

The built files will be in the `build/` directory, ready to be served by any static file server (nginx, Apache, etc.).

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_COPILOT_BACKEND_URL` | URL of the copilot-backend service | `http://localhost:8080` |

## Usage

### Asking Questions

Simply type your data governance questions in the chat input:

- "Show me the database schemas"
- "What are the most expensive queries?"
- "Analyze missing indexes in the users table"
- "Check database health"

### Understanding Responses

When the LLM uses database analysis tools, you'll see:

```
🔧 Tools Used:
  list_schemas ({})
  analyze_db_health ({})
```

This shows exactly which pg-airman-mcp tools were executed to answer your question.

### Session Management

- **New Chat** button - start a fresh conversation
- **History** button - view and restore previous conversations
- Conversations are automatically saved in browser localStorage

## Architecture

```
User Types Query
  ↓
Svelte UI (this app)
  ↓ POST /query
Copilot Backend (FastAPI)
  ↓ OpenAI API
Nemotron LLM
  ↓ Tool calls
pg-airman-mcp (MCP server)
  ↓ SQL queries
PostgreSQL Database
```

## Deployment to OpenShift

### Option 1: Static File Deployment

Build the app and serve via nginx:

```bash
# Build
npm run build

# Create nginx config
cat > nginx.conf <<EOF
server {
    listen 8080;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF

# Dockerfile
cat > Dockerfile <<EOF
FROM nginx:alpine
COPY build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
EOF

# Build and push image
oc new-build --binary --name=copilot-ui -n your-namespace
oc start-build copilot-ui --from-dir=. --follow -n your-namespace

# Deploy
oc new-app copilot-ui -n your-namespace
oc expose svc/copilot-ui -n your-namespace
```

### Option 2: SvelteKit Adapter

Install the Node adapter for SvelteKit:

```bash
npm install -D @sveltejs/adapter-node
```

Update `svelte.config.js`:

```javascript
import adapter from '@sveltejs/adapter-node';

export default {
  kit: {
    adapter: adapter()
  }
};
```

Build and deploy as a Node.js app.

## Troubleshooting

### "Failed to fetch" error

- Check that `VITE_COPILOT_BACKEND_URL` is set correctly in `.env`
- Verify the backend is running: `curl http://localhost:8080/health`
- Check browser console for CORS errors

### CORS errors

The copilot backend has CORS enabled for all origins in development. For production, update the backend's `CORSMiddleware` configuration in [service.py](../../packages/copilot/src/copilot/service.py:237).

### Backend connection refused

If using port-forward:
```bash
# Check if port-forward is still running
ps aux | grep "port-forward"

# Restart if needed
oc port-forward service/copilot-backend 8080:8080 -n your-namespace
```

### No response from backend

Check backend logs:
```bash
oc logs -f deployment/copilot-backend -n your-namespace
```

Common issues:
- MCP server not reachable (check pg-airman-mcp is running)
- LLM not reachable (check Nemotron service URL in backend config)
- Database credentials incorrect

## Development Tips

### Hot Module Replacement

SvelteKit supports HMR - changes to `.svelte` files will update instantly without refreshing the page.

### Testing with Mock Backend

For UI development without the backend, you can mock the `/query` endpoint:

```javascript
// In ChatInterface.svelte, replace the fetch with:
const data = {
  response: "This is a mock response for testing",
  tool_calls: [
    { tool: "list_schemas", arguments: {}, result: "..." }
  ]
};
```

### Component Structure

```
src/
├── lib/
│   ├── components/
│   │   ├── ChatInterface.svelte    # Main container
│   │   ├── MessageList.svelte      # Message display
│   │   ├── MessageBubble.svelte    # Individual message with tool calls
│   │   ├── ChatInput.svelte        # User input
│   │   ├── ChatHistory.svelte      # Session history sidebar
│   │   └── ThinkingIndicator.svelte # Loading state
│   └── types/
│       └── chat.ts                 # TypeScript interfaces
└── routes/
    ├── +layout.svelte              # Root layout
    └── +page.svelte                # Main page
```

## License

MIT
