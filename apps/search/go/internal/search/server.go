package search

import (
	"database/sql"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"strings"
	"time"
)

type SearchRequest struct {
	Query  string  `json:"query"`
	Labels []Label `json:"labels"`
}

type SearchResult struct {
	ID    int64   `json:"id"`
	Score float64 `json:"score"`
}

type SearchResponse struct {
	QueryTerms []string       `json:"query_terms"`
	Results    []SearchResult `json:"results"`
}

func NewHandler(db *sql.DB) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /search", func(w http.ResponseWriter, r *http.Request) {
		r.Body = http.MaxBytesReader(w, r.Body, 64*1024)
		defer r.Body.Close()

		var input SearchRequest
		decoder := json.NewDecoder(r.Body)
		if err := decoder.Decode(&input); err != nil {
			http.Error(w, "Invalid search request", http.StatusBadRequest)
			return
		}
		if err := decoder.Decode(new(any)); err != io.EOF {
			http.Error(w, "Expected a single JSON request", http.StatusBadRequest)
			return
		}

		query := strings.TrimSpace(input.Query)
		terms := searchTerms(query)
		response := SearchResponse{
			QueryTerms: terms,
			Results:    []SearchResult{},
		}

		if query != "" {
			candidates, err := fetchCandidates(r.Context(), db, terms, input.Labels)
			if err != nil {
				log.Printf("Search failed: %v", err)
				http.Error(w, "Search temporarily unavailable", http.StatusServiceUnavailable)
				return
			}

			for _, thread := range rankThreads(candidates, terms, input.Labels, time.Now()) {
				response.Results = append(response.Results, SearchResult{
					ID:    thread.ID,
					Score: thread.FinalSearchScore,
				})
			}
		}

		body, err := json.Marshal(response)
		if err != nil {
			log.Printf("Encode search response: %v", err)
			http.Error(w, "Unable to encode results", http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		if _, err := w.Write(body); err != nil {
			log.Printf("Write search response: %v", err)
		}
	})

	return mux
}
