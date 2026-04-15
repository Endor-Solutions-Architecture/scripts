package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"fScpSxhmwl4y","alg":"RS256","n":"awT1lrYcA6kwhbWHt4ibAHdegNR1Cu4X-TNQwkn5zDKlXMcs","e":"AQAB","d":"eCqqk0op"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"fScpSxhmwl4y","alg":"RS256","n":"awT1lrYcA6kwhbWHt4ibAHdegNR1Cu4X-TNQwkn5zDKlXMcs","e":"AQAB","d":"eCqqk0op"}
  _ = jwt.MapClaims{"jwk": m}
}
