# Data Governance Copilot UI

A modern, professional chatbot interface built with SvelteKit for data governance assistance.

## Features

✅ **Streaming Responses** - Real-time SSE (Server-Sent Events) streaming for smooth chat experience  
✅ **Thinking Animation** - Animated indicator while the AI processes requests  
✅ **Chat History** - Dropdown to view and manage previous conversations  
✅ **Modern Design** - Professional gradient styling suitable for enterprise data governance  
✅ **Fully Responsive** - Clean, accessible interface with keyboard navigation  
✅ **No External Dependencies** - No Vercel SDK or cloud services required  

## Development

```bash
# Start the development server
pnpm dev

# Build for production  
pnpm build

# Run type checking
pnpm check
```

## Server Running

The dev server is currently running at:
- Local: http://localhost:5173/
- Network: http://10.195.154.106:5173/

## Integrating Your LLM

To connect to your actual LLM backend, modify `src/routes/api/chat/+server.ts`:

1. Replace the mock `generateMockResponse()` function
2. Connect to your LLM API (OpenAI, Anthropic, local model, etc.)
3. Stream responses using the existing SSE infrastructure

## Technologies

- SvelteKit 2.x with Svelte 5
- TypeScript
- Server-Sent Events for streaming
- Native CSS (no UI libraries)
