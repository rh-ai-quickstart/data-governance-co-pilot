<script lang="ts">
	import { tick } from 'svelte';
	import { getBackendUrl } from '$lib/config';
	import { retryFetchSSE } from '$lib/utils/retryFetch';
	import MessageList from './MessageList.svelte';
	import ChatInput from './ChatInput.svelte';
	import ChatHistory from './ChatHistory.svelte';
	import PolicyUpload from './PolicyUpload.svelte';
	import type { Message, ChatSession, ProgressEvent, ProgressState } from '$lib/types/chat';
	import edbLogo from '$lib/assets/edb.png';
	import redhatLogo from '$lib/assets/redhatai.png';

	let messages = $state<Message[]>([]);
	let isStreaming = $state(false);
	let chatSessions = $state<ChatSession[]>([]);
	let currentSessionId = $state<string>(crypto.randomUUID());
	let showHistory = $state(false);
	let inputValue = $state('');
	let reasoningEnabled = $state<boolean>(true);
	let providerMode = $state<string | null>(null);
	let progressState = $state<ProgressState>({
		iterations: [],
		currentIteration: 0,
		thinkingContent: [],
		toolCalls: [],
		reasoningEnabled: true
	});

	// Auto-scroll state
	let messagesContainer: HTMLElement;
	let isUserScrolledUp = $state(false);
	let isAutoScrolling = false;

	// Load reasoning preference from localStorage on mount
	$effect(() => {
		const saved = localStorage.getItem('reasoningEnabled');
		if (saved !== null) {
			reasoningEnabled = JSON.parse(saved);
		}
	});

	// Fetch provider info on mount
	$effect(() => {
		fetchProviderInfo();
	});

	async function fetchProviderInfo() {
		try {
			const backendUrl = getBackendUrl();
			const response = await retryFetchSSE(
				`${backendUrl}/provider/info`,
				undefined,
				(attempt, error) => {
					console.warn(`[ChatInterface] Provider info retry ${attempt}/7: ${error.message}`);
				}
			);
			if (response.ok) {
				const data = await response.json();
				providerMode = data.provider_mode;
				console.log(`[ChatInterface] Provider mode: ${providerMode}`);
			}
		} catch (error) {
			console.error('[ChatInterface] Failed to fetch provider info after retries:', error);
		}
	}

	function toggleReasoning() {
		reasoningEnabled = !reasoningEnabled;
		localStorage.setItem('reasoningEnabled', JSON.stringify(reasoningEnabled));
	}

	// Check if user is scrolled to bottom
	function isScrolledToBottom(): boolean {
		if (!messagesContainer) return true;
		const threshold = 100; // pixels from bottom
		const { scrollHeight, scrollTop, clientHeight } = messagesContainer;
		return scrollHeight - scrollTop - clientHeight < threshold;
	}

	// Scroll to bottom instantly
	async function scrollToBottom() {
		if (!messagesContainer) return;
		await tick();

		// Set flag to ignore scroll events we trigger
		isAutoScrolling = true;
		messagesContainer.scrollTop = messagesContainer.scrollHeight;

		// Clear flag after a short delay to allow for scroll event processing
		setTimeout(() => {
			isAutoScrolling = false;
		}, 100);
	}

	// Track user manual scrolling
	$effect(() => {
		if (!messagesContainer) return;

		const handleScroll = () => {
			// Ignore scroll events from our auto-scroll
			if (isAutoScrolling) {
				return;
			}

			const atBottom = isScrolledToBottom();

			// User manually scrolled - update state based on position
			// If user scrolls back to bottom, resume auto-scrolling
			isUserScrolledUp = !atBottom;
		};

		messagesContainer.addEventListener('scroll', handleScroll, { passive: true });
		return () => messagesContainer.removeEventListener('scroll', handleScroll);
	});

	// Auto-scroll when content changes
	$effect(() => {
		// Create reactive dependencies
		messages.length;
		progressState.iterations.length;

		// Track thinking content size to trigger scroll when reasoning streams in
		const thinkingSize = progressState.iterations.reduce(
			(sum, iter) => sum + (iter.thinking?.length || 0),
			0
		);

		isStreaming;

		if (!isUserScrolledUp) {
			scrollToBottom();
		}
	});

	async function handleSendMessage(content: string) {
		// Log the call stack to identify where this is being called from
		console.log('[ChatInterface] handleSendMessage called from:', new Error().stack);

		// Prevent duplicate submissions while a request is in progress
		if (isStreaming) {
			console.log('[ChatInterface] REJECTED - Ignoring duplicate submission - already processing a query');
			console.log('[ChatInterface] Current isStreaming state:', isStreaming);
			return;
		}

		console.log('[ChatInterface] ACCEPTED - Starting handleSendMessage with query:', content);

		const userMessage: Message = {
			id: crypto.randomUUID(),
			role: 'user',
			content,
			timestamp: new Date()
		};

		messages = [...messages, userMessage];
		console.log('[ChatInterface] Added user message, messages count:', messages.length);

		// Create assistant message placeholder (will be updated with final response)
		const assistantMessage: Message = {
			id: crypto.randomUUID(),
			role: 'assistant',
			content: '',
			timestamp: new Date(),
			toolCalls: []
		};

		messages = [...messages, assistantMessage];
		isStreaming = true;

		// Reset progress state
		progressState = {
			iterations: [],
			currentIteration: 0,
			thinkingContent: [],
			toolCalls: [],
			reasoningEnabled: reasoningEnabled
		};

		console.log('[ChatInterface] Added empty assistant message, isStreaming=true');

		try {
			// Get backend URL from environment variable or use default
			const backendUrl = getBackendUrl();
			console.log('[ChatInterface] Backend URL:', backendUrl);

			const requestBody = {
				query: content,
				conversation_id: currentSessionId,
				enable_reasoning: reasoningEnabled
			};
			console.log('[ChatInterface] Starting SSE stream with body:', requestBody);

			// Use fetch with automatic retry for SSE connection
			const response = await retryFetchSSE(
				`${backendUrl}/query/stream`,
				{
					method: 'POST',
					headers: {
						'Content-Type': 'application/json',
						'Accept': 'text/event-stream'
					},
					body: JSON.stringify(requestBody)
				},
				(attempt, error) => {
					console.warn(`[ChatInterface] Retry attempt ${attempt}/7: ${error.message}`);
					// Update assistant message to show retry status
					const retryMessage = messages[messages.length - 1];
					if (retryMessage && retryMessage.role === 'assistant') {
						retryMessage.content = `Connecting to backend... (attempt ${attempt}/7)`;
						messages = [...messages]; // Trigger reactivity
					}
				}
			);

			if (!response.ok) {
				console.error('[ChatInterface] Response not OK:', response.status, response.statusText);
				throw new Error(`HTTP error! status: ${response.status}`);
			}

			if (!response.body) {
				throw new Error('Response body is null');
			}

			// Read the stream
			const reader = response.body.getReader();
			const decoder = new TextDecoder();
			let buffer = '';

			while (true) {
				const { done, value } = await reader.read();

				// Decode chunk and add to buffer (even if done, to process final chunk)
				if (value) {
					buffer += decoder.decode(value, { stream: true });
				}

				// Process complete SSE messages (format: "data: {json}\n\n")
				const lines = buffer.split('\n\n');
				buffer = lines.pop() || ''; // Keep incomplete message in buffer

				for (const line of lines) {
					if (line.startsWith('data: ')) {
						const jsonData = line.slice(6); // Remove "data: " prefix
						try {
							const event: ProgressEvent = JSON.parse(jsonData);
							console.log('[ChatInterface] SSE event:', event.type);

							// Handle different event types
							switch (event.type) {
								case 'iteration_start':
									// Add new iteration to progress
									progressState.iterations.push({
										iteration: event.iteration,
										toolCalls: []
									});
									progressState.currentIteration = event.iteration;
									break;

								case 'llm_content_delta':
									// Stream LLM response content to UI as it arrives (real-time)
									// Backend has already filtered out thinking content
									const currentMessage = messages[messages.length - 1];
									if (currentMessage && currentMessage.role === 'assistant') {
										currentMessage.content += event.content;
										messages = [...messages]; // Trigger reactivity
									}
									break;

								case 'llm_thinking':
									// Add/append thinking content to current iteration (streamed in real-time)
									const thinkingIter = progressState.iterations.find(
										i => i.iteration === event.iteration
									);
									if (thinkingIter) {
										// Append thinking content as it streams in
										thinkingIter.thinking = (thinkingIter.thinking || '') + event.content;
										progressState = progressState; // Trigger reactivity
									}
									break;

								case 'tool_call':
									// Add tool call to current iteration
									const toolCallIter = progressState.iterations.find(
										i => i.iteration === event.iteration
									);
									if (toolCallIter) {
										toolCallIter.toolCalls.push({
											tool_name: event.tool_name,
											arguments: event.arguments
										});
									}
									break;

								case 'tool_result':
									// Update tool call with timing info (result omitted for data governance)
									const resultIter = progressState.iterations.find(
										i => i.iteration === event.iteration
									);
									if (resultIter) {
										const toolCall = resultIter.toolCalls.find(
											tc => tc.tool_name === event.tool_name && !tc.mcp_time
										);
										if (toolCall) {
											toolCall.mcp_time = event.mcp_time;
										}
									}
									break;

								case 'timing_summary':
									progressState.timingSummary = {
										total_time: event.total_time,
										llm_time: event.llm_time,
										mcp_time: event.mcp_time,
										backend_overhead: event.backend_overhead,
										iterations: event.iterations,
										tool_calls: event.tool_calls,
										context_tokens_used: event.context_tokens_used,
										context_tokens_limit: event.context_tokens_limit,
										context_usage_pct: event.context_usage_pct
									};
									break;

								case 'final_response':
									// Update assistant message with final response and attach progress state
									const finalMessage: Message = {
										...assistantMessage,
										content: event.content,
										toolCalls: event.tool_calls,
										progressState: JSON.parse(JSON.stringify(progressState)) // Deep copy
									};
									messages = [...messages.slice(0, -1), finalMessage];
									console.log('[ChatInterface] Final response received');

									// Reset progress state for next query
									progressState = {
										iterations: [],
										currentIteration: 0,
										thinkingContent: [],
										toolCalls: []
									};
									break;

								case 'error':
									console.error('[ChatInterface] Error event:', event.message);
									const errorMessage: Message = {
										...assistantMessage,
										content: `Sorry, there was an error: ${event.message}`
									};
									messages = [...messages.slice(0, -1), errorMessage];
									break;
							}

							// Trigger reactivity
							progressState = progressState;
						} catch (e) {
							console.error('[ChatInterface] Failed to parse SSE event:', e, jsonData);
						}
					}
				}

				// Exit loop after processing final chunk
				if (done) {
					console.log('[ChatInterface] Stream complete');
					break;
				}
			}
		} catch (error) {
			console.error('[ChatInterface] Error in handleSendMessage:', error);

			let errorText = 'Unknown error';
			if (error instanceof Error) {
				errorText = error.message;
			}

			const errorMessage: Message = {
				...assistantMessage,
				content: `Sorry, there was an error processing your request: ${errorText}`
			};
			messages = [...messages.slice(0, -1), errorMessage];
		} finally {
			isStreaming = false;
			console.log('[ChatInterface] Set isStreaming=false');
			saveCurrentSession();
			console.log('[ChatInterface] Session saved');
		}
	}

	function saveCurrentSession() {
		if (messages.length > 0) {
			const existingIndex = chatSessions.findIndex((s) => s.id === currentSessionId);
			const session: ChatSession = {
				id: currentSessionId,
				title: messages[0]?.content.slice(0, 50) || 'New Chat',
				messages: [...messages],
				timestamp: new Date()
			};

			if (existingIndex >= 0) {
				chatSessions[existingIndex] = session;
			} else {
				chatSessions = [session, ...chatSessions];
			}
		}
	}

	function loadSession(sessionId: string) {
		const session = chatSessions.find((s) => s.id === sessionId);
		if (session) {
			currentSessionId = session.id;
			messages = [...session.messages];
			showHistory = false;
		}
	}

	function startNewChat() {
		saveCurrentSession();
		currentSessionId = crypto.randomUUID();
		messages = [];
		showHistory = false;
	}

	function deleteSession(sessionId: string) {
		chatSessions = chatSessions.filter((s) => s.id !== sessionId);
		if (sessionId === currentSessionId) {
			startNewChat();
		}
	}

	function handleSuggestionClick(suggestion: string) {
		inputValue = suggestion;
	}

	function handlePolicyChange() {
		console.log('[ChatInterface] Policy updated - new conversations will use updated policy');
	}

	function handleConversationReset() {
		console.log('[ChatInterface] Resetting conversation due to policy update');

		// Clear current messages
		messages = [];
		progressState = {
			iterations: [],
			currentIteration: 0,
			thinkingContent: [],
			toolCalls: [],
			reasoningEnabled: reasoningEnabled
		};

		// Generate new session ID
		const newSessionId = crypto.randomUUID();
		console.log(`[ChatInterface] Created new session: ${newSessionId}`);
		currentSessionId = newSessionId;

		// Reset streaming state
		isStreaming = false;
		inputValue = '';

		// Scroll to top
		scrollToBottom();
	}
</script>

<div class="chat-container">
	<header class="chat-header">
		<div class="header-content">
			<div class="title-section">
				<h1>Data Governance Copilot</h1>
				<p class="subtitle">Powered by EDB's PG Airman MCP server on Red Hat OpenShift AI</p>
			</div>
			<div class="header-actions">
				<PolicyUpload
					conversationId={currentSessionId}
					onPolicyChange={handlePolicyChange}
					onConversationReset={handleConversationReset}
				/>
				<button
					class="icon-btn reasoning-btn"
					class:active={reasoningEnabled}
					onclick={toggleReasoning}
					disabled={providerMode === 'llama_stack'}
					title={providerMode === 'llama_stack'
						? 'Deploy using MCP direct to enable reasoning'
						: (reasoningEnabled ? 'Disable Reasoning (faster)' : 'Enable Reasoning (slower, more transparent)')}
				>
					<svg
						width="20"
						height="20"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
					>
						<path d="M12 3c.132 0 .263 0 .393 0a7.5 7.5 0 0 0 7.92 12.446a9 9 0 1 1 -8.313 -12.454z" />
						<path d="M17 4a2 2 0 0 0 2 2a2 2 0 0 0 -2 2a2 2 0 0 0 -2 -2a2 2 0 0 0 2 -2" />
						<path d="M19 11h2m-1 -1v2" />
					</svg>
				</button>
				<button class="icon-btn new-chat-btn" onclick={startNewChat} title="New Chat">
					<svg
						width="20"
						height="20"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
					>
						<path d="M12 5v14M5 12h14" />
					</svg>
				</button>
				<button
					class="icon-btn history-btn"
					onclick={() => (showHistory = !showHistory)}
					title="Chat History"
				>
					<svg
						width="20"
						height="20"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
					>
						<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
						<path d="M3 3v5h5" />
						<path d="M12 7v5l4 2" />
					</svg>
				</button>
			</div>
		</div>

		{#if showHistory}
			<ChatHistory
				sessions={chatSessions}
				currentSessionId={currentSessionId}
				onSelectSession={loadSession}
				onDeleteSession={deleteSession}
				onClose={() => (showHistory = false)}
			/>
		{/if}
	</header>

	<div bind:this={messagesContainer} class="messages-container" id="messages-container">
		<MessageList {messages} {isStreaming} onSuggestionClick={handleSuggestionClick} {progressState} />
	</div>

	<div class="input-container">
		<ChatInput onSend={handleSendMessage} disabled={isStreaming} bind:value={inputValue} providerMode={providerMode} />
		<div class="tech-stack">
			<a href="https://www.redhat.com/en/artificial-intelligence?sc_cid=RHCTN0250000435836&gclsrc=aw.ds&gad_source=1&gad_campaignid=20301154521&gbraid=0AAAAADsbVMRNHTLNr2UbKTCNzmUArtOjK&gclid=EAIaIQobChMIx72bsYaqkgMVdzYIBR1WbCjXEAAYASAAEgJrOvD_BwE" target="_blank" rel="noopener noreferrer" class="tech-badge">
				<img src={redhatLogo} alt="Red Hat Logo" width="168" height="38" />
			</a>
			<a href="https://www.enterprisedb.com/products/edb-postgres-ai" target="_blank" rel="noopener noreferrer" class="tech-badge">
				<img src={edbLogo} alt="EDB Logo" width="168" height="38" />
			</a>
		</div>
	</div>
</div>

<style>
	.chat-container {
		display: flex;
		flex-direction: column;
		height: 100vh;
		width: 60%;
		max-width: 1400px;
		margin: 0 auto;
		background: white;
		box-shadow: 0 0 50px rgba(0, 0, 0, 0.1);
	}

	.chat-header {
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		color: white;
		padding: 1.5rem 2rem;
		box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
		position: relative;
	}

	.header-content {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.title-section h1 {
		margin: 0;
		font-size: 1.75rem;
		font-weight: 600;
	}

	.subtitle {
		margin: 0.25rem 0 0 0;
		font-size: 0.875rem;
		opacity: 0.9;
	}

	.header-actions {
		display: flex;
		gap: 0.5rem;
	}

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
		opacity: 0.4;
		cursor: not-allowed;
	}

	.icon-btn:disabled:hover {
		background: rgba(255, 255, 255, 0.2);
		transform: none;
	}

	.reasoning-btn.active {
		background: rgba(255, 255, 255, 0.4);
		box-shadow: 0 0 10px rgba(255, 255, 255, 0.5);
	}

	.messages-container {
		flex: 1;
		overflow-y: auto;
		background: #f8f9fa;
	}

	.input-container {
		padding: 1.5rem 2rem;
		background: white;
		border-top: 1px solid #e1e4e8;
	}

	.tech-stack {
		display: flex;
		gap: 1rem;
		justify-content: center;
		margin-top: 0.75rem;
		padding-top: 0.75rem;
		border-top: 1px solid #f0f0f0;
	}

	.tech-badge {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		font-size: 0.75rem;
		color: #64748b;
		font-weight: 500;
		text-decoration: none;
		transition: all 0.2s;
	}

	.tech-badge:hover {
		color: #667eea;
		transform: translateY(-1px);
	}

	.tech-badge img {
		transition: all 0.2s;
	}

	.tech-badge:hover img {
		transform: scale(1.05);
	}
</style>
