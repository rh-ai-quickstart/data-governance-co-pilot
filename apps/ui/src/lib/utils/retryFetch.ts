/**
 * Retry utility for fetch requests with exponential backoff
 *
 * Handles transient failures when connecting to copilot-backend:
 * - Network errors
 * - Connection resets
 * - Temporary unavailability (503)
 */

export interface RetryOptions {
	maxRetries?: number;
	initialDelayMs?: number;
	maxDelayMs?: number;
	backoffMultiplier?: number;
	retryableStatuses?: number[];
	onRetry?: (attempt: number, error: Error) => void;
}

const DEFAULT_OPTIONS: Required<RetryOptions> = {
	maxRetries: 3,
	initialDelayMs: 1000,
	maxDelayMs: 10000,
	backoffMultiplier: 2,
	retryableStatuses: [503, 502, 504], // Service Unavailable, Bad Gateway, Gateway Timeout
	onRetry: () => {}
};

/**
 * Sleep for specified milliseconds
 */
function sleep(ms: number): Promise<void> {
	return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Check if error is retryable
 */
function isRetryableError(error: unknown, retryableStatuses: number[]): boolean {
	// Network errors (fetch failed)
	if (error instanceof TypeError && error.message.includes('fetch')) {
		return true;
	}

	// HTTP errors with retryable status codes
	if (error instanceof Response) {
		return retryableStatuses.includes(error.status);
	}

	return false;
}

/**
 * Fetch with automatic retry and exponential backoff
 *
 * @param url - URL to fetch
 * @param init - Fetch options
 * @param options - Retry configuration
 * @returns Response object
 * @throws Error if all retries exhausted
 */
export async function retryFetch(
	url: string,
	init?: RequestInit,
	options?: RetryOptions
): Promise<Response> {
	const opts = { ...DEFAULT_OPTIONS, ...options };
	let lastError: Error | null = null;
	let delay = opts.initialDelayMs;

	for (let attempt = 0; attempt <= opts.maxRetries; attempt++) {
		try {
			const response = await fetch(url, init);

			// Check if response status is retryable (e.g., 503 Service Unavailable)
			if (!response.ok && opts.retryableStatuses.includes(response.status)) {
				if (attempt < opts.maxRetries) {
					console.warn(
						`[retryFetch] HTTP ${response.status} from ${url}, retrying in ${delay}ms (attempt ${attempt + 1}/${opts.maxRetries})`
					);
					opts.onRetry(attempt + 1, new Error(`HTTP ${response.status}`));
					await sleep(delay);
					delay = Math.min(delay * opts.backoffMultiplier, opts.maxDelayMs);
					continue;
				}
				// Last attempt - return the failed response
				return response;
			}

			// Success (or non-retryable error like 404, 400)
			return response;

		} catch (error) {
			// Network error or fetch failure
			lastError = error instanceof Error ? error : new Error(String(error));

			if (attempt < opts.maxRetries && isRetryableError(error, opts.retryableStatuses)) {
				console.warn(
					`[retryFetch] Network error: ${lastError.message}, retrying in ${delay}ms (attempt ${attempt + 1}/${opts.maxRetries})`
				);
				opts.onRetry(attempt + 1, lastError);
				await sleep(delay);
				delay = Math.min(delay * opts.backoffMultiplier, opts.maxDelayMs);
			} else {
				// Non-retryable error or max retries reached
				throw lastError;
			}
		}
	}

	// All retries exhausted
	throw lastError || new Error('Fetch failed after all retries');
}

/**
 * Fetch with retry specifically configured for SSE streaming
 *
 * SSE connections are long-lived, so we use different retry settings:
 * - More retries to cover pod startup/restart scenarios (up to ~30 seconds total)
 * - Exponential backoff to avoid hammering the backend
 * - Only retry connection establishment, not mid-stream failures
 *
 * Retry timeline with these settings:
 * - Attempt 1: immediate
 * - Attempt 2: +1s (total: 1s)
 * - Attempt 3: +2s (total: 3s)
 * - Attempt 4: +4s (total: 7s)
 * - Attempt 5: +5s (total: 12s)
 * - Attempt 6: +5s (total: 17s)
 * - Attempt 7: +5s (total: 22s)
 * - Attempt 8: +5s (total: 27s)
 * Total: ~27 seconds of retry attempts
 */
export async function retryFetchSSE(
	url: string,
	init?: RequestInit,
	onRetry?: (attempt: number, error: Error) => void
): Promise<Response> {
	return retryFetch(url, init, {
		maxRetries: 7,
		initialDelayMs: 1000,
		maxDelayMs: 5000,
		backoffMultiplier: 2,
		retryableStatuses: [503, 502, 504],
		onRetry
	});
}
