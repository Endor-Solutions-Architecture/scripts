package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"bGEM9jlzF2RP","alg":"RS256","n":"4lrVi0BClLd7oO6RO5XKl_r2A02dPVz9xa3yzuv63K2dN-PY","e":"AQAB","d":"-UA8WMUsPcUxgKiRVfarrdBmkaoOXWU5VQT-tA0SuKjYVDXF8TKYy0UOG_xCg-bR"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"bGEM9jlzF2RP","alg":"RS256","n":"4lrVi0BClLd7oO6RO5XKl_r2A02dPVz9xa3yzuv63K2dN-PY","e":"AQAB","d":"-UA8WMUsPcUxgKiRVfarrdBmkaoOXWU5VQT-tA0SuKjYVDXF8TKYy0UOG_xCg-bR"}
  _ = jwt.MapClaims{"jwk": m}
}
