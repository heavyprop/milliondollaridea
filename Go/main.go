package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"time"
)

func main() {
	if err := run(); err != nil {
		log.Fatal(err)
	}
}

func run() error {
	db, err := openDatabase(context.Background())
	if err != nil {
		return err
	}
	defer db.Close()

	server := &http.Server{
		Addr:              "127.0.0.1:8080",
		Handler:           newSearchHandler(db),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      15 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	fmt.Println("Search service listening on http://127.0.0.1:8080")
	return server.ListenAndServe()
}
