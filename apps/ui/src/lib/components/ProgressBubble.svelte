<script lang="ts">
	import type { ProgressState } from '$lib/types/chat';

	let { progressState, isStreaming }: { progressState: ProgressState; isStreaming: boolean } = $props();

	let isCollapsed = $state(false);

	function toggleCollapse() {
		isCollapsed = !isCollapsed;
	}

	function formatTime(seconds: number | null | undefined): string {
		if (seconds === null || seconds === undefined) {
			return 'N/A';
		}
		if (seconds < 1) {
			return `${(seconds * 1000).toFixed(0)}ms`;
		}
		return `${seconds.toFixed(2)}s`;
	}
</script>

<div class="progress-bubble">
	<div class="progress-header" onclick={toggleCollapse}>
		<div class="header-left">
			<span class="header-icon">🧠</span>
			<span class="header-title">Reasoning & Progress</span>
			{#if isStreaming}
				<span class="streaming-badge">Thinking...</span>
			{/if}
		</div>
		<button class="collapse-btn" aria-label={isCollapsed ? 'Expand' : 'Collapse'}>
			{isCollapsed ? '▼' : '▲'}
		</button>
	</div>

	{#if !isCollapsed}
		<div class="progress-content">
			{#if progressState.timingSummary}
				<div class="timing-summary">
					<div class="timing-header">Performance Summary</div>
					<div class="timing-grid">
						<div class="timing-item">
							<span class="timing-label">Total Time:</span>
							<span class="timing-value">{formatTime(progressState.timingSummary.total_time)}</span>
						</div>
						{#if progressState.timingSummary.llm_time !== undefined && progressState.timingSummary.llm_time !== null}
							<div class="timing-item">
								<span class="timing-label">LLM Time:</span>
								<span class="timing-value">{formatTime(progressState.timingSummary.llm_time)}</span>
							</div>
						{/if}
						{#if progressState.timingSummary.mcp_time !== undefined && progressState.timingSummary.mcp_time !== null}
							<div class="timing-item">
								<span class="timing-label">MCP Time:</span>
								<span class="timing-value">{formatTime(progressState.timingSummary.mcp_time)}</span>
							</div>
						{/if}
						<div class="timing-item">
							<span class="timing-label">Steps:</span>
							<span class="timing-value">{progressState.timingSummary.iterations}</span>
						</div>
						<div class="timing-item">
							<span class="timing-label">Tool Calls:</span>
							<span class="timing-value">{progressState.timingSummary.tool_calls}</span>
						</div>
						{#if progressState.timingSummary.context_tokens_used !== undefined && progressState.timingSummary.context_tokens_used !== null && progressState.timingSummary.context_tokens_limit !== undefined && progressState.timingSummary.context_tokens_limit !== null && progressState.timingSummary.context_usage_pct !== undefined && progressState.timingSummary.context_usage_pct !== null}
							<div class="timing-item">
								<span class="timing-label">Context:</span>
								<span class="timing-value"
									class:warning={progressState.timingSummary.context_usage_pct > 80}
									class:critical={progressState.timingSummary.context_usage_pct > 95}
								>
									<!--{progressState.timingSummary.context_tokens_used.toLocaleString()} / {progressState.timingSummary.context_tokens_limit.toLocaleString()} -->
									{progressState.timingSummary.context_usage_pct.toFixed(1)}% used
								</span>
							</div>
						{/if}
					</div>
				</div>
			{/if}

			{#if progressState.iterations.length > 0}
				<div class="iterations-section">
					<div class="section-header">Steps ({progressState.iterations.length})</div>
					{#each progressState.iterations as iteration (iteration.iteration)}
						<div class="iteration">
							<div class="iteration-header">Step {iteration.iteration}</div>

							<!-- Always show LLM processing indicator at start of iteration -->
							{#if iteration.toolCalls.length > 0 && !iteration.thinking}
								<div class="llm-processing">
									<span class="processing-icon">🤖</span>
									<span class="processing-text">Processing with LLM</span>
								</div>
							{/if}

							{#if iteration.thinking}
								{#if progressState.reasoningEnabled === false}
									<div class="reasoning-disabled-message">
										<div class="reasoning-label">💭 Reasoning:</div>
										<div class="reasoning-text">
											Reasoning is turned off. Click the <strong>reasoning toggle button</strong> in the header to enable detailed thinking steps.
										</div>
									</div>
								{:else}
									<div class="thinking-block">
										<div class="thinking-label">💭 Thinking:</div>
										<div class="thinking-content">{iteration.thinking}</div>
									</div>
								{/if}
							{/if}

							{#if iteration.toolCalls.length > 0}
								<div class="tool-calls">
									{#each iteration.toolCalls as toolCall}
										<div class="tool-call">
											<div class="tool-call-header">
												<span class="tool-name">🔧 {toolCall.tool_name}</span>
												{#if toolCall.mcp_time}
													<span class="tool-time">{formatTime(toolCall.mcp_time)}</span>
												{/if}
											</div>
											<div class="tool-arguments">
												<strong>Arguments:</strong>
												<pre>{JSON.stringify(toolCall.arguments, null, 2)}</pre>
											</div>
										</div>
									{/each}
								</div>
							{/if}

							{#if !iteration.thinking && iteration.toolCalls.length === 0}
								<div class="llm-processing">
									<span class="processing-icon">🤖</span>
									<span class="processing-text">Processing with LLM</span>
								</div>
							{/if}
						</div>
					{/each}
				</div>
			{/if}

		</div>
	{/if}
</div>

<style>
	.progress-bubble {
		background: #f8f9ff;
		border: 1px solid #d1d9ff;
		border-radius: 12px;
		margin: 1rem 0;
		overflow: hidden;
	}

	.progress-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1rem 1.5rem;
		background: linear-gradient(135deg, #64748b 0%, #475569 100%);
		color: white;
		cursor: pointer;
		user-select: none;
	}

	.progress-header:hover {
		background: linear-gradient(135deg, #475569 0%, #334155 100%);
	}

	.header-left {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.header-icon {
		font-size: 1.25rem;
	}

	.header-title {
		font-weight: 600;
		font-size: 1rem;
	}

	.streaming-badge {
		background: rgba(255, 255, 255, 0.2);
		padding: 0.25rem 0.75rem;
		border-radius: 12px;
		font-size: 0.75rem;
		font-weight: 500;
		animation: pulse 2s ease-in-out infinite;
	}

	@keyframes pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.6;
		}
	}

	.collapse-btn {
		background: rgba(255, 255, 255, 0.2);
		border: none;
		color: white;
		width: 32px;
		height: 32px;
		border-radius: 6px;
		cursor: pointer;
		transition: all 0.2s;
		font-size: 0.875rem;
	}

	.collapse-btn:hover {
		background: rgba(255, 255, 255, 0.3);
	}

	.progress-content {
		padding: 1.5rem;
		/*max-height: 600px;*/
		overflow-y: visible;
	}

	.timing-summary {
		background: white;
		border: 1px solid #e1e8ed;
		border-radius: 8px;
		padding: 1rem;
		margin-bottom: 1.5rem;
	}

	.timing-header {
		font-weight: 600;
		color: #1a202c;
		margin-bottom: 0.75rem;
		font-size: 0.875rem;
	}

	.timing-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 0.55rem;
	}

	.timing-item {
		display: flex;
		justify-content: flex-start;
		align-items: flex-end;
		gap: 0.5rem;
	}

	.timing-label {
		font-size: 0.875rem;
		color: #64748b;
		text-align: right;
		min-width: 90px;
		justify-self: flex-end;
	}

	.timing-value {
		font-weight: 600;
		color: #667eea;
		font-size: 0.875rem;
		text-align: left;
		padding-left:5px;
	}

	.timing-value.warning {
		color: #f59e0b;
	}

	.timing-value.critical {
		color: #ef4444;
		font-weight: 700;
	}

	.iterations-section {
		margin-top: 1rem;
	}

	.section-header {
		font-weight: 600;
		color: #1a202c;
		margin-bottom: 0.75rem;
		font-size: 0.875rem;
	}

	.iteration {
		background: white;
		border: 1px solid #e1e8ed;
		border-radius: 8px;
		padding: 1rem;
		margin-bottom: 1rem;
	}

	.iteration-header {
		font-weight: 600;
		color: #667eea;
		margin-bottom: 0.75rem;
		font-size: 0.875rem;
	}

	.thinking-block {
		background: #fffbeb;
		border-left: 3px solid #f59e0b;
		padding: 0.75rem;
		margin-bottom: 1rem;
		border-radius: 4px;
	}

	.thinking-label {
		font-weight: 600;
		color: #92400e;
		margin-bottom: 0.5rem;
		font-size: 0.75rem;
	}

	.thinking-content {
		color: #78350f;
		font-size: 0.875rem;
		line-height: 1.5;
		white-space: pre-wrap;
	}

	.reasoning-disabled-message {
		background: #e0e7ff;
		border-left: 3px solid #667eea;
		padding: 0.75rem;
		margin-bottom: 1rem;
		border-radius: 4px;
	}

	.reasoning-label {
		font-weight: 600;
		color: #3730a3;
		margin-bottom: 0.5rem;
		font-size: 0.75rem;
	}

	.reasoning-text {
		color: #4338ca;
		font-size: 0.875rem;
		line-height: 1.5;
	}

	.reasoning-text strong {
		color: #667eea;
	}

	.llm-processing {
		background: #f0f9ff;
		border-left: 3px solid #0ea5e9;
		padding: 0.75rem;
		margin-bottom: 1rem;
		border-radius: 4px;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.processing-icon {
		font-size: 1rem;
	}

	.processing-text {
		color: #0c4a6e;
		font-size: 0.875rem;
		font-style: italic;
	}

	.tool-calls {
		margin-top: 0.75rem;
	}

	.tool-call {
		background: #f1f5f9;
		border: 1px solid #cbd5e1;
		border-radius: 6px;
		padding: 0.75rem;
		margin-bottom: 0.75rem;
	}

	.tool-call:last-child {
		margin-bottom: 0;
	}

	.tool-call-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.5rem;
	}

	.tool-name {
		font-weight: 600;
		color: #334155;
		font-size: 0.875rem;
	}

	.tool-time {
		font-size: 0.75rem;
		color: #64748b;
		background: white;
		padding: 0.125rem 0.5rem;
		border-radius: 4px;
	}

	.tool-arguments {
		margin-top: 0.5rem;
		font-size: 0.75rem;
	}

	.tool-arguments strong {
		color: #475569;
		display: block;
		margin-bottom: 0.25rem;
	}

	.tool-arguments pre {
		background: white;
		border: 1px solid #e2e8f0;
		border-radius: 4px;
		padding: 0.5rem;
		overflow-x: auto;
		white-space: pre-wrap;
		word-wrap: break-word;
		font-family: 'Courier New', monospace;
		font-size: 0.75rem;
		color: #1e293b;
		margin: 0;
	}

	.loading-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 2rem;
		color: #64748b;
	}

	.spinner {
		width: 40px;
		height: 40px;
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

	.loading-state p {
		margin: 0;
		font-size: 0.875rem;
	}
</style>
