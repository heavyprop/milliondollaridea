package main

import "time"

type Label struct {
	ID    string  `json:"id"`
	Score float64 `json:"score"`
}

type Thread struct {
	ID          int64
	Title       string
	Description string
	TopicLabels []Label
	CreatedAt   time.Time

	Likes        int
	CommentCount int
	ViewCount    int

	TitleMatchScore       float64
	DescriptionMatchScore float64
	TextMatchScore        float64
	TagMatchScore         float64
	EngagementScore       float64
	RecencyScore          float64
	RelevanceScore        float64
	FinalSearchScore      float64
	PassesSearchGate      bool
}
