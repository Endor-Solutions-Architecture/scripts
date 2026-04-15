package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"1AQ6J8YnsJOs","alg":"RS256","n":"jwMlxs6QpyoQoyNDRUSv0MPX_mms86h8orwHU7S7PWg2sRG8","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"1AQ6J8YnsJOs","alg":"RS256","n":"jwMlxs6QpyoQoyNDRUSv0MPX_mms86h8orwHU7S7PWg2sRG8","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
