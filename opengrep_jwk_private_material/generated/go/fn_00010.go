package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"3w1XcX7uCFvx","alg":"RS256","n":"QSWIhez-bqjOL9-g8f-x05eIDJ_AK98CPSjyfI9ULWjttSdg","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"3w1XcX7uCFvx","alg":"RS256","n":"QSWIhez-bqjOL9-g8f-x05eIDJ_AK98CPSjyfI9ULWjttSdg","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
