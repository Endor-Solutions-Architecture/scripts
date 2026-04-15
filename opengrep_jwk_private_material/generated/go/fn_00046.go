package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"SFkTQ7G1oxhO","alg":"RS256","n":"1pjeRA7Z6-Jtbor4DhJEixzuVdjRm_ctWz4WmG66_G7erjcd","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"SFkTQ7G1oxhO","alg":"RS256","n":"1pjeRA7Z6-Jtbor4DhJEixzuVdjRm_ctWz4WmG66_G7erjcd","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
