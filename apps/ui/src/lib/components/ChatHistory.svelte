<script lang="ts">
	import type { ChatSession } from '$lib/types/chat';

	let {
		sessions,
		currentSessionId,
		onSelectSession,
		onDeleteSession,
		onClose
	}: {
		sessions: ChatSession[];
		currentSessionId: string;
		onSelectSession: (id: string) => void;
		onDeleteSession: (id: string) => void;
		onClose: () => void;
	} = $props();

	function formatDate(date: Date): string {
		const now = new Date();
		const sessionDate = new Date(date);
		const diffTime = Math.abs(now.getTime() - sessionDate.getTime());
		const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

		if (diffDays === 0) {
			return 'Today';
		} else if (diffDays === 1) {
			return 'Yesterday';
		} else if (diffDays < 7) {
			return `${diffDays} days ago`;
		} else {
			return sessionDate.toLocaleDateString();
		}
	}
</script>

<div class="history-overlay" onclick={onClose} role="button" tabindex="0" onkeydown={(e) => e.key === 'Escape' && onClose()}></div>
<div class="history-panel">
	<div class="history-header">
		<h3>Chat History</h3>
		<button class="close-btn" onclick={onClose} aria-label="Close history">
			<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
			</svg>
		</button>
	</div>

	<div class="history-list">
		{#if sessions.length === 0}
			<div class="empty-history">
				<p>No chat history yet</p>
			</div>
		{:else}
			{#each sessions as session (session.id)}
				<div
					class="history-item"
					class:active={session.id === currentSessionId}
					role="button"
					tabindex="0"
					onclick={() => onSelectSession(session.id)}
					onkeydown={(e) => {
						if (e.key === 'Enter' || e.key === ' ') {
							e.preventDefault();
							onSelectSession(session.id);
						}
					}}
					aria-label={`Select chat: ${session.title}`}
				>
					<div class="session-content">
						<div class="session-title">{session.title}</div>
						<div class="session-date">{formatDate(session.timestamp)}</div>
					</div>
					<button
						class="delete-btn"
						aria-label="Delete chat"
						onclick={(e) => {
							e.stopPropagation();
							onDeleteSession(session.id);
						}}
					>
						<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
							/>
						</svg>
					</button>
				</div>
			{/each}
		{/if}
	</div>
</div>

<style>
	.history-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.3);
		z-index: 999;
		animation: fadeIn 0.2s ease-out;
	}

	.history-panel {
		position: absolute;
		top: 100%;
		right: 0;
		width: 100%;
		max-width: 400px;
		max-height: 500px;
		background: white;
		border-radius: 12px;
		box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
		z-index: 1000;
		margin-top: 0.5rem;
		display: flex;
		flex-direction: column;
		animation: slideDown 0.3s ease-out;
	}

	.history-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1rem 1.5rem;
		border-bottom: 1px solid #e5e7eb;
	}

	.history-header h3 {
		margin: 0;
		font-size: 1.125rem;
		font-weight: 600;
		color: #374151;
	}

	.close-btn {
		background: none;
		border: none;
		color: #6b7280;
		cursor: pointer;
		padding: 0.25rem;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 6px;
		transition: all 0.2s;
	}

	.close-btn:hover {
		background: #f3f4f6;
		color: #374151;
	}

	.history-list {
		overflow-y: auto;
		flex: 1;
	}

	.empty-history {
		padding: 3rem 1.5rem;
		text-align: center;
		color: #9ca3af;
	}

	.history-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1rem 1.5rem;
		cursor: pointer;
		transition: all 0.2s;
		border-bottom: 1px solid #f3f4f6;
	}

	.history-item:hover {
		background: #f9fafb;
	}

	.history-item:focus {
		outline: 2px solid #667eea;
		outline-offset: -2px;
		background: #f9fafb;
	}

	.history-item.active {
		background: #ede9fe;
		border-left: 3px solid #667eea;
	}

	.session-content {
		flex: 1;
		min-width: 0;
	}

	.session-title {
		font-weight: 500;
		color: #374151;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		margin-bottom: 0.25rem;
	}

	.session-date {
		font-size: 0.75rem;
		color: #9ca3af;
	}

	.delete-btn {
		background: none;
		border: none;
		color: #9ca3af;
		cursor: pointer;
		padding: 0.5rem;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 6px;
		transition: all 0.2s;
		opacity: 0;
	}

	.history-item:hover .delete-btn {
		opacity: 1;
	}

	.delete-btn:hover {
		background: #fee2e2;
		color: #dc2626;
	}

	@keyframes fadeIn {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}

	@keyframes slideDown {
		from {
			opacity: 0;
			transform: translateY(-10px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}
</style>
