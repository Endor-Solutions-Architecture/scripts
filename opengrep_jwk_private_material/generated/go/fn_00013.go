package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"xeclHwaBfWUk","alg":"RS256","n":"agKgapd_TCnHukBfaczoqFNKVyZ8DF8N6GSmwS2M7olbfL3s","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"xeclHwaBfWUk","alg":"RS256","n":"agKgapd_TCnHukBfaczoqFNKVyZ8DF8N6GSmwS2M7olbfL3s","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
