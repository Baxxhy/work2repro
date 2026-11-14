//go:build http

package httpserver

import (
	"context"

	"github.com/EvilFreelancer/coddy-agent/internal/llm"
)

// cannedSummaryProvider keeps compaction tests independent of a live model API.
type cannedSummaryProvider struct{}

func (cannedSummaryProvider) Complete(context.Context, []llm.Message, []llm.ToolDefinition) (*llm.Response, error) {
	return &llm.Response{Content: "summary", StopReason: "end_turn"}, nil
}

func (cannedSummaryProvider) Stream(_ context.Context, _ []llm.Message, _ []llm.ToolDefinition, onChunk func(llm.StreamChunk)) (*llm.Response, error) {
	if onChunk != nil {
		onChunk(llm.StreamChunk{Content: "summary"})
	}
	return &llm.Response{Content: "summary", StopReason: "end_turn"}, nil
}
