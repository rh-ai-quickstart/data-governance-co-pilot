<script lang="ts">
	import type { Message, ProgressState } from '$lib/types/chat';
	import MessageBubble from './MessageBubble.svelte';
	import ThinkingIndicator from './ThinkingIndicator.svelte';
	import ProgressBubble from './ProgressBubble.svelte';

	let { messages, isStreaming, onSuggestionClick, progressState }: {
		messages: Message[];
		isStreaming: boolean;
		onSuggestionClick?: (suggestion: string) => void;
		progressState: ProgressState;
	} = $props();
	let messagesEnd: HTMLDivElement;
	let lastMessageCount = $state(0);
	let isUserScrolledUp = $state(false);
	let lastScrollTime = 0;

	// Check if user is scrolled to bottom
	function isScrolledToBottom(): boolean {
		const container = document.getElementById('messages-container');
		if (!container) return true;

		const threshold = 100; // pixels from bottom to consider "at bottom"
		const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
		return distanceFromBottom < threshold;
	}

	// Track user manual scrolling
	$effect(() => {
		const container = document.getElementById('messages-container');
		if (!container) return;

		const handleScroll = () => {
			// Ignore scroll events we triggered (within 100ms)
			if (Date.now() - lastScrollTime < 100) return;

			isUserScrolledUp = !isScrolledToBottom();
		};

		container.addEventListener('scroll', handleScroll, { passive: true });
		return () => container.removeEventListener('scroll', handleScroll);
	});

	// Smooth auto-scroll that respects user's scroll position
	$effect(() => {
		const messageCountChanged = messages.length !== lastMessageCount;
		lastMessageCount = messages.length;

		// Only auto-scroll if:
		// 1. User hasn't manually scrolled up
		// 2. Either a new message was added OR streaming just ended
		if (messages.length > 0 && !isUserScrolledUp && (messageCountChanged || !isStreaming)) {
			lastScrollTime = Date.now();
			messagesEnd?.scrollIntoView({
				behavior: messageCountChanged ? 'smooth' : 'auto',
				block: 'end'
			});
		}
	});
</script>

<div class="message-list">
	{#if messages.length === 0}
		<div class="empty-state">
			<div class="empty-icon">
				<svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="1.5"
						d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
					/>
				</svg>
			</div>
			<h2>Welcome to Data Governance Copilot</h2>
			<p>Advanced data analysis integrated with your corporate data governance policy.</p>
			<div class="suggestions">
				<button
					class="suggestion-card"
					onclick={() => onSuggestionClick?.("Tell me about this database.")}
				>
					Tell me about this database?
				</button>
				<button
					class="suggestion-card"
					onclick={() => onSuggestionClick?.("Hi, I need to build a report on Customer Lifetime Value (LTV). I'm not sure what tables or views to use. Can you find the official source for me?")}
				>
					Hi, I need to build a report on Customer Lifetime Value (LTV). I'm not sure what tables or views to use. Can you find the official source for me?
				</button>
				<button
					class="suggestion-card"
					onclick={() => onSuggestionClick?.("Can you show me a sample of the top 10 customers by LTV?")}
				>
					Show me top top 10 customers by LTV?
				</button>
				<button
					class="suggestion-card"
					onclick={() => onSuggestionClick?.("Show me a count of customers by state.")}
				>
					Show me a count of customers by state.
				</button>
				<button
					class="suggestion-card"
					onclick={() => onSuggestionClick?.("Visualize this data using a simple bar chart with a vega-lite specification.")}
				>
					Visualize this data using a simple bar chart.
				</button>
			</div>
		</div>
	{:else}
		{#each messages as message (message.id)}
			{#if !(isStreaming && message === messages[messages.length - 1])}
				<!-- Show progress/reasoning bubble BEFORE the message content if this message has progress state -->
				{#if message.progressState && message.progressState.iterations.length > 0}
					<ProgressBubble progressState={message.progressState} isStreaming={false} />
				{/if}
				<MessageBubble {message} />
			{/if}
		{/each}

		<!-- During streaming: show progress bubble first, then message bubble -->
		{#if isStreaming}
			<!-- Progress bubble for currently streaming query: shows reasoning and tool execution details -->
			{#if progressState.iterations.length > 0}
				<ProgressBubble {progressState} {isStreaming} />
			{/if}

			<!-- Message bubble for streaming response (comes after progress bubble) -->
			{#if messages[messages.length - 1]?.content && messages[messages.length - 1].content.trim().length > 0}
				<MessageBubble message={messages[messages.length - 1]} />
			{:else}
				<div class="thinking-container">
					<ThinkingIndicator />
				</div>
			{/if}
		{/if}
	{/if}
	<div bind:this={messagesEnd}></div>
</div>

<style>
	.message-list {
		padding: 2rem;
		max-width: 800px;
		margin: 0 auto;
		width: 100%;
	}

	.empty-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		text-align: center;
		padding: 4rem 2rem;
		color: #6b7280;
	}

	.empty-icon {
		margin-bottom: 1.5rem;
		color: #9ca3af;
	}

	.empty-state h2 {
		font-size: 1.5rem;
		font-weight: 600;
		color: #374151;
		margin: 0 0 0.5rem 0;
	}

	.empty-state p {
		font-size: 1rem;
		margin: 0 0 2rem 0;
		max-width: 500px;
	}

	.suggestions {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		width: 100%;
		max-width: 500px;
	}

	.suggestion-card {
		background: white;
		padding: 1rem 1.5rem;
		border-radius: 12px;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
		cursor: pointer;
		transition: all 0.2s;
		border: 1px solid #e5e7eb;
		width: 100%;
		text-align: left;
		font-family: inherit;
		font-size: inherit;
		color: inherit;
		line-height: inherit;
	}

	.suggestion-card:hover {
		box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
		transform: translateY(-2px);
		border-color: #667eea;
	}

	.thinking-container {
		margin: 1rem 0;
	}
</style>
