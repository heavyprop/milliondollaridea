package search

import (
	"regexp"
	"strings"
)

var tokenRE = regexp.MustCompile(`[a-z0-9+#.]+`)

var stopWords = map[string]bool{
	"a":      true,
	"an":     true,
	"and":    true,
	"are":    true,
	"as":     true,
	"at":     true,
	"be":     true,
	"best":   true,
	"but":    true,
	"by":     true,
	"for":    true,
	"from":   true,
	"has":    true,
	"have":   true,
	"how":    true,
	"i":      true,
	"if":     true,
	"in":     true,
	"is":     true,
	"it":     true,
	"of":     true,
	"on":     true,
	"or":     true,
	"should": true,
	"that":   true,
	"the":    true,
	"this":   true,
	"to":     true,
	"was":    true,
	"what":   true,
	"when":   true,
	"where":  true,
	"which":  true,
	"who":    true,
	"why":    true,
	"with":   true,
	"you":    true,
}

func searchTerms(query string) []string {
	terms := []string{}
	seen := make(map[string]bool)

	for _, term := range tokenRE.FindAllString(strings.ToLower(query), -1) {
		if len(term) < 2 || stopWords[term] || seen[term] {
			continue
		}
		terms = append(terms, term)
		seen[term] = true
	}
	return terms

}
