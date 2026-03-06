<script lang="ts">
	import { getBackendUrl } from '$lib/config';

	let {
		conversationId,
		onPolicyChange,
		onConversationReset
	}: {
		conversationId: string;
		onPolicyChange?: () => void;
		onConversationReset?: () => void;
	} = $props();

	let hasPolicyState = $state(false);
	let policyLength = $state<number | null>(null);
	let isUploading = $state(false);
	let showMessage = $state(false);
	let messageText = $state('');
	let messageType = $state<'success' | 'error'>('success');
	let showConfirmDialog = $state(false);
	let pendingFileContent = $state<string | null>(null);
	let providerMode = $state<string | null>(null);
	let requiresRestart = $state(false);

	let fileInputRef: HTMLInputElement;

	// Check policy status and provider info on mount
	$effect(() => {
		checkPolicyStatus();
		fetchProviderInfo();
	});

	async function checkPolicyStatus() {
		try {
			const backendUrl = getBackendUrl();
			const response = await fetch(`${backendUrl}/policy/status`);
			if (response.ok) {
				const data = await response.json();
				hasPolicyState = data.has_policy;
				policyLength = data.policy_length;
			}
		} catch (error) {
			console.error('[PolicyUpload] Failed to check policy status:', error);
		}
	}

	async function fetchProviderInfo() {
		try {
			const backendUrl = getBackendUrl();
			const response = await fetch(`${backendUrl}/provider/info`);
			if (response.ok) {
				const data = await response.json();
				providerMode = data.provider_mode;
				requiresRestart = data.requires_restart_on_policy_update;
				console.log(`[PolicyUpload] Provider mode: ${providerMode}, requires restart: ${requiresRestart}`);
			}
		} catch (error) {
			console.error('[PolicyUpload] Failed to fetch provider info:', error);
		}
	}

	function handleUploadClick() {
		fileInputRef?.click();
	}

	async function handleFileSelected(event: Event) {
		const target = event.target as HTMLInputElement;
		const file = target.files?.[0];

		if (!file) return;

		// Validate file type
		if (!file.name.endsWith('.txt')) {
			displayMessage('Only .txt files are allowed', 'error');
			target.value = ''; // Reset input
			return;
		}

		// Validate file size (max 1MB)
		const maxSize = 1024 * 1024; // 1MB in bytes
		if (file.size > maxSize) {
			displayMessage('File size must be less than 1MB', 'error');
			target.value = ''; // Reset input
			return;
		}

		// Read file content
		try {
			const text = await file.text();

			// Check if confirmation is needed (Llama Stack mode)
			if (requiresRestart) {
				// Store file content and show confirmation dialog
				pendingFileContent = text;
				showConfirmDialog = true;
			} else {
				// MCP-Direct mode: upload immediately
				await uploadPolicy(text);
			}
		} catch (error) {
			console.error('[PolicyUpload] File read error:', error);
			displayMessage('Failed to read file', 'error');
		} finally {
			target.value = ''; // Reset input
		}
	}

	function handleConfirmUpload() {
		showConfirmDialog = false;
		if (pendingFileContent) {
			uploadPolicy(pendingFileContent, true);
			pendingFileContent = null;
		}
	}

	function handleCancelUpload() {
		showConfirmDialog = false;
		pendingFileContent = null;
	}

	async function uploadPolicy(policyText: string, clearConversation = false) {
		try {
			isUploading = true;

			// Upload to backend with conversation_id if clearing is needed
			const backendUrl = getBackendUrl();
			const requestBody: { policy_text: string; conversation_id?: string } = {
				policy_text: policyText
			};

			// Include conversation_id if we need to clear it
			if (clearConversation && conversationId) {
				requestBody.conversation_id = conversationId;
			}

			const response = await fetch(`${backendUrl}/policy/upload`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify(requestBody)
			});

			if (!response.ok) {
				const error = await response.json();
				throw new Error(error.detail || 'Upload failed');
			}

			const result = await response.json();
			hasPolicyState = true;
			policyLength = result.policy_length;
			displayMessage(result.message || 'Policy uploaded successfully', 'success');

			// If conversation restart was required, notify parent to clear UI
			if (result.requires_restart && clearConversation) {
				onConversationReset?.();
			}

			// Notify parent component
			onPolicyChange?.();
		} catch (error) {
			console.error('[PolicyUpload] Upload error:', error);
			displayMessage(
				error instanceof Error ? error.message : 'Failed to upload policy',
				'error'
			);
		} finally {
			isUploading = false;
		}
	}

	async function handleDeletePolicy() {
		// Build confirmation message based on provider mode
		let confirmMessage = 'Are you sure you want to remove the current policy?';
		if (requiresRestart) {
			confirmMessage =
				'Removing this policy will recreate the agent and delete your current conversation. Continue?';
		}

		// Confirm deletion
		if (!confirm(confirmMessage)) {
			return;
		}

		try {
			const backendUrl = getBackendUrl();
			const response = await fetch(`${backendUrl}/policy`, {
				method: 'DELETE'
			});

			if (!response.ok) {
				const error = await response.json();
				throw new Error(error.detail || 'Delete failed');
			}

			const result = await response.json();
			hasPolicyState = false;
			policyLength = null;
			displayMessage(result.message || 'Policy removed successfully', 'success');

			// If conversation restart was required, notify parent to clear UI
			if (result.requires_restart) {
				onConversationReset?.();
			}

			// Notify parent component
			onPolicyChange?.();
		} catch (error) {
			console.error('[PolicyUpload] Delete error:', error);
			displayMessage(
				error instanceof Error ? error.message : 'Failed to remove policy',
				'error'
			);
		}
	}

	function displayMessage(text: string, type: 'success' | 'error') {
		messageText = text;
		messageType = type;
		showMessage = true;

		// Auto-dismiss after 3 seconds
		setTimeout(() => {
			showMessage = false;
		}, 3000);
	}
</script>

<!-- Hidden file input -->
<input
	type="file"
	accept=".txt,text/plain"
	bind:this={fileInputRef}
	onchange={handleFileSelected}
	style="display: none;"
/>

{#if !hasPolicyState}
	<!-- Upload button when no policy is active -->
	<button
		class="icon-btn upload-btn"
		onclick={handleUploadClick}
		disabled={isUploading}
		title="Upload Data Governance Policy"
	>
		{#if isUploading}
			<svg
				width="20"
				height="20"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				class="spinner-icon"
			>
				<circle cx="12" cy="12" r="10" />
			</svg>
		{:else}
			<svg
				width="20"
				height="20"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
			>
				<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
				<polyline points="17 8 12 3 7 8" />
				<line x1="12" y1="3" x2="12" y2="15" />
			</svg>
		{/if}
	</button>
{:else}
	<!-- Policy status badge with delete button -->
	<div class="policy-status">
		<div class="policy-badge">
			<svg
				width="16"
				height="16"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
			>
				<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
				<polyline points="14 2 14 8 20 8" />
			</svg>
			<span class="policy-text">Policy ({policyLength?.toLocaleString()} chars)</span>
			<button class="delete-btn" onclick={handleDeletePolicy} title="Remove Policy">
				<svg
					width="14"
					height="14"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
				>
					<line x1="18" y1="6" x2="6" y2="18" />
					<line x1="6" y1="6" x2="18" y2="18" />
				</svg>
			</button>
		</div>
	</div>
{/if}

<!-- Message toast -->
{#if showMessage}
	<div class="message-toast" class:success={messageType === 'success'} class:error={messageType === 'error'}>
		{messageText}
	</div>
{/if}

<!-- Confirmation Dialog -->
{#if showConfirmDialog}
	<div class="dialog-overlay" onclick={handleCancelUpload}>
		<div class="dialog-content" onclick={(e) => e.stopPropagation()}>
			<div class="dialog-header">
				<svg
					width="48"
					height="48"
					viewBox="0 0 24 24"
					fill="none"
					stroke="#f59e0b"
					stroke-width="2"
				>
					<path
						d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"
					/>
					<line x1="12" y1="9" x2="12" y2="13" />
					<line x1="12" y1="17" x2="12.01" y2="17" />
				</svg>
				<h3>Confirm Policy Upload</h3>
			</div>
			<div class="dialog-body">
				<p>
					Uploading a governance policy will recreate the agent and <strong
						>delete your current conversation</strong
					>.
				</p>
				<p>This action cannot be undone. Do you want to continue?</p>
			</div>
			<div class="dialog-actions">
				<button class="dialog-btn cancel-btn" onclick={handleCancelUpload}>Cancel</button>
				<button class="dialog-btn confirm-btn" onclick={handleConfirmUpload}>
					Continue Upload
				</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.icon-btn {
		background: rgba(255, 255, 255, 0.2);
		border: none;
		color: white;
		width: 40px;
		height: 40px;
		border-radius: 8px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.2s;
	}

	.icon-btn:hover {
		background: rgba(255, 255, 255, 0.3);
		transform: translateY(-1px);
	}

	.icon-btn:active {
		transform: translateY(0);
	}

	.icon-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.icon-btn:disabled:hover {
		transform: none;
	}

	.spinner-icon {
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	.policy-status {
		display: flex;
		align-items: center;
	}

	.policy-badge {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		background: rgba(255, 255, 255, 0.2);
		padding: 0.5rem 0.75rem;
		border-radius: 8px;
		color: white;
		font-size: 0.875rem;
		font-weight: 500;
		transition: all 0.2s;
	}

	.policy-badge:hover {
		background: rgba(255, 255, 255, 0.25);
	}

	.policy-text {
		white-space: nowrap;
	}

	.delete-btn {
		background: rgba(255, 255, 255, 0.2);
		border: none;
		color: white;
		width: 24px;
		height: 24px;
		border-radius: 4px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.2s;
		padding: 0;
	}

	.delete-btn:hover {
		background: rgba(255, 100, 100, 0.4);
	}

	.message-toast {
		position: fixed;
		top: 5rem;
		right: 2rem;
		padding: 1rem 1.5rem;
		border-radius: 8px;
		color: white;
		font-weight: 500;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
		animation: slideIn 0.3s ease-out;
		z-index: 1000;
	}

	.message-toast.success {
		background: linear-gradient(135deg, #10b981 0%, #059669 100%);
	}

	.message-toast.error {
		background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
	}

	@keyframes slideIn {
		from {
			transform: translateX(100%);
			opacity: 0;
		}
		to {
			transform: translateX(0);
			opacity: 1;
		}
	}

	/* Confirmation Dialog Styles */
	.dialog-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 2000;
		animation: fadeIn 0.2s ease-out;
	}

	.dialog-content {
		background: white;
		border-radius: 12px;
		padding: 2rem;
		max-width: 480px;
		width: 90%;
		box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
		animation: scaleIn 0.2s ease-out;
	}

	.dialog-header {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
		margin-bottom: 1.5rem;
	}

	.dialog-header h3 {
		margin: 0;
		font-size: 1.5rem;
		font-weight: 600;
		color: #1f2937;
	}

	.dialog-body {
		margin-bottom: 2rem;
	}

	.dialog-body p {
		margin: 0 0 1rem 0;
		color: #4b5563;
		line-height: 1.6;
	}

	.dialog-body p:last-child {
		margin-bottom: 0;
	}

	.dialog-body strong {
		color: #dc2626;
		font-weight: 600;
	}

	.dialog-actions {
		display: flex;
		gap: 1rem;
		justify-content: flex-end;
	}

	.dialog-btn {
		padding: 0.75rem 1.5rem;
		border-radius: 8px;
		font-weight: 500;
		font-size: 0.95rem;
		cursor: pointer;
		transition: all 0.2s;
		border: none;
	}

	.cancel-btn {
		background: #e5e7eb;
		color: #374151;
	}

	.cancel-btn:hover {
		background: #d1d5db;
	}

	.confirm-btn {
		background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
		color: white;
	}

	.confirm-btn:hover {
		background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
		transform: translateY(-1px);
		box-shadow: 0 4px 12px rgba(220, 38, 38, 0.3);
	}

	@keyframes fadeIn {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}

	@keyframes scaleIn {
		from {
			transform: scale(0.9);
			opacity: 0;
		}
		to {
			transform: scale(1);
			opacity: 1;
		}
	}
</style>
