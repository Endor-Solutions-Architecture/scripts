package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"XJhVzL5sAjla","alg":"RS256","n":"6eRirtynNoSNo_rYtTxi_6_2Byy7XxzQPtuQfg4ZaGhAz02T","e":"AQAB","d":"nxUeveTu"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"XJhVzL5sAjla","alg":"RS256","n":"6eRirtynNoSNo_rYtTxi_6_2Byy7XxzQPtuQfg4ZaGhAz02T","e":"AQAB","d":"nxUeveTu"}
  _ = jwt.MapClaims{"jwk": m}
}
