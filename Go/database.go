package main

import (
	"context"
	"database/sql"
	_ "embed"
	"encoding/json"
	"fmt"
	"os"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
)

//go:embed searching.sql
var candidateSQL string

func openDatabase(ctx context.Context) (*sql.DB, error) {
	databaseURL := os.Getenv("DATABASE_URL")
	if databaseURL == "" {
		return nil, fmt.Errorf("DATABASE_URL is not set")
	}

	db, err := sql.Open("pgx", databaseURL)
	if err != nil {
		return nil, fmt.Errorf("open database: %w", err)
	}

	db.SetMaxOpenConns(10)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(30 * time.Minute)

	pingCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	if err := db.PingContext(pingCtx); err != nil {
		db.Close()
		return nil, fmt.Errorf("connect to database: %w", err)
	}

	return db, nil
}

func fetchCandidates(
	ctx context.Context,
	db *sql.DB,
	queryTerms []string,
	queryLabels []Label,
) ([]Thread, error) {
	if len(queryTerms) == 0 && len(queryLabels) == 0 {
		return []Thread{}, nil
	}

	if queryTerms == nil {
		queryTerms = []string{}
	}

	if queryLabels == nil {
		queryLabels = []Label{}
	}

	termsJSON, err := json.Marshal(queryTerms)
	if err != nil {
		return nil, fmt.Errorf("encode query terms: %w", err)
	}

	labelsJSON, err := json.Marshal(queryLabels)
	if err != nil {
		return nil, fmt.Errorf("encode query labels: %w", err)
	}

	queryCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	rows, err := db.QueryContext(
		queryCtx,
		candidateSQL,
		string(termsJSON),
		string(labelsJSON),
	)
	if err != nil {
		return nil, fmt.Errorf("fetch candidates: %w", err)
	}
	defer rows.Close()

	threads := []Thread{}

	for rows.Next() {
		var thread Thread
		var topicLabelsJSON []byte

		err := rows.Scan(
			&thread.ID,
			&thread.Title,
			&thread.Description,
			&topicLabelsJSON,
			&thread.CreatedAt,
			&thread.Likes,
			&thread.CommentCount,
			&thread.ViewCount,
		)
		if err != nil {
			return nil, fmt.Errorf("read candidate: %w", err)
		}

		if err := json.Unmarshal(topicLabelsJSON, &thread.TopicLabels); err != nil {
			return nil, fmt.Errorf("decode labels for thread %d: %w", thread.ID, err)
		}
		threads = append(threads, thread)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("read candidate rows: %w", err)
	}
	return threads, nil
}
