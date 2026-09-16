FROM golang:1.27.1 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /search ./cmd/search

FROM debian:bookworm-slim
COPY --from=build /search /usr/local/bin/search
USER 65532:65532
CMD ["search"]
