package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"UCTnkQ1x2Dbf","alg":"RS256","n":"ilVk3lcT76xLBDFhFZQlfeOWCcfHKhfd6nlWvOMJ3xrDizC5","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"UCTnkQ1x2Dbf","alg":"RS256","n":"ilVk3lcT76xLBDFhFZQlfeOWCcfHKhfd6nlWvOMJ3xrDizC5","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
