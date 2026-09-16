package main

import (
	"math"
	"sort"
	"strings"
	"time"
)

const (
	recencyHalfLifeDays = 14

	titleTextWeight       = 0.7
	descriptionTextWeight = 0.3
	textRelevanceWeight   = 0.65
	tagRelevanceWeight    = 0.35
	agreementBonusWeight  = 0.3

	likeEngagementWeight    = 0.55
	commentEngagementWeight = 0.30
	viewEngagementWeight    = 0.15

	finalRelevanceWeight = 0.7
	finalRecencyWeight   = 0.3

	minRelevanceScore   = 0.05
	minTagMatchScore    = 0.1
	allowAnyTextMatch   = true
	minPopularityFactor = 0.3
)

func rankThreads(
	candidateThreads []Thread,
	queryTerms []string,
	queryLabels []Label,
	now time.Time,
) []Thread {
	if len(candidateThreads) == 0 {
		return []Thread{}
	}

	threads := append([]Thread{}, candidateThreads...)

	maxLikes, maxComments, maxViews := 0, 0, 0

	for _, thread := range threads {
		maxLikes = max(maxLikes, thread.Likes)
		maxComments = max(maxComments, thread.CommentCount)
		maxViews = max(maxViews, thread.ViewCount)
	}

	engagementScores := make([]float64, 0, len(threads))

	for i := range threads {
		thread := &threads[i]

		thread.TitleMatchScore = textMatchScore(queryTerms, thread.Title)

		thread.DescriptionMatchScore = textMatchScore(queryTerms, thread.Description)

		thread.TextMatchScore = (titleTextWeight * thread.TitleMatchScore) +
			(descriptionTextWeight * thread.DescriptionMatchScore)

		thread.TagMatchScore = tagMatchScore(queryLabels, thread.TopicLabels)

		likeScore := normaliseCount(thread.Likes, maxLikes)
		commentScore := normaliseCount(thread.CommentCount, maxComments)
		viewScore := normaliseCount(thread.ViewCount, maxViews)

		thread.EngagementScore = (likeEngagementWeight * likeScore) +
			(commentEngagementWeight * commentScore) +
			(viewEngagementWeight * viewScore)

		thread.RecencyScore = recencyScore(*thread, now)

		baseRelevance := (textRelevanceWeight * thread.TextMatchScore) +
			(tagRelevanceWeight * thread.TagMatchScore)

		agreementBonus := thread.TextMatchScore * thread.TagMatchScore

		thread.RelevanceScore = baseRelevance * (1 + agreementBonusWeight*agreementBonus)

		engagementScores = append(engagementScores, thread.EngagementScore)
	}

	engagementBaseline := median(engagementScores)

	rankedThreads := []Thread{}

	for _, thread := range threads {
		thread.PassesSearchGate = thread.RelevanceScore >= minRelevanceScore ||
			thread.TagMatchScore >= minTagMatchScore ||
			(allowAnyTextMatch && thread.TextMatchScore > 0)

		if !thread.PassesSearchGate {
			continue
		}

		popularityFactor := 1 + (thread.EngagementScore - engagementBaseline)

		if popularityFactor < minPopularityFactor {
			popularityFactor = minPopularityFactor
		}

		thread.FinalSearchScore = (finalRelevanceWeight*thread.RelevanceScore +
			finalRecencyWeight*thread.RecencyScore) * popularityFactor

		rankedThreads = append(rankedThreads, thread)
	}

	sort.SliceStable(rankedThreads, func(i, j int) bool {
		return rankedThreads[i].FinalSearchScore > rankedThreads[j].FinalSearchScore
	})

	return rankedThreads
}

func textMatchScore(queryTerms []string, text string) float64 {
	if len(queryTerms) == 0 {
		return 0
	}

	textTerms := make(map[string]bool)

	for _, term := range tokenRE.FindAllString(strings.ToLower(text), -1) {
		textTerms[term] = true
	}

	matchedCount := 0

	for _, term := range queryTerms {
		if textTerms[term] {
			matchedCount++
		}
	}

	return float64(matchedCount) / float64(len(queryTerms))
}

func tagMatchScore(queryLabels, threadLabels []Label) float64 {
	queryScores := make(map[string]float64)
	threadScores := make(map[string]float64)

	for _, label := range queryLabels {
		queryScores[label.ID] = label.Score
	}

	for _, label := range threadLabels {
		threadScores[label.ID] = label.Score
	}

	rawScore := 0.0

	for id, queryScore := range queryScores {
		rawScore += queryScore * threadScores[id]
	}

	if rawScore > 1 {
		return 1
	}

	return rawScore
}

func normaliseCount(value, maxValue int) float64 {
	if maxValue == 0 {
		return 0
	}

	return math.Log1p(float64(value)) / math.Log1p(float64(maxValue))
}

func recencyScore(thread Thread, now time.Time) float64 {
	age := now.Sub(thread.CreatedAt)
	ageDays := age.Hours() / 24

	if ageDays < 0 {
		ageDays = 0
	}

	return math.Pow(0.5, ageDays/float64(recencyHalfLifeDays))
}

func median(values []float64) float64 {
	sort.Float64s(values)
	middle := len(values) / 2
	if len(values)%2 == 0 {
		return (values[middle-1] + values[middle]) / 2
	}
	return values[middle]
}
