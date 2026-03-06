<script lang="ts">
	let {
		onSend,
		disabled,
		value = $bindable(''),
		providerMode = null
	}: {
		onSend: (message: string) => void;
		disabled: boolean;
		value?: string;
		providerMode?: string | null;
	} = $props();

	let input = $state(value);
	let textareaElement: HTMLTextAreaElement;

	// Sync input with external value prop
	$effect(() => {
		input = value;
	});

	// Sync external value when input changes
	$effect(() => {
		value = input;
	});

	function handleSubmit() {
		const message = input.trim();
		if (message && !disabled) {
			onSend(message);
			input = '';
			adjustTextareaHeight();
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			handleSubmit();
		}
	}

	function adjustTextareaHeight() {
		if (textareaElement) {
			textareaElement.style.height = 'auto';
			textareaElement.style.height = Math.min(textareaElement.scrollHeight, 200) + 'px';
		}
	}

	$effect(() => {
		//We may want to remove this check since if the user deletes the text area content,
		//it will evaluate to false and not resize the text area.
		if (input) {
			adjustTextareaHeight();
		}
	});
</script>

<div class="chat-input-container">
	<div class="input-wrapper">
		<textarea
			bind:this={textareaElement}
			bind:value={input}
			onkeydown={handleKeydown}
			placeholder="Type your natural language query here and press 'Enter'."
			{disabled}
			rows="1"
		></textarea>
		<button onclick={handleSubmit} disabled={!input.trim() || disabled} class="send-button" aria-label="Send message">
			<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
			</svg>
		</button>
	</div>
	<div class="input-footer">
		<div class="provider-mode">
			{#if providerMode === 'llama_stack'}
				Using OpenShift AI Llama Stack
			{:else if providerMode === 'mcp_direct'}
				Using MCP on OpenShift AI
			{/if}
		</div>
		<div class="input-hint">Press Enter to send, Shift+Enter for new line</div>
	</div>
</div>

<style>
	.chat-input-container {
		width: 100%;
	}

	.input-wrapper {
		display: flex;
		gap: 0.75rem;
		align-items: flex-end;
		background: white;
		border: 2px solid #e5e7eb;
		border-radius: 16px;
		padding: 0.75rem;
		transition: all 0.2s;
	}

	.input-wrapper:focus-within {
		border-color: #667eea;
		box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
	}

	textarea {
		flex: 1;
		border: none;
		outline: none;
		resize: none;
		font-family: inherit;
		font-size: 1rem;
		line-height: 1.5;
		min-height: 24px;
		max-height: 200px;
		overflow-y: auto;
		background: transparent;
	}

	textarea::placeholder {
		color: #9ca3af;
	}

	textarea:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.send-button {
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		color: white;
		border: none;
		width: 40px;
		height: 40px;
		border-radius: 12px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.2s;
		flex-shrink: 0;
	}

	.send-button:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
	}

	.send-button:active:not(:disabled) {
		transform: translateY(0);
	}

	.send-button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.input-footer {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-top: 0.5rem;
		gap: 1rem;
	}

	.provider-mode {
		font-size: 0.75rem;
		color: #9ca3af;
		text-align: left;
	}

	.input-hint {
		font-size: 0.75rem;
		color: #9ca3af;
		text-align: right;
	}
</style>
