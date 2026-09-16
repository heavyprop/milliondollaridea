package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"searchservice/internal/search"
)

func main() {
	if err := run(); err != nil {
		log.Fatal(err)
	}
}

func run() error {
	db, err := search.OpenDatabase(context.Background())
	if err != nil {
		return err
	}
	defer db.Close()

	address := os.Getenv("SEARCH_LISTEN_ADDR")
	if address == "" {
		address = "127.0.0.1:8080"
	}
	server := &http.Server{
		Addr:              address,
		Handler:           search.NewHandler(db),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      15 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	fmt.Printf("Search service listening on http://%s\n", address)
	return server.ListenAndServe()
}
