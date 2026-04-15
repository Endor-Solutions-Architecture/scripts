package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"eUHXwY0-WQur","alg":"RS256","n":"ieBLQztuy_b61MOdd3S1AoB2kMsQSrDMOVbtW3UZBLtSiLLI","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"eUHXwY0-WQur","alg":"RS256","n":"ieBLQztuy_b61MOdd3S1AoB2kMsQSrDMOVbtW3UZBLtSiLLI","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
