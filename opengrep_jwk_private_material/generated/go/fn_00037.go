package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"9U9NOXgX4rYf","alg":"RS256","n":"BDUi7-yyCLgYR_h2FdiyvNGoAKR6hbYiihC07FC_EncrAzmP","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"9U9NOXgX4rYf","alg":"RS256","n":"BDUi7-yyCLgYR_h2FdiyvNGoAKR6hbYiihC07FC_EncrAzmP","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
