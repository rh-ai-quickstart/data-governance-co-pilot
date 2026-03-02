export interface ToolCall {
	tool: string;
	arguments: Record<string, any>;
	result: string;
}

export interface Message {
	id: string;
	role: 'user' | 'assistant';
	content: string;
	timestamp: Date;
	toolCalls?: ToolCall[];
	progressState?: ProgressState; // Reasoning and progress for this response (UI only, not sent to backend)
}

export interface ChatSession {
	id: string;
	title: string;
	messages: Message[];
	timestamp: Date;
}

// Progress event types for SSE streaming
export type ProgressEvent =
	| { type: 'query_start'; query: string; timestamp: string }
	| { type: 'conversation_resumed'; conversation_id: string; message_count: number }
	| { type: 'conversation_started'; conversation_id: string }
	| { type: 'iteration_start'; iteration: number; max_iterations: number }
	| { type: 'llm_thinking'; content: string; iteration: number; llm_time: number }
	| { type: 'llm_content_delta'; content: string; iteration?: number }
	| { type: 'tool_call'; tool_name: string; arguments: Record<string, any>; iteration: number }
	| { type: 'tool_result'; tool_name: string; result: string; mcp_time: number; iteration: number }
	| { type: 'timing_summary'; total_time: number; llm_time: number; mcp_time: number; backend_overhead: number; iterations: number; tool_calls: number; context_tokens_used?: number; context_tokens_limit?: number; context_usage_pct?: number }
	| { type: 'final_response'; content: string; tool_calls: ToolCall[]; conversation_id?: string }
	| { type: 'error'; message: string; traceback?: string; total_time?: number; iterations?: number; tool_calls?: number };

// Progress state for tracking during streaming
export interface ProgressState {
	iterations: ProgressIteration[];
	currentIteration: number;
	thinkingContent: string[];
	toolCalls: Array<{ tool_name: string; arguments: Record<string, any>; result?: string }>;
	reasoningEnabled?: boolean; // Whether reasoning mode is enabled for this query
	timingSummary?: {
		total_time: number;
		llm_time: number;
		mcp_time: number;
		backend_overhead: number;
		iterations: number;
		tool_calls: number;
		context_tokens_used?: number;
		context_tokens_limit?: number;
		context_usage_pct?: number;
	};
}

export interface ProgressIteration {
	iteration: number;
	thinking?: string;
	toolCalls: Array<{ tool_name: string; arguments: Record<string, any>; result?: string; mcp_time?: number }>;
}
