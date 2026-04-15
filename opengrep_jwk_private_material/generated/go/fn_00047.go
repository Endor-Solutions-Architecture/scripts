package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"oct","kid":"missing-k","alg":"HS256"}
func main() {
  m := map[string]any{"kty":"oct","kid":"missing-k","alg":"HS256"}
  _ = jwt.MapClaims{"jwk": m}
}
