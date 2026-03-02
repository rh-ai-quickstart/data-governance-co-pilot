<script lang="ts">
	import type { Message } from '$lib/types/chat';
	import { marked } from 'marked';
	import hljs from 'highlight.js/lib/core';
	import sql from 'highlight.js/lib/languages/sql';
	import 'highlight.js/styles/github.css';
	import VegaLiteChart from './VegaLiteChart.svelte';

	// Register SQL language for syntax highlighting
	hljs.registerLanguage('sql', sql);

	let { message }: { message: Message } = $props();

	// State for extracted Vega-Lite specs
	let vegaSpecs = $state<Array<{ id: number; spec: string }>>([]);

	function formatTime(date: Date): string {
		return new Date(date).toLocaleTimeString('en-US', {
			hour: 'numeric',
			minute: '2-digit'
		});
	}

	// Configure marked with syntax highlighting
	marked.setOptions({
		highlight: function(code, lang) {
			if (lang && hljs.getLanguage(lang)) {
				try {
					return hljs.highlight(code, { language: lang }).value;
				} catch (err) {
					console.error('Highlight error:', err);
				}
			}
			return code;
		},
		breaks: true,
		gfm: true // GitHub Flavored Markdown (includes tables)
	});

	// Extract Vega-Lite specs from markdown and replace with placeholders
	function extractVegaSpecs(content: string): { markdown: string; specs: Array<{ id: number; spec: string }> } {
		if (!content) return { markdown: '', specs: [] };

		const specs: Array<{ id: number; spec: string }> = [];
		let specId = 0;

		// First, match explicit ```vega-lite code blocks
		const vegaLiteRegex = /```\s*vega-lite\s*\n([\s\S]*?)```/gi;

		// Second, match ```json blocks that contain Vega-Lite schema
		// This handles cases where LLM uses ```json instead of ```vega-lite
		const jsonVegaRegex = /```\s*json\s*\n([\s\S]*?vega\.github\.io\/schema\/vega-lite[\s\S]*?)```/gi;

		let processedMarkdown = content;

		// Process explicit vega-lite blocks first
		processedMarkdown = processedMarkdown.replace(vegaLiteRegex, (match, specContent) => {
			const trimmedSpec = specContent.trim();
			console.log(`[MessageBubble] Extracted Vega-Lite spec ${specId} (explicit):`, trimmedSpec.substring(0, 100));
			specs.push({
				id: specId,
				spec: trimmedSpec
			});
			const placeholder = `\n\n<!-- VEGA_CHART_${specId} -->\n\n`;
			specId++;
			return placeholder;
		});

		// Then process JSON blocks that contain Vega-Lite schema
		processedMarkdown = processedMarkdown.replace(jsonVegaRegex, (match, specContent) => {
			const trimmedSpec = specContent.trim();
			console.log(`[MessageBubble] Extracted Vega-Lite spec ${specId} (from JSON block):`, trimmedSpec.substring(0, 100));
			specs.push({
				id: specId,
				spec: trimmedSpec
			});
			const placeholder = `\n\n<!-- VEGA_CHART_${specId} -->\n\n`;
			specId++;
			return placeholder;
		});

		return { markdown: processedMarkdown, specs };
	}

	// Render markdown to HTML
	function renderMarkdown(content: string): string {
		if (!content) return '';
		try {
			const { markdown, specs } = extractVegaSpecs(content);
			vegaSpecs = specs; // Update state with extracted specs
			return marked.parse(markdown) as string;
		} catch (err) {
			console.error('Markdown parsing error:', err);
			return content; // Fallback to plain text
		}
	}

	// Debug logging
	$effect(() => {
		console.log('[MessageBubble] Rendering message:', {
			role: message.role,
			contentLength: message.content?.length || 0,
			content: message.content,
			toolCallsCount: message.toolCalls?.length || 0,
			vegaSpecsCount: vegaSpecs.length
		});
	});
</script>

<div class="message-wrapper" class:user={message.role === 'user'}>
	<div class="message-bubble" class:user={message.role === 'user'}>
		{#if message.role === 'assistant'}
			<div class="avatar assistant-avatar">
				<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
					/>
				</svg>
			</div>
		{/if}
		<div class="message-content">
			<div class="message-text">{@html renderMarkdown(message.content)}</div>

			<!-- Render extracted Vega-Lite charts -->
			{#each vegaSpecs as vegaSpec (vegaSpec.id)}
				<VegaLiteChart spec={vegaSpec.spec} />
			{/each}

			{#if message.toolCalls && message.toolCalls.length > 0}
				<div class="tool-calls">
					<div class="tool-calls-header">🔧 Tools Used:</div>
					{#each message.toolCalls as toolCall}
						<div class="tool-call">
							<span class="tool-name">{toolCall.tool}</span>
							{#if Object.keys(toolCall.arguments).length > 0}
								<span class="tool-args">({JSON.stringify(toolCall.arguments)})</span>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
			<div class="message-time">{formatTime(message.timestamp)}</div>
		</div>
		{#if message.role === 'user'}
			<div class="avatar user-avatar">
				<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
					/>
				</svg>
			</div>
		{/if}
	</div>
</div>

<style>
	.message-wrapper {
		display: flex;
		margin-bottom: 1.5rem;
		animation: slideIn 0.3s ease-out;
	}

	.message-wrapper.user {
		justify-content: flex-end;
	}

	.message-bubble {
		display: flex;
		gap: 0.75rem;
		max-width: 80%;
		align-items: flex-start;
	}

	.message-bubble.user {
		flex-direction: row-reverse;
	}

	.avatar {
		width: 36px;
		height: 36px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}

	.assistant-avatar {
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		color: white;
	}

	.user-avatar {
		background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
		color: white;
	}

	.message-content {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.message-text {
		background: white;
		padding: 0.875rem 1.125rem;
		border-radius: 16px;
		box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
		line-height: 1.5;
		word-wrap: break-word;
	}

	/* Markdown styling */
	.message-text :global(p) {
		margin: 0.5rem 0;
	}

	.message-text :global(p:first-child) {
		margin-top: 0;
	}

	.message-text :global(p:last-child) {
		margin-bottom: 0;
	}

	/* Table styling */
	.message-text :global(table) {
		border-collapse: collapse;
		width: 100%;
		margin: 1rem 0;
		font-size: 0.875rem;
		background: white;
		border-radius: 8px;
		overflow: hidden;
	}

	.message-text :global(th) {
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		color: white;
		font-weight: 600;
		padding: 0.75rem;
		text-align: left;
		border: 1px solid #e5e7eb;
	}

	.message-text :global(td) {
		padding: 0.625rem 0.75rem;
		border: 1px solid #e5e7eb;
		color: #374151;
	}

	.message-text :global(tr:nth-child(even)) {
		background-color: #f9fafb;
	}

	.message-text :global(tr:hover) {
		background-color: #f3f4f6;
	}

	/* Code block styling */
	.message-text :global(pre) {
		background: #f6f8fa;
		border: 1px solid #e5e7eb;
		border-radius: 8px;
		padding: 1rem;
		overflow-x: visible;
		margin: 1rem 0;
		font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
		font-size: 0.875rem;
		line-height: 1.5;
	}

	.message-text :global(code) {
		background: #f6f8fa;
		padding: 0.125rem 0.375rem;
		border-radius: 4px;
		font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
		font-size: 0.875rem;
		color: #e83e8c;
	}

	.message-text :global(pre code) {
		background: transparent;
		padding: 0;
		color: inherit;
	}

	/* List styling */
	.message-text :global(ul),
	.message-text :global(ol) {
		margin: 0.5rem 0;
		padding-left: 1.5rem;
	}

	.message-text :global(li) {
		margin: 0.25rem 0;
	}

	/* Heading styling */
	.message-text :global(h1),
	.message-text :global(h2),
	.message-text :global(h3),
	.message-text :global(h4) {
		margin: 1rem 0 0.5rem 0;
		font-weight: 600;
		color: #374151;
	}

	.message-text :global(h1) { font-size: 1.5rem; }
	.message-text :global(h2) { font-size: 1.25rem; }
	.message-text :global(h3) { font-size: 1.125rem; }
	.message-text :global(h4) { font-size: 1rem; }

	/* Blockquote styling */
	.message-text :global(blockquote) {
		border-left: 4px solid #667eea;
		padding-left: 1rem;
		margin: 1rem 0;
		color: #6b7280;
		font-style: italic;
	}

	.user .message-text {
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		color: white;
	}

	.message-time {
		font-size: 0.75rem;
		color: #9ca3af;
		padding: 0 0.5rem;
	}

	.user .message-time {
		text-align: right;
	}

	.tool-calls {
		margin-top: 0.5rem;
		padding: 0.75rem;
		background: #f3f4f6;
		border-radius: 8px;
		font-size: 0.875rem;
	}

	.tool-calls-header {
		font-weight: 600;
		margin-bottom: 0.5rem;
		color: #6b7280;
	}

	.tool-call {
		padding: 0.25rem 0;
		color: #374151;
	}

	.tool-name {
		font-weight: 500;
		color: #667eea;
	}

	.tool-args {
		color: #9ca3af;
		font-size: 0.75rem;
		margin-left: 0.25rem;
		word-wrap: break-word;
		overflow-wrap: break-word;
	}

	@keyframes slideIn {
		from {
			opacity: 0;
			transform: translateY(10px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}
</style>
