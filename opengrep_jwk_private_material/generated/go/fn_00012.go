package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"D_tHvfb-t8oL","alg":"RS256","n":"NL0iaOpGUDXITqjvQY8V2TGyJFOjtIJonGJJ6Tjmlhn0ccUJ","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"D_tHvfb-t8oL","alg":"RS256","n":"NL0iaOpGUDXITqjvQY8V2TGyJFOjtIJonGJJ6Tjmlhn0ccUJ","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
