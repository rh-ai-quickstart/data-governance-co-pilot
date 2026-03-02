<script lang="ts">
	// Animated thinking indicator for when the AI is processing
</script>

<div class="thinking-wrapper">
	<div class="avatar">
		<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="2"
				d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
			/>
		</svg>
	</div>
	<div class="thinking-bubble">
		<div class="thinking-dots">
			<span class="dot"></span>
			<span class="dot"></span>
			<span class="dot"></span>
		</div>
	</div>
</div>

<style>
	.thinking-wrapper {
		display: flex;
		gap: 0.75rem;
		align-items: center;
		animation: slideIn 0.3s ease-out;
	}

	.avatar {
		width: 36px;
		height: 36px;
		border-radius: 50%;
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		color: white;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		animation: pulse 2s ease-in-out infinite;
	}

	.thinking-bubble {
		background: white;
		padding: 0.875rem 1.125rem;
		border-radius: 16px;
		box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
	}

	.thinking-dots {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}

	.dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: #667eea;
		animation: bounce 1.4s ease-in-out infinite;
	}

	.dot:nth-child(2) {
		animation-delay: 0.2s;
	}

	.dot:nth-child(3) {
		animation-delay: 0.4s;
	}

	@keyframes bounce {
		0%,
		80%,
		100% {
			transform: translateY(0);
			opacity: 0.5;
		}
		40% {
			transform: translateY(-8px);
			opacity: 1;
		}
	}

	@keyframes pulse {
		0%,
		100% {
			box-shadow: 0 0 0 0 rgba(102, 126, 234, 0.4);
		}
		50% {
			box-shadow: 0 0 0 8px rgba(102, 126, 234, 0);
		}
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
