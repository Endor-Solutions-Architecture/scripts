package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"jPKmkVXcsKxX","alg":"RS256","n":"CKvrpL7h0nuA1FdTkonwNFhuIjZol2FV-NKbv-Bpp1X_SQPs","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"jPKmkVXcsKxX","alg":"RS256","n":"CKvrpL7h0nuA1FdTkonwNFhuIjZol2FV-NKbv-Bpp1X_SQPs","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
