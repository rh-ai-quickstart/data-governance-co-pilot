<script lang="ts">
	import { onMount } from 'svelte';
	import embed from 'vega-embed';

	let { spec }: { spec: string | object } = $props();

	let chartContainer: HTMLDivElement;
	let error = $state<string | null>(null);
	let isLoading = $state(true);

	onMount(async () => {
		try {
			// Parse spec if it's a string
			const parsedSpec = typeof spec === 'string' ? JSON.parse(spec) : spec;

			// Render the chart
			await embed(chartContainer, parsedSpec, {
				actions: {
					export: true,
					source: false,
					compiled: false,
					editor: false
				},
				theme: 'latimes' // Clean, professional theme
			});

			isLoading = false;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to render chart';
			isLoading = false;
		}
	});
</script>

{#if error}
	<div class="chart-error">
		<div class="error-header">
			<span class="error-icon">⚠️</span>
			<span class="error-title">Chart Rendering Failed</span>
		</div>
		<div class="error-message">{error}</div>
		<details class="spec-details">
			<summary>View Specification</summary>
			<pre>{typeof spec === 'string' ? spec : JSON.stringify(spec, null, 2)}</pre>
		</details>
	</div>
{:else}
	<div class="chart-wrapper">
		{#if isLoading}
			<div class="chart-loading">
				<div class="spinner"></div>
				<p>Rendering chart...</p>
			</div>
		{/if}
		<div bind:this={chartContainer} class="vega-chart"></div>
	</div>
{/if}

<style>
	.chart-wrapper {
		margin: 1rem 0;
		background: white;
		border: 1px solid #e5e7eb;
		border-radius: 8px;
		padding: 1rem;
		overflow-x: auto;
	}

	.vega-chart {
		width: 100%;
	}

	.chart-loading {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 2rem;
		color: #64748b;
	}

	.spinner {
		width: 32px;
		height: 32px;
		border: 3px solid #e2e8f0;
		border-top-color: #667eea;
		border-radius: 50%;
		animation: spin 1s linear infinite;
		margin-bottom: 1rem;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	.chart-loading p {
		margin: 0;
		font-size: 0.875rem;
	}

	.chart-error {
		margin: 1rem 0;
		background: #fef2f2;
		border: 1px solid #fecaca;
		border-radius: 8px;
		padding: 1rem;
	}

	.error-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}

	.error-icon {
		font-size: 1.25rem;
	}

	.error-title {
		font-weight: 600;
		color: #991b1b;
		font-size: 0.875rem;
	}

	.error-message {
		color: #b91c1c;
		font-size: 0.875rem;
		margin-bottom: 1rem;
	}

	.spec-details {
		margin-top: 0.5rem;
	}

	.spec-details summary {
		cursor: pointer;
		color: #475569;
		font-size: 0.875rem;
		font-weight: 500;
		padding: 0.5rem;
		background: white;
		border: 1px solid #e2e8f0;
		border-radius: 4px;
	}

	.spec-details summary:hover {
		background: #f8fafc;
	}

	.spec-details pre {
		margin-top: 0.5rem;
		background: white;
		border: 1px solid #e2e8f0;
		border-radius: 4px;
		padding: 0.75rem;
		overflow-x: auto;
		font-family: 'Monaco', 'Menlo', monospace;
		font-size: 0.75rem;
		color: #1e293b;
	}

	/* Vega embed container styling */
	:global(.vega-embed) {
		padding: 0 !important;
	}

	:global(.vega-embed .vega-actions) {
		right: 0 !important;
		top: 0 !important;
	}

	:global(.vega-embed .vega-actions a) {
		color: #667eea !important;
	}
</style>
