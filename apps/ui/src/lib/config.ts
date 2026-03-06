/**
 * Runtime configuration loader
 *
 * Loads configuration from window.__RUNTIME_CONFIG__ which is injected
 * by the server at runtime (via /config.js).
 *
 * Falls back to build-time env vars for local development.
 */

interface RuntimeConfig {
	backendUrl: string;
}

// Type augmentation for window object
declare global {
	interface Window {
		__RUNTIME_CONFIG__?: RuntimeConfig;
	}
}

let config: RuntimeConfig | null = null;

/**
 * Get the runtime configuration.
 * Loads from window.__RUNTIME_CONFIG__ if available (production),
 * otherwise falls back to build-time env vars (local dev).
 */
export function getConfig(): RuntimeConfig {
	if (config) {
		return config;
	}

	// Try to load from runtime config (injected by server)
	if (typeof window !== 'undefined' && window.__RUNTIME_CONFIG__) {
		config = window.__RUNTIME_CONFIG__;
		console.log('[Config] Loaded runtime config:', config);
		return config;
	}

	// Fallback to build-time env vars for local development
	config = {
		backendUrl: import.meta.env.VITE_COPILOT_BACKEND_URL || 'http://localhost:8080'
	};

	console.log('[Config] Using build-time config (dev mode):', config);
	return config;
}

/**
 * Get the backend URL from runtime config
 */
export function getBackendUrl(): string {
	return getConfig().backendUrl;
}
