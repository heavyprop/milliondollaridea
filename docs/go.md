# Go documentation

The search service is in `apps/search/go/`. Start it there with `go run ./cmd/search` after setting `DATABASE_URL`. Ranking code is in `internal/search/scoring.go`; see [architecture](architecture.md) for the complete module map.

```
:= 
```
- means that it infers its type

## Slice
In Go, a slice is a view into an underlying array. It contains:
- a pointer to the array's data
- Length: how many elements the slice contains
- Capacity: how many elements it can hold from its starting position before needing a larger array
